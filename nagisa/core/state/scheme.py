import weakref
import inspect
import collections
from typing import List, Any
from nagisa.utils.primitive.typing import *


class NodeMeta:

    __slots__ = ["attributes", "type", "is_container", "is_alias"]

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

    __slots__ = [
        "_meta",
        "_value",
        "_alias_entries",
        "_entries",
        "_finalized",
        "_parent",
        "__weakref__",
    ]

    @classmethod
    def new_from_primitive(cls, value: Any, parent=None, attributes=None):

        if isinstance(value, cls):
            value._parent = parent
            return value

        if isinstance(value, dict):
            result = cls(attributes=attributes, is_container=True, parent=parent)
            for k, v in value.items():
                result.entry(k, cls.new_from_primitive(v, parent, attributes))
        else:
            result = cls(default=value, parent=parent, attributes=attributes)

        return result

    def __init__(
        self, parent=None, default=None, type_=None, attributes=None, is_container=False
    ):
        if not is_container:
            assert (
                default is not None or type_ is not None
            ), "At least one of `type_` or `default` should be provided."

            type_ = regularize_type(type_)
            if default is None:
                final_type = type_
            elif type_ is None:
                final_type = infer_type(default)
            else:
                inferred_type = infer_type(default)
                assert compatible_with(
                    inferred_type, type_
                ), "Type of `{!r}` is `{!r}`, which could not match with `type_` {!r}.".format(
                    default, inferred_type, type_
                )
                final_type = type_
            assert is_acceptable_type(
                final_type
            ), "Type {!r} is not acceptable.".format(final_type)
            if default is None:
                default = get_default_value(final_type)
            self._value = cast(default, final_type)
        else:
            self._alias_entries = dict()
            self._entries = dict()
            final_type = None

        attributes = self.__class__.__parse_attributes(attributes)
        self._meta = NodeMeta(
            type_=final_type, attributes=attributes, is_container=is_container
        )
        self._parent = weakref.ref(parent) if parent is not None else None

        self._finalized = False

    @classmethod
    def __parse_attributes(cls, attributes):
        ns = _AttributeSlots()

        if attributes is None:
            attributes = []

        if isinstance(attributes, str):
            attributes = attributes.split()

        ns.writable = False
        for attr_item in attributes:
            if attr_item.lower() in ("w", "writable"):
                ns.writable = True

        cls._parse_attributes(ns, attributes)
        return ns

    @classmethod
    def _parse_attributes(cls, ns, attributes):
        pass

    def _update_value(self, value):
        if self._finalized:
            self.__check_is_container("update value", False)

            if not self._meta.attributes.writable:
                raise AttributeError("Cannot update a read-only node.")

        if not check_type(value, self._meta.type):
            raise TypeError(
                "Cannot update `{!r}` node with value {!r}.".format(
                    self._meta.type, value
                )
            )

        self._value = cast(value, self._meta.type)

    def __getattr__(self, name):
        if name == "__dict__":
            raise AttributeError

        if name not in set(self._alias_entries) | set(self._entries):
            raise AttributeError('Attribute "{}" not found.'.format(name))

        if name in self._alias_entries:
            name = self._alias_entries[name]

        node = self._entries[name]
        if node._meta.is_container:
            return node
        else:
            return node._value

    def __setattr__(self, name, value):

        if any(name.endswith(x) for x in SchemeNode.__slots__):
            object.__setattr__(self, name, value)
            return

        self.__check_finalized("update attribute", True)
        self.__check_is_container("update attribute", True)

        if name in self._alias_entries:
            name = self._alias_entries[name]

        if name in self._entries:
            self._entries[name]._update_value(value)
        else:
            if not self._meta.attributes.writable:
                raise RuntimeError("Cannot set attribute on read-only node.")

            entry = self.__add_entry(name, value, attributes="writable")
            if self._finalized:
                entry.finalize()

    def __add_entry(self, name, value, attributes=None):

        if name in dir(self):
            raise RuntimeError('Cannot use preserved name "{}" as entry.'.format(name))

        node = self.new_from_primitive(value, parent=self, attributes=attributes)
        self._entries[name] = node
        return node

    def entry(self, name, node):
        assert name not in self._entries, 'Entry name "{}" already exists.'.format(name)

        self.__add_entry(name, node)
        return self

    def finalize(self):
        if not self._meta.is_container:
            self._finalized = True
            return self

        if self._finalized:
            return self

        self.__verify_alias()
        self._finalized = True
        for entry in self._entries.values():
            entry.finalize()

        return self

    def __check_finalized(self, action: str, value: bool):
        if self._finalized != value:
            raise RuntimeError(
                "Cannot {} {} the object is finalized.".format(
                    action, "before" if value else "after"
                )
            )

    def __check_is_container(self, action: str, value: bool):
        if self._meta.is_container != value:
            raise RuntimeError(
                "Cannot {} on {} node.".format(
                    action, "non-container" if value else "container"
                )
            )

    def alias(self, name: str, target: str):
        self.__check_finalized("create alias", False)
        self.__check_is_container("create alias", True)

        assert (
            name.isidentifier()
        ), 'Alias name should be valid Python identifier, got "{}".'.format(name)
        assert (
            target.isidentifier()
        ), 'Alias target should be valid Python identifier, got "{}".'.format(target)

        self._alias_entries[name] = target
        return self

    def __get_meta_by_path(self, path: str):
        ptr = self
        for part in path.split("."):
            ptr = getattr(ptr, part, None)
            if not isinstance(ptr, self.__class__):
                return InvalidMeta()
        return ptr._meta

    def __verify_alias(self):
        if not self._meta.is_container:
            return

        duplicated = set(self._alias_entries) & set(self._entries)
        assert not duplicated, "Aliases {} duplicated with existing entries.".format(
            ", ".join('"{}"'.format(x) for x in duplicated)
        )

        for name, target in self._alias_entries.items():
            visited = [name, target]
            ptr = target
            while ptr not in self._entries:
                if ptr not in self._alias_entries:
                    raise RuntimeError(
                        "Broken alias {} (not an entry).".format(" -> ".join(visited))
                    )
                ptr = self._alias_entries[ptr]
                if ptr in visited:
                    raise RuntimeError(
                        "Cyclic alias {}.".format(" -> ".join(visited + [ptr]))
                    )
                visited.append(ptr)
            self._alias_entries[name] = ptr

    def to_str(self, level=0, indent_size=2):
        if not self._meta.is_container:
            return "({}) {}".format(stringify_type(self._meta.type), self._value)

        indent = " " * (level * indent_size)
        retstr = ""
        for key, entry in sorted(
            self._entries.items(), key=lambda x: x[1]._meta.is_container
        ):
            retstr += "{}{}:".format(indent, key)
            content = entry.to_str(level + 1, indent_size)
            if entry._meta.is_container:
                retstr += "\n{}".format(content)
            else:
                retstr += " {}\n".format(content)
        for src, target in sorted(self._alias_entries.items(), key=lambda x: x[0]):
            retstr += "{} -> {}\n".format(src, target)

        return retstr

    def __str__(self):
        return self.to_str(level=0)

    @classmethod
    def from_class(cls, template):
        return _class_to_scheme(cls, template)

    @staticmethod
    def writable(klass):
        klass.__writable__ = True
        return klass

    def value_dict(self):
        if not self._meta.is_container:
            return self._value

        dct = {}
        for name, child_node in self._entries.items():
            dct[name] = child_node.value_dict()

        return dct

    def type_dict(self):
        if not self._meta.is_container:
            return self._meta.type

        dct = {}
        for name, child_node in self._entries.items():
            dct[name] = child_node.type_dict()

        return dct


