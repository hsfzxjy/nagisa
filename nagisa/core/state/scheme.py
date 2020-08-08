# pylint: disable=attribute-defined-outside-init

import weakref
import inspect
import collections
from typing import Any
from nagisa.core.misc import accessor
from nagisa.core.primitive import typing
from nagisa.core.primitive.proxy import proxy
from nagisa.core.misc.serialization import load_yaml_with_base, dump_yaml


class NodeMeta:

    __slots__ = ["attributes", "type", "is_container", "is_alias"]

    def __init__(self, type_=None, attributes=None, is_container=False, is_alias=False):
        self.type = type_
        self.attributes = attributes
        self.is_container = is_container
        self.is_alias = is_alias


class _AttributeSlots:
    pass


class SchemeNode:

    __slots__ = [
        "_meta_",
        "_value_",
        "_alias_entries_",
        "_entries_",
        "_finalized_",
        "_parent_",
        "__weakref__",
    ]

    @classmethod
    def new_from_primitive(cls, value: Any, parent=None, attributes=None):

        if isinstance(value, cls):
            if parent is not None:
                value._parent_ = weakref.ref(parent)
            return value

        if isinstance(value, dict):
            result = cls(attributes=attributes, is_container=True, parent=parent)
            for k, v in value.items():
                result.entry(
                    k,
                    cls.new_from_primitive(value=v, parent=result, attributes=attributes),
                )
        else:
            result = cls(default=value, parent=parent, attributes=attributes)

        return result

    def __reduce__(self):
        meta_dict = {}
        alias_dict = {}

        def _visitor(path, node):
            meta_dict[path] = node._meta_
            if node._meta_.is_container:
                alias_dict[path] = node._alias_entries_

        self._walk_((), _visitor, visit_container=True)
        return (self._reconstruct_, (self.value_dict(), meta_dict, alias_dict, self._finalized_))

    @classmethod
    def _reconstruct_(cls, value_dict, meta_dict, alias_dict, finalized):
        def _build(value, path, parent):
            meta = meta_dict[path]
            if isinstance(value, dict):
                result = cls(is_container=True, parent=parent, meta=meta)
                for k, v in value.items():
                    result.entry(k, _build(v, path + (k, ), result))
            else:
                result = cls(default=value, meta=meta)

            return result

        result = _build(value_dict, (), None)
        if finalized:
            result.finalize()

        return result

    @staticmethod
    def _infer_(type_, value):
        assert value is not None or type_ is not None, \
            "At least one of `type_` or `default` should be provided"

        if value is None:
            final_type = type_
        elif type_ is None:
            final_type = typing.inferT(value)
        else:
            assert typing.checkT(value, type_), \
                f"Value {value!r} is incompatible with type {type_!r}"
            final_type = type_

        typing.is_acceptableT(final_type, raise_exc=True)
        if value is None:
            value = typing.get_default_value(final_type)

        return final_type, value

    def __init__(
        self,
        parent=None,
        default=None,
        type_=None,
        attributes=None,
        is_container=False,
        meta=None,
    ):
        if not is_container:
            if meta is None:
                final_type, default = self._infer_(type_, default)
            else:
                final_type = meta.type
            self._value_ = proxy(
                typing.cast(default, final_type, check=False),
                T=final_type,
                mutable=True,
                host=self,
            )
        else:
            self._alias_entries_ = dict()
            self._entries_ = dict()
            final_type = None

        if meta is None:
            attributes = self.__class__.__parse_attributes__(attributes)
            self._meta_ = NodeMeta(
                type_=final_type, attributes=attributes, is_container=is_container
            )
        else:
            self._meta_ = meta
        self._parent_ = weakref.ref(parent) if parent is not None else None

        self._finalized_ = False

    def __getattr__(self, name):
        if name == "__dict__":
            raise AttributeError

        if not self.has_entry(name):
            raise AttributeError(f"Attribute {name!r} not found")

        if name in self._alias_entries_:
            name = self._alias_entries_[name]

        node = self._entries_[name]
        if node._meta_.is_container:
            return node

        return node._value_

    __getitem__ = __getattr__

    def __setattr__(self, name, value):

        if any(name.endswith(x) for x in SchemeNode.__slots__):
            object.__setattr__(self, name, value)
            return

        self._check_is_container_("update attribute", True)

        if name in self._alias_entries_:
            name = self._alias_entries_[name]

        self._update_value_(value, entry_name=name, action="update")

    __setitem__ = __setattr__

    def __str__(self):
        return self.to_str(level=0)

    def _check_finalized_(self, action: str, value: bool):
        if self._finalized_ != value:
            prep = "before" if value else "after"
            raise RuntimeError(f"Cannot {action} {prep} the object is finalized")

    def _check_is_container_(self, action: str, value: bool):
        if self._meta_.is_container != value:
            adj = "non-container" if value else "container"
            raise RuntimeError(f"Cannot {action} on {adj} node")

    def _check_alias_(self):
        if not self._meta_.is_container:
            return

        duplicated = set(self._alias_entries_) & set(self._entries_)
        assert not duplicated, \
            "Aliases {} duplicated with existing entries".format(
                ", ".join(f'{x!r}' for x in duplicated)
            )

        for name, target in self._alias_entries_.items():
            visited = [name, target]
            ptr = target
            while ptr not in self._entries_:
                if ptr not in self._alias_entries_:
                    raise RuntimeError(
                        "Broken alias {} (not an entry)".format(" -> ".join(visited))
                    )
                ptr = self._alias_entries_[ptr]
                if ptr in visited:
                    raise RuntimeError("Cyclic alias {}".format(" -> ".join(visited + [ptr])))
                visited.append(ptr)
            self._alias_entries_[name] = ptr

    def _add_entry_(self, name, value, attributes=None):

        if name in dir(self):
            raise RuntimeError(f'Cannot use preserved name {name!r} as entry.')

        node = self.new_from_primitive(value, parent=self, attributes=attributes)
        self._entries_[name] = node
        return node

    @classmethod
    def __parse_attributes__(cls, attributes):
        ns = _AttributeSlots()

        if attributes is None:
            attributes = []

        if isinstance(attributes, str):
            attributes = attributes.split()

        ns.writable = False
        for attr_item in attributes:
            if attr_item.lower() in ("w", "writable"):
                ns.writable = True

        cls._parse_attributes_(ns, attributes)
        return ns

    def _walk_(self, path, func, *, visit_container=False):
        if not self._meta_.is_container:
            func(path, self)
            return

        if visit_container:
            func(path, self)

        for key, entry in self._entries_.items():
            entry._walk_(path + (key, ), func, visit_container=visit_container)

    @classmethod
    def _parse_attributes_(cls, ns, attributes):
        pass

    def _update_value_(self, obj, *, entry_name=None, action="update"):
        assert action in ("update", "merge")

        if entry_name is None:
            host = self
        else:
            assert self._meta_.is_container

            if entry_name not in self._entries_:
                if not self._meta_.attributes.writable:
                    raise AttributeError(
                        f"Entry {entry_name!r} not found on container {self.dotted_path()!r}"
                    )

                host = self
                obj = {entry_name: obj}
                action = "merge"
            else:
                host = self._entries_[entry_name]

        if self._finalized_ and not host._meta_.attributes.writable:
            raise AttributeError(f"Cannot update read-only entry {host.dotted_path()!r}")

        if host._meta_.is_container:
            if not isinstance(obj, dict):
                raise TypeError(
                    f"Expect value to be a dict for container entry {host.dotted_path()!r},"
                    f" got {type(obj)!r}"
                )

            extra_entries = set(obj) - set(host._entries_)
            if not host._meta_.attributes.writable and extra_entries:
                verbose_extra_entries = ", ".join(map("{!r}".format, extra_entries))
                raise AttributeError(
                    f"Adding extra entries {verbose_extra_entries} to "
                    f"read-only container {host.dotted_path()!r} is forbidden"
                )

            if host._meta_.attributes.writable and action == "update":
                host._entries_.clear()
                host._alias_entries_.clear()

            for name, value in obj.items():
                if name in host._entries_:
                    host._entries_[name]._update_value_(value, action=action)
                else:
                    entry = host._add_entry_(name, value, attributes="writable")
                    if host._finalized_:
                        entry.finalize()
        else:
            if not typing.checkT(obj, host._meta_.type):
                raise TypeError(
                    f"Cannot update {host._meta_.type!r} type entry {host.dotted_path()!r}"
                    f" with value {obj!r}"
                )

            host._value_ = proxy(
                typing.cast(obj, host._meta_.type, check=False),
                T=host._meta_.type,
                mutable=host._mutable_,
                host=host,
            )

    @property
    def _mutable_(self):
        return not self._finalized_ or self._meta_.attributes.writable

    def dotted_path(self):
        entry = self
        paths = []
        while True:
            parent = entry._parent_() if entry._parent_ is not None else None
            if parent is None:
                break
            for k, v in parent._entries_.items():
                if v is entry:
                    paths.append(k)
                    break
            entry = parent

        return ".".join(reversed(paths))

    def has_entry(self, name):
        return name in set(self._entries_) | set(self._alias_entries_)

    def entry(self, name, node):
        assert name not in self._entries_, f"Entry name {name!r} already exists"

        self._add_entry_(name, node)
        return self

    def finalize(self):
        if not self._meta_.is_container:
            self._finalized_ = True
            if hasattr(self._value_, "mutable"):
                self._value_.mutable(self._meta_.attributes.writable)
            return self

        if self._finalized_:
            return self

        self._check_alias_()
        self._finalized_ = True
        for entry in self._entries_.values():
            entry.finalize()

        return self

    def alias(self, name: str, target: str):
        self._check_finalized_("create alias", False)
        self._check_is_container_("create alias", True)

        assert name.isidentifier(), \
            f"Alias name should be valid Python identifier, got {name!r}"
        assert target.isidentifier(), \
            f"Alias target should be valid Python identifier, got {target!r}"

        self._alias_entries_[name] = target
        return self

    def to_str(self, level=0, indent_size=2):
        if not self._meta_.is_container:
            return "({}) {}".format(typing.strT(self._meta_.type), self._value_)

        indent = " " * (level * indent_size)
        retstr = ""
        for key, entry in sorted(self._entries_.items(), key=lambda x: x[1]._meta_.is_container):
            retstr += f"{indent}{key}:"
            content = entry.to_str(level + 1, indent_size)
            if entry._meta_.is_container:
                retstr += f"\n{content}"
            else:
                retstr += f" {content}\n"
        for src, target in sorted(self._alias_entries_.items(), key=lambda x: x[0]):
            retstr += f"{src} -> {target}\n"

        return retstr

    def value_by_path(self, path: str, default=AttributeError):
        node = self
        for part in path.split("."):
            if not node.has_entry(part) and default is not AttributeError:
                return default
            node = getattr(node, part)
        return node

    def value_dict(self):
        if not self._meta_.is_container:
            if hasattr(self._value_, "as_primitive"):
                return self._value_.as_primitive()
            return self._value_

        dct = {}
        for name, child_node in self._entries_.items():
            dct[name] = child_node.value_dict()

        return dct

    def type_dict(self):
        if not self._meta_.is_container:
            return self._meta_.type

        dct = {}
        for name, child_node in self._entries_.items():
            dct[name] = child_node.type_dict()

        return dct

    def merge_from_dict(self, dct):
        self._update_value_(dct, action="merge")
        return self

    def merge_from_file(self, filename: str):
        dct = load_yaml_with_base(filename, caller_level=-2)
        self.merge_from_dict(dct)
        return self

    def dump(self, output):
        dump_yaml(self.value_dict(), output)
        return self

    def _merge_from_directives_(self, directives, *, ext_syntax=True):
        def _attrsetter(obj: SchemeNode, key, value):
            obj._entries_[key]._update_value_(value)

        def _attrchecker(obj: SchemeNode, key):
            return key in obj._entries_

        for directive, value in directives:
            accessor.modify(self, directive, value, ext_syntax, _attrsetter, _attrchecker)

        return self

    @classmethod
    def from_class(cls, singleton=False):
        def _decorator(template):
            return _SchemeBuilder(cls, template, singleton=singleton)

        if isinstance(singleton, bool):
            return _decorator
        template = singleton
        return _SchemeBuilder(cls, template)

    @staticmethod
    def writable(klass):
        klass.__writable__ = True
        return klass

    w = writable

    @classmethod
    def _handle_singleton_(cls, instance):
        pass


