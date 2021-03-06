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

    __slots__ = ["attrs", "type", "is_container"]

    def __init__(self, T=None, attrs=None, is_container=False):
        self.type = T
        self.attrs = attrs
        self.is_container = is_container

    def __eq__(self, other):
        assert isinstance(other, NodeMeta)
        return all(getattr(self, name) == getattr(other, name) for name in self.__slots__)


class _AttributeSlots:
    def __eq__(self, other):
        assert isinstance(other, _AttributeSlots)
        return self.__dict__ == other.__dict__


class SchemaNode:

    __slots__ = [
        "_meta_",
        "_value_",
        "_alias_entries_",
        "_entries_",
        "_frozen_",
        "_parent_",
        "__weakref__",
    ]

    @classmethod
    def new_from_primitive(cls, value: Any, parent=None, attrs=None):

        if isinstance(value, cls):
            if parent is not None:
                value._parent_ = weakref.ref(parent)
            return value

        if isinstance(value, dict):
            result = cls(attrs=attrs, parent=parent)
            for k, v in value.items():
                result.entry(
                    k,
                    cls.new_from_primitive(value=v, parent=result, attrs=attrs),
                )
        else:
            result = cls(default=value, parent=parent, attrs=attrs)

        return result

    def __reduce__(self):
        meta_dict = {}
        alias_dict = {}

        def _visitor(path, node):
            meta_dict[path] = node._meta_
            if node._meta_.is_container:
                alias_dict[path] = node._alias_entries_

        self._walk_((), _visitor, visit_container=True)
        return (self._reconstruct_, (self.value_dict(), meta_dict, alias_dict, self._frozen_))

    @classmethod
    def _reconstruct_(cls, value_dict, meta_dict, alias_dict, frozen):
        def _build(value, path, parent):
            meta = meta_dict[path]
            if isinstance(value, dict):
                result = cls(parent=parent, meta=meta)
                result._alias_entries_ = alias_dict[path]
                for k, v in value.items():
                    result.entry(k, _build(v, path + (k, ), result))
            else:
                result = cls(default=value, meta=meta)

            return result

        result = _build(value_dict, (), None)
        if frozen:
            result.freeze()

        return result

    @staticmethod
    def _infer_(T, value):
        assert value is not None or T is not None, \
            "At least one of `T` or `default` should be provided"

        if value is None:
            final_type = T
        elif T is None:
            final_type = typing.inferT(value)
        else:
            assert typing.checkT(value, T), \
                f"Value {value!r} is incompatible with type {T!r}"
            final_type = T

        typing.is_acceptableT(final_type, raise_exc=True)
        if value is None:
            value = typing.get_default_value(final_type)

        return final_type, value

    def __init__(
        self,
        parent=None,
        default=None,
        T=None,
        attrs=None,
        meta=None,
    ):
        is_container = default is None and T is None
        if not is_container:
            if meta is None:
                final_type, default = self._infer_(T, default)
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
            attrs = self.__class__.__parse_attrs__(attrs)
            self._meta_ = NodeMeta(T=final_type, attrs=attrs, is_container=is_container)
        else:
            self._meta_ = meta
        self._parent_ = weakref.ref(parent) if parent is not None else None

        self._frozen_ = False

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

        if any(name.endswith(x) for x in SchemaNode.__slots__):
            object.__setattr__(self, name, value)
            return

        self._check_is_container_("update attribute", True)

        if name in self._alias_entries_:
            name = self._alias_entries_[name]

        self._update_value_(value, entry_name=name, action="update")

    __setitem__ = __setattr__

    def __str__(self):
        return self.to_str(level=0)

    def _check_frozen_(self, action: str, value: bool):
        if self._frozen_ != value:
            prep = "before" if value else "after"
            raise RuntimeError(f"Cannot {action} {prep} the object is frozen")

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

    def _add_entry_(self, name, value, attrs=None):

        if name in dir(self):
            raise RuntimeError(f'Cannot use preserved name {name!r} as entry.')

        node = self.new_from_primitive(value, parent=self, attrs=attrs)
        self._entries_[name] = node
        return node

    @classmethod
    def __parse_attrs__(cls, attrs):
        ns = _AttributeSlots()

        if attrs is None:
            attrs = []

        if isinstance(attrs, str):
            attrs = attrs.split()

        ns.writable = False
        cls._init_attrs_(ns)
        bad_attrs = []
        for attr in attrs:
            if attr.lower() in ("w", "writable"):
                ns.writable = True
            elif not cls._parse_attr_(ns, attr):
                bad_attrs.append(attr)

        if bad_attrs:
            raise ValueError(f"Cannot parse attrs {bad_attrs!r}")

        return ns

    @classmethod
    def _init_attrs_(cls, ns):
        pass

    @classmethod
    def _parse_attr_(cls, ns, attr):
        return False

    def _walk_(self, path, func, *, visit_container=False):
        if not self._meta_.is_container:
            func(path, self)
            return

        if visit_container:
            func(path, self)

        for key, entry in self._entries_.items():
            entry._walk_(path + (key, ), func, visit_container=visit_container)

    def _update_value_(self, obj, *, entry_name=None, action="update"):
        assert action in ("update", "merge")

        if entry_name is None:
            host = self
        else:
            assert self._meta_.is_container

            if entry_name not in self._entries_:
                if not self._meta_.attrs.writable:
                    raise AttributeError(
                        f"Entry {entry_name!r} not found on container {self.dotted_path()!r}"
                    )

                host = self
                obj = {entry_name: obj}
                action = "merge"
            else:
                host = self._entries_[entry_name]

        if self._frozen_ and not host._meta_.attrs.writable:
            raise AttributeError(f"Cannot update read-only entry {host.dotted_path()!r}")

        if host._meta_.is_container:
            if not isinstance(obj, dict):
                raise TypeError(
                    f"Expect value to be a dict for container entry {host.dotted_path()!r},"
                    f" got {type(obj)!r}"
                )

            extra_entries = set(obj) - set(host._entries_)
            if not host._meta_.attrs.writable and extra_entries:
                verbose_extra_entries = ", ".join(map("{!r}".format, extra_entries))
                raise AttributeError(
                    f"Adding extra entries {verbose_extra_entries} to "
                    f"read-only container {host.dotted_path()!r} is forbidden"
                )

            if host._meta_.attrs.writable and action == "update":
                host._entries_.clear()
                host._alias_entries_.clear()

            for name, value in obj.items():
                if name in host._entries_:
                    host._entries_[name]._update_value_(value, action=action)
                else:
                    entry = host._add_entry_(name, value, attrs="writable")
                    if host._frozen_:
                        entry.freeze()
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
        return not self._frozen_ or self._meta_.attrs.writable

    def equal(self, other, *, strict=False):
        assert isinstance(other, self.__class__)

        def _visitor(node: SchemaNode, other_node: SchemaNode):
            if other_node is None:
                return False

            ret = (
                node._meta_.type == other_node._meta_.type
                and node._meta_.is_container == other_node._meta_.is_container
                and node._frozen_ == other_node._frozen_
            )
            if strict:
                ret = ret and node._meta_.attrs == other_node._meta_.attrs
            if not ret:
                return False

            if node._meta_.is_container:
                if strict:
                    ret = ret and node._alias_entries_ == other_node._alias_entries_
                if not ret:
                    return False

                for name, entry in node._entries_.items():
                    other_entry = other_node._entries_.get(name, None)
                    if not _visitor(entry, other_entry):
                        return False

                return True
            else:
                return node._value_ == other_node._value_

        return _visitor(self, other)

    def __eq__(self, other):
        return self.equal(other, strict=True)

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

    def entry(self, name, value=None, T=None, attrs=None):
        assert name not in self._entries_, f"Entry name {name!r} already exists"

        if not isinstance(value, self.__class__):
            value = self.__class__(default=value, T=T, attrs=attrs)
        self._add_entry_(name, value)
        return self

    def freeze(self):
        if not self._meta_.is_container:
            self._frozen_ = True
            if hasattr(self._value_, "mutable"):
                self._value_.mutable(self._meta_.attrs.writable)
            return self

        if self._frozen_:
            return self

        self._check_alias_()
        self._frozen_ = True
        for entry in self._entries_.values():
            entry.freeze()

        return self

    def alias(self, name: str, target: str):
        self._check_frozen_("create alias", False)
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
        def _attrsetter(obj: SchemaNode, key, value):
            obj._entries_[key]._update_value_(value)

        def _attrchecker(obj: SchemaNode, key):
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
    __slots__ = ("schema_class", "template", "singleton", "__instance__")

    def __init__(self, schema_class, template, singleton=False):
        self.schema_class = schema_class
        self.template = template
        self.singleton = singleton
        self.__instance__ = None

    def __repr__(self):
        return f"<{self.schema_class.__name__} Builder>"

    def __call__(self):
        if self.singleton:
            if self.__instance__ is None:
                self.__instance__ = self._parse_(self.schema_class, self.template)
                self.schema_class._handle_singleton_(self.__instance__)
            return self.__instance__
        return self._parse_(self.schema_class, self.template)

    def _parse_(self, schema_class, template):
        return self._build_(schema_class, template)

    def _build_(self, schema_class, template):
        entries = collections.defaultdict(dict)
        alias_entries = {}

        if getattr(template, "__writable__", False):
            attrs = ["writable"]
        else:
            attrs = []
        node = schema_class(attrs=attrs)

        for name, default in self._get_entryname_default_pairs_(template):
            if inspect.isclass(default):
                default = self._build_(schema_class, default)
                entries[name]["is_container"] = True

            entries[name]["default"] = default

        for name, annotation in getattr(template, "__annotations__", {}).items():
            T, attrs, alias = self._parse_annotation_(annotation)

            if alias is not None:
                alias_entries[name] = alias
            else:
                entries[name]["T"] = T
                entries[name]["attrs"] = attrs

        for name, kwargs in entries.items():
            child_node = (
                kwargs["default"] if kwargs.get("is_container") else schema_class(**kwargs)
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
            attrs = annotations[1:]
        else:
            attrs = annotations[:]

        return T, attrs, None
