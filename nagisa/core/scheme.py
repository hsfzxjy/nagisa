import weakref
import collections
from typing import List, Any
from nagisa.utils.primitive_typing import *

class NodeMeta:

    __slots__ = ['attributes', 'type', 'is_container', 'is_alias']

    def __init__(self, type_=None, attributes=None, is_container=False, is_alias=False):
        self.type = type_
        self.attributes = attributes
        self.is_container = is_container
        self.is_alias = is_alias

    def is_valid(self):
        return True

class _AttributeSlots:
    pass

class SchemeNode:

    __slots__ = ['__meta', '__value', '__alias_entries', '__entries', '__finalized', '__parent', '__weakref__']

    @classmethod
    def new_from_primitive(cls, value: Any, parent=None, attributes=None):

        if isinstance(value, cls):
            value.__parent = parent
            return value

        if isinstance(value, dict):
            result = cls(
                attributes=attributes,
                is_container=True,
                parent=parent
            )
            for k, v in value.items():
                result.entry(k, cls.new_from_primitive(v, parent, attributes))
        else:
            result = cls(default=value, parent=parent, attributes=attributes)
            
        return result

    def __init__(self, parent=None, default=None, type_=None, attributes=None, is_container=False):
        if not is_container:
            assert default is not None or type_ is not None, \
                "At least one of `type_` or `default` should be provided."

            type_ = regularize_type(type_)
            if default is None:
                final_type = type_
            elif type_ is None:
                final_type = infer_type(default)
            else:
                inferred_type = infer_type(default)
                assert compatible_with(inferred_type, type_), \
                    "Type of `{!r}` is `{!r}`, which could not match with `type_` {!r}.".format(
                        default, inferred_type, type_
                    )
                final_type = type_
            assert is_acceptable_type(final_type), \
                "Type {!r} is not acceptable.".format(final_type)
            if default is None:
                default = get_default_value(final_type)
            self.__value = cast(default, final_type)
        else:
            self.__alias_entries = dict()
            self.__entries = dict()
            final_type = None

        attributes = self.__class__.__parse_attributes(attributes)
        self.__meta = NodeMeta(type_=final_type, attributes=attributes, is_container=is_container)
        self.__parent = weakref.ref(parent) if parent is not None else None

        self.__finalized = not is_container

    @classmethod
    def __parse_attributes(cls, attributes):
        ns = _AttributeSlots()

        if attributes is None:
            attributes = []

        if isinstance(attributes, str):
            attributes = attributes.split()

        ns.writable = False
        for attr_item in attributes:
            if attr_item.lower() in ('w', 'writable'):
                ns.writable = True

        cls._parse_attributes(ns, attributes)
        return ns

    @classmethod
    def _parse_attributes(cls, ns, attributes):
        pass

    def __update_value(self, value):
        self.__check_finalized('update value', True)
        self.__check_is_container('update value', False)

        if not self.__meta.attributes.writable:
            raise AttributeError("Cannot update a read-only node.")

        if not check_type(value, self.__meta.type):
            raise TypeError(
                "Cannot update `{!r}` node with value {!r}.".format(
                    self.__meta.type, value
            ))

        self.__value = cast(value, self.__meta.type)

    def __getattr__(self, name):
        if name == '__dict__':
            raise AttributeError

        if name not in set(self.__alias_entries) | set(self.__entries):
            raise AttributeError("Attribute \"{}\" not found.".format(name))

        if name in self.__alias_entries:
            name = self.__alias_entries[name]

        node = self.__entries[name]
        if node.__meta.is_container:
            return node
        else:
            return node.__value

    def __setattr__(self, name, value):

        if any(name.endswith(x) for x in self.__class__.__slots__):
            object.__setattr__(self, name, value)
            return

        self.__check_finalized('update attribute', True)
        self.__check_is_container('update attribute', True)

        if name in self.__alias_entries:
            name = self.__alias_entries[name]

        if name in self.__entries:
            self.__entries[name].__update_value(value)
        else:
            if not self.__meta.attributes.writable:
                raise RuntimeError("Cannot set attribute on read-only node.")

            self.__add_entry(name, value, attributes="writable")

    def __add_entry(self, name, node, attributes=None):

        if name in dir(self):
            raise RuntimeError('Cannot use preserved name "{}" as entry.'.format(name))

        self.__entries[name] = self.new_from_primitive(node, parent=self, attributes=attributes)

    def entry(self, name, node):
        assert name not in self.__entries, \
            "Entry name \"{}\" already exists.".format(name)

        self.__add_entry(name, node)
        return self

    def finalize(self):
        if self.__finalized:
            return self

        self.__verify_alias()
        self.__finalized = True
        for entry in self.__entries.values():
            if entry.__meta.is_container:
                entry.finalize()

        return self

    def __check_finalized(self, action: str, value: bool):
        if self.__finalized != value:
            raise RuntimeError('Cannot {} {} the object is finalized.'.format(
                action, 'before' if value else 'after'
            ))

    def __check_is_container(self, action: str, value: bool):
        if self.__meta.is_container != value:
            raise RuntimeError('Cannot {} on {} node.'.format(
                action, 'non-container' if value else 'container'
            ))

    def alias(self, name: str, target: str):
        self.__check_finalized('create alias', False)
        self.__check_is_container('create alias', True)

        assert name.isidentifier(), \
            "Alias name should be valid Python identifier, got \"{}\".".format(name)
        assert target.isidentifier(), \
            "Alias target should be valid Python identifier, got \"{}\".".format(target)

        self.__alias_entries[name] = target
        return self
        
    def __get_meta_by_path(self, path: str):
        ptr = self
        for part in path.split('.'):
            ptr = getattr(ptr, part, None)
            if not isinstance(ptr, self.__class__):
                return InvalidMeta()
        return ptr.__meta

    def __verify_alias(self):
        if not self.__meta.is_container:
            return

        duplicated = set(self.__alias_entries) & set(self.__entries)
        assert not duplicated, \
            "Aliases {} duplicated with existing entries.".format(
                ', '.join('"{}"'.format(x) for x in duplicated)
            )

        for name, target in self.__alias_entries.items():
            visited = [name, target]
            ptr = target
            while ptr not in self.__entries:
                if ptr not in self.__alias_entries:
                    raise RuntimeError(
                        "Broken alias {} (not an entry).".format(
                            ' -> '.join(visited)
                        )
                    )
                ptr = self.__alias_entries[ptr]
                if ptr in visited:
                    raise RuntimeError(
                        "Cyclic alias {}.".format(
                            ' -> '.join(visited + [ptr])
                        )
                    )
                visited.append(ptr)
            self.__alias_entries[name] = ptr

    def to_str(self, level=0, indent_size=2):
        if not self.__meta.is_container:
            return '({}) {}'.format(
                stringify_type(self.__meta.type), 
                self.__value
            )

        indent = ' ' * (level * indent_size)
        retstr = ''
        for key, entry in sorted(self.__entries.items(), key=lambda x: x[1].__meta.is_container):
            retstr += '{}{}:'.format(indent, key)
            content = entry.to_str(level + 1, indent_size)
            if entry.__meta.is_container:
                retstr += '\n{}'.format(content)
            else:
                retstr += ' {}\n'.format(content)
        for src, target in sorted(self.__alias_entries.items(), key=lambda x: x[0]):
            retstr += '{} -> {}\n'.format(src, target)

        return retstr

    def __str__(self):
        return self.to_str(level=0)