class _SchemeBuilder:
    __slots__ = ("scheme_class", "template", "singleton", "__instance__")

    def __init__(self, scheme_class, template, singleton=False):
        self.scheme_class = scheme_class
        self.template = template
        self.singleton = singleton
        self.__instance__ = None

    def __repr__(self):
        return f"<{self.scheme_class.__name__} Builder>"

    def __call__(self):
        if self.singleton:
            if self.__instance__ is None:
                self.__instance__ = self._parse_(self.scheme_class, self.template)
                self.scheme_class._handle_singleton_(self.__instance__)
            return self.__instance__
        return self._parse_(self.scheme_class, self.template)

    def _parse_(self, scheme_class, template):
        return self._build_(scheme_class, template)

    def _build_(self, scheme_class, template):
        entries = collections.defaultdict(dict)
        alias_entries = {}

        if getattr(template, "__writable__", False):
            attributes = ["writable"]
        else:
            attributes = []
        node = scheme_class(is_container=True, attributes=attributes)

        for name, default in self._get_entryname_default_pairs_(template):
            if inspect.isclass(default):
                default = self._build_(scheme_class, default)
                entries[name]["is_container"] = True

            entries[name]["default"] = default

        for name, annotation in getattr(template, "__annotations__", {}).items():
            T, attributes, alias = self._parse_annotation_(annotation)

            if alias is not None:
                alias_entries[name] = alias
            else:
                entries[name]["type_"] = T
                entries[name]["attributes"] = attributes

        for name, kwargs in entries.items():
            child_node = (
                kwargs["default"] if kwargs.get("is_container") else scheme_class(**kwargs)
            )
            node.entry(name, child_node)
        for name, alias in alias_entries.items():
            node.alias(name, alias)

        return node

    def _get_entryname_default_pairs_(self, template):
        return [
            (name, value) for name, value in inspect.getmembers(template)
            if not name.startswith("__")
        ]

    def _parse_annotation_(self, annotations):
        if isinstance(annotations, str):
            return None, None, annotations
        elif typing.is_acceptableT(annotations):
            return annotations, None, None
        elif isinstance(annotations, list):
            assert len(annotations) > 0
        else:
            raise TypeError(f"Cannot parse annotations {annotations!r}")

        T = None
        if typing.is_acceptableT(annotations[0]):
            T = annotations[0]
            attributes = annotations[1:]
        else:
            attributes = annotations[:]

        return T, attributes, None
