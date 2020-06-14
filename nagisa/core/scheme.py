import weakref
import collections
import typing
from typing import List, Tuple, Any

_PRIMITIVE_TYPES = (int, float, bool, str)
_ACCEPTED_TYPES = frozenset([
    *_PRIMITIVE_TYPES,
    *(List[x] for x in _PRIMITIVE_TYPES),
    *(Tuple[x] for x in _PRIMITIVE_TYPES),
])

def _compatible_with(T1, T2) -> bool:

    if T1 is T2:
        return True

    if T1 is int and T2 is float:
        return True

    o_T1 = typing.get_origin(T1)
    o_T2 = typing.get_origin(T2)

    if o_T1 is o_T2 and o_T1 is not None:
        return _compatible_with(typing.get_args(T1)[0], typing.get_args(T2)[0])

    return False

def _get_default_value(T):
    origin_type = typing.get_origin(T)
    if origin_type is None:
        return T()
    return origin_type()

def _infer_type(value, allow_empty_container=False):
    type_ = type(value)
    if type_ in (list, tuple):
        con_type = { list: List, tuple: Tuple }[type_]
        if len(value) == 0:
            if not allow_empty_container:
                raise TypeError('Cannot infer type for empty container {!r}.'.format(value))
            return con_type

        elem_type = _infer_type(value[0])
        for i, x in enumerate(value[1:], start=1):
            if not _compatible_with(_infer_type(x), elem_type):
                raise TypeError(
                    'Cannot infer type for container object {!r}, '
                    'since the {}-th element {!r} has different type as previous.'.format(value, i, x))

        return con_type[elem_type]

    return type_

def _check_type(value, type_) -> bool:
    return _compatible_with(_infer_type(value), type_)

def _stringify_type(T) -> str:

    origin_type = typing.get_origin(T)

    if origin_type is None: 
        return T.__name__

    return str(T)


class NodeMeta:

    __slots__ = ['attributes', 'type', 'is_container', 'is_alias']

    def __init__(self, type_=None, attributes=None, is_container=False, is_alias=False):
        self.type = type_
        self.attributes = attributes
        self.is_container = is_container
        self.is_alias = is_alias

    def is_valid(self):
        return True

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

            if default is None:
                default = _get_default_value(type_)
                final_type = type_
            elif type_ is None:
                final_type = _infer_type(default)
            else:
                inferred_type = _infer_type(default)
                assert _compatible_with(inferred_type, type_), \
                    "Type of `{!r}` is `{!r}`, which could not match with `type_` {!r}.".format(
                        default, inferred_type, type_
                    )
                final_type = type_
            assert final_type in _ACCEPTED_TYPES, \
                "Type {!r} is not acceptable.".format(final_type)
            self.__value = default
        else:
            self.__alias_entries = dict()
            self.__entries = dict()
            final_type = None

        attributes = self.__class__._parse_attributes(attributes)
        self.__meta = NodeMeta(type_=final_type, attributes=attributes, is_container=is_container)
        self.__parent = weakref.ref(parent) if parent is not None else None

        self.__finalized = not is_container

    @classmethod
    def _parse_attributes(cls, attributes):
        if attributes is None:
            return ()
        return tuple(attributes.split())
        raise NotImplementedError

    def is_writable(self):
        return 'writable' in self.__meta.attributes

    def __update_value(self, value):
        self.__check_finalized('update value', True)
        self.__check_is_container('update value', False)

        if not self.is_writable():
            raise AttributeError("Cannot update a read-only node.")

        if not _check_type(value, self.__meta.type):
            raise TypeError(
                "Cannot update `{!r}` node with value {!r}.".format(
                    self.__meta.type, value
            ))

        self.__value = value

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
            if not self.is_writable():
                raise RuntimeError("Cannot set attribute on read-only node.")

            self.__add_entry(name, value, attributes="writable")

    def __add_entry(self, name, node, attributes=None):

        if name in dir(self):
            raise RuntimeError('Cannot use preserved name "{}" as entry.'.format(name))

        self.__entries[name] = self.new_from_primitive(node, parent=self, attributes=attributes).finalize()

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
                _stringify_type(self.__meta.type), 
                self.__value
            )

        retstr = ' ' * (level * indent_size)
        for key, entry in sorted(self.__entries.items(), key=lambda x: x[1].__meta.is_container):
            retstr += '{}: '.format(key)
            if entry.__meta.is_container:
                retstr += '\n'
            retstr += '{}\n'.format(entry.to_str(level + 1, indent_size))
        for src, target in sorted(self.__alias_entries.items(), key=lambda x: x[0]):
            retstr += '{} -> {}\n'.format(src, target)

        return retstr

    def __str__(self):
        return self.to_str(level=0)