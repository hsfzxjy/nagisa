import weakref
import inspect
import collections
from typing import Any
from nagisa.core.misc import accessor
from nagisa.core.primitive.typing import *
from nagisa.core.primitive.proxy import proxy
from nagisa.core.misc.serialization import load_yaml_with_base, dump_yaml


class NodeMeta:

    __slots__ = ["attributes", "type", "is_container", "is_alias"]

    def __init__(
        self, type_=None, attributes=None, is_container=False, is_alias=False
    ):
        self.type = type_
        self.attributes = attributes
        self.is_container = is_container
        self.is_alias = is_alias


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
            if parent is not None:
                value._parent = weakref.ref(parent)
            return value

        if isinstance(value, dict):
            result = cls(
                attributes=attributes, is_container=True, parent=parent
            )
            for k, v in value.items():
                result.entry(
                    k,
                    cls.new_from_primitive(
                        value=v, parent=result, attributes=attributes
                    ),
                )
        else:
            result = cls(default=value, parent=parent, attributes=attributes)

        return result

    def __init__(
        self,
        parent=None,
        default=None,
        type_=None,
        attributes=None,
        is_container=False
    ):
        if not is_container:
            assert (
                default is not None or type_ is not None
            ), "At least one of `type_` or `default` should be provided."

            if default is None:
                final_type = type_
            elif type_ is None:
                final_type = infer_type(default)
            else:
                assert check_type(
                    default, type_
                ), f"Value {default!r} is incompatible with type {type_!r}"
                final_type = type_

            is_acceptable_type(final_type, raise_exc=True)
            if default is None:
                default = get_default_value(final_type)
            self._value = proxy(
                cast(default, final_type, check=False),
                T=final_type,
                mutable=True,
                host=self,
            )
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

    __getitem__ = __getattr__

    def __setattr__(self, name, value):

        if any(name.endswith(x) for x in SchemeNode.__slots__):
            object.__setattr__(self, name, value)
            return

        self.__check_is_container("update attribute", True)

        if name in self._alias_entries:
            name = self._alias_entries[name]

        self._update_value(value, entry_name=name, action="update")

    __setitem__ = __setattr__

    def __str__(self):
        return self.to_str(level=0)

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
                        "Broken alias {} (not an entry).".format(
                            " -> ".join(visited)
                        )
                    )
                ptr = self._alias_entries[ptr]
                if ptr in visited:
                    raise RuntimeError(
                        "Cyclic alias {}.".format(
                            " -> ".join(visited + [ptr])
                        )
                    )
                visited.append(ptr)
            self._alias_entries[name] = ptr

    def __add_entry(self, name, value, attributes=None):

        if name in dir(self):
            raise RuntimeError(
                'Cannot use preserved name "{}" as entry.'.format(name)
            )

        node = self.new_from_primitive(
            value, parent=self, attributes=attributes
        )
        self._entries[name] = node
        return node

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

    def _walk(self, path, func):
        if not self._meta.is_container:
            func(path, self)
            return

        for key, entry in self._entries.items():
            entry._walk(path + [key], func)

    @classmethod
    def _parse_attributes(cls, ns, attributes):
        pass

    def _update_value(self, obj, *, entry_name=None, action="update"):
        assert action in ("update", "merge")

        if entry_name is None:
            host = self
        else:
            assert self._meta.is_container

            if entry_name not in self._entries:
                if not self._meta.attributes.writable:
                    raise AttributeError(
                        f"Entry {entry_name!r} not found on container {self.dotted_path()!r}."
                    )
                else:
                    host = self
                    obj = {entry_name: obj}
                    action = "merge"
            else:
                host = self._entries[entry_name]

        if self._finalized and not host._meta.attributes.writable:
            raise AttributeError(
                f"Cannot update read-only entry {host.dotted_path()!r}."
            )

        if host._meta.is_container:
            if not isinstance(obj, dict):
                raise TypeError(
                    f"Expect value to be a dict for container entry {host.dotted_path()!r}, got {type(obj)!r}."
                )

            extra_entries = set(obj) - set(host._entries)
            if not host._meta.attributes.writable and extra_entries:
                verbose_extra_entries = ", ".join(
                    map("{!r}".format, extra_entries)
                )
                raise AttributeError(
                    f"Adding extra entries {verbose_extra_entries} to read-only container {host.dotted_path()!r} is forbidden."
                )

            if host._meta.attributes.writable and action == "update":
                host._entries.clear()
                host._alias_entries.clear()

            for name, value in obj.items():
                if name in host._entries:
                    host._entries[name]._update_value(value, action=action)
                else:
                    entry = host.__add_entry(
                        name, value, attributes="writable"
                    )
                    if host._finalized:
                        entry.finalize()
        else:
            if not check_type(obj, host._meta.type):
                raise TypeError(
                    f"Cannot update {host._meta.type!r} type entry {host.dotted_path()!r} with value {obj!r}."
                )

            host._value = proxy(
                cast(obj, host._meta.type, check=False),
                T=host._meta.type,
                mutable=host.mutable,
                host=host,
            )

    @property
    def mutable(self):
        return not self._finalized or self._meta.attributes.writable

    def dotted_path(self):
        entry = self
        paths = []
        while True:
            parent = entry._parent() if entry._parent is not None else None
            if parent is None:
                break
            for k, v in parent._entries.items():
                if v is entry:
                    paths.append(k)
                    break
            entry = parent

        return ".".join(reversed(paths))

    def entry(self, name, node):
        assert name not in self._entries, 'Entry name "{}" already exists.'.format(
            name
        )

        self.__add_entry(name, node)
        return self

    def finalize(self):
        if not self._meta.is_container:
            self._finalized = True
            if hasattr(self._value, 'mutable'):
                self._value.mutable(self._meta.attributes.writable)
            return self

        if self._finalized:
            return self

        self.__verify_alias()
        self._finalized = True
        for entry in self._entries.values():
            entry.finalize()

        return self

    def alias(self, name: str, target: str):
        self.__check_finalized("create alias", False)
        self.__check_is_container("create alias", True)

        assert (name.isidentifier(
        )), 'Alias name should be valid Python identifier, got "{}".'.format(
            name
        )
        assert (target.isidentifier(
        )), 'Alias target should be valid Python identifier, got "{}".'.format(
            target
        )

        self._alias_entries[name] = target
        return self

    def to_str(self, level=0, indent_size=2):
        if not self._meta.is_container:
            return "({}) {}".format(
                stringify_type(self._meta.type), self._value
            )

        indent = " " * (level * indent_size)
        retstr = ""
        for key, entry in sorted(self._entries.items(),
                                 key=lambda x: x[1]._meta.is_container):
            retstr += "{}{}:".format(indent, key)
            content = entry.to_str(level + 1, indent_size)
            if entry._meta.is_container:
                retstr += "\n{}".format(content)
            else:
                retstr += " {}\n".format(content)
        for src, target in sorted(self._alias_entries.items(),
                                  key=lambda x: x[0]):
            retstr += "{} -> {}\n".format(src, target)

        return retstr

    def value_by_path(self, path: str):
        node = self
        for part in path.split("."):
            node = getattr(node, part)
        return node

    def value_dict(self):
        if not self._meta.is_container:
            if hasattr(self._value, 'as_primitive'):
                return self._value.as_primitive()
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

    def merge_from_dict(self, dct):
        self._update_value(dct, action="merge")
        return self

    def merge_from_file(self, filename: str):
        dct = load_yaml_with_base(filename, caller_level=-4)
        self.merge_from_dict(dct)
        return self

    def dump(self, output):
        dump_yaml(self.value_dict(), output)
        return self

    def _merge_from_directives(self, directives, ext_syntax=True):
        def _attrsetter(obj: SchemeNode, key, value):
            obj._entries[key]._update_value(value)

        def _attrchecker(obj: SchemeNode, key):
            return key in obj._entries

        for directive, value in directives:
            accessor.modify(
                self, directive, value, ext_syntax, _attrsetter, _attrchecker
            )

        return self

    @classmethod
    def from_class(cls, singleton=False):
        def _decorator(template):
            return _class_to_scheme(cls, template, singleton=singleton)

        if isinstance(singleton, bool):
            return _decorator
        template = singleton
        return _class_to_scheme(cls, template)

    @staticmethod
    def writable(klass):
        klass.__writable__ = True
        return klass

    @classmethod
    def _handle_singleton(cls, instance):
        pass