class _class_to_scheme:
    def __init__(self, scheme_class, template):
        self.scheme_class = scheme_class
        self.template = template

    def __repr__(self):
        return f'<{self.scheme_class.__name__} Constructor>'

    def __call__(self):
        return self._parse(self.scheme_class, self.template)

    def _parse(self, scheme_class, template):
        return self._constructor_scheme_node(scheme_class, template)

    def _constructor_scheme_node(self, scheme_class, template):
        entries = collections.defaultdict(dict)
        alias_entries = {}

        if getattr(template, "__writable__", False):
            attributes = ["writable"]
        else:
            attributes = []
        node = scheme_class(is_container=True, attributes=attributes)

        for name, default in self._get_entryname_default_pairs(template):
            if inspect.isclass(default):
                default = self._constructor_scheme_node(scheme_class, default)
                entries[name]["is_container"] = True

            entries[name]["default"] = default

        for name, annotation in getattr(template, "__annotations__", {}).items():
            T, attributes, alias = self._parse_annotation(annotation)

            if alias is not None:
                alias_entries[name] = alias
            else:
                entries[name]["type_"] = T
                entries[name]["attributes"] = attributes

        for name, kwargs in entries.items():
            child_node = (
                kwargs["default"]
                if kwargs.get("is_container")
                else scheme_class(**kwargs)
            )
            node.entry(name, child_node)
        for name, alias in alias_entries.items():
            node.alias(name, alias)

        return node

    def _get_entryname_default_pairs(self, template):
        return [
            (name, value)
            for name, value in inspect.getmembers(template)
            if not name.startswith("__")
        ]

    def _parse_annotation(self, annotations):
        if isinstance(annotations, str):
            return None, None, annotations
        elif is_acceptable_type(annotations):
            return annotations, None, None
        elif isinstance(annotations, list):
            assert len(annotations) > 0
        else:
            raise TypeError("Annotations `{!r}` cannot be parsed.".format(annotations))

        T = None
        if is_acceptable_type(annotations[0]):
            T = annotations[0]
            attributes = annotations[1:]
        else:
            attributes = annotations[:]

        return T, attributes, None