class _class_to_scheme:
    __slots__ = ("scheme_class", "template", "singleton", "__instance")

    def __init__(self, scheme_class, template, singleton=False):
        self.scheme_class = scheme_class
        self.template = template
        self.singleton = singleton
        self.__instance = None

    def __repr__(self):
        return f"<{self.scheme_class.__name__} Constructor>"

    def __call__(self):
        if self.singleton:
            if self.__instance is None:
                self.__instance = self._parse(self.scheme_class, self.template)
                self.scheme_class._handle_singleton(self.__instance)
            return self.__instance
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

        for name, annotation in getattr(template, "__annotations__",
                                        {}).items():
            T, attributes, alias = self._parse_annotation(annotation)

            if alias is not None:
                alias_entries[name] = alias
            else:
                entries[name]["type_"] = T
                entries[name]["attributes"] = attributes

        for name, kwargs in entries.items():
            child_node = (
                kwargs["default"]
                if kwargs.get("is_container") else scheme_class(**kwargs)
            )
            node.entry(name, child_node)
        for name, alias in alias_entries.items():
            node.alias(name, alias)

        return node

    def _get_entryname_default_pairs(self, template):
        return [
            (name, value) for name, value in inspect.getmembers(template)
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
            raise TypeError(f"Annotations {annotations!r} cannot be parsed.")

        T = None
        if is_acceptable_type(annotations[0]):
            T = annotations[0]
            attributes = annotations[1:]
        else:
            attributes = annotations[:]

        return T, attributes, None
