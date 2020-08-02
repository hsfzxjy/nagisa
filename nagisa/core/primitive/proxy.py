import sys
import types
import weakref

from nagisa.core.functools import wraps
from nagisa.core.misc import naming
from . import typing

__all__ = ['proxy']


def proxy(obj, *, mutable: bool = False, T=None, host=None):
    if isinstance(obj.__class__, ProxyMeta):
        return obj

    if isinstance(obj, list):
        return SwitchableList(obj, T=T, host=host, mutable=mutable)

    return obj


def _not_implemented(self, *args, **kwargs):
    raise NotImplementedError


class ProxyMeta(type):
    def __new__(mcls, name, bases, namespace):
        proxy_methods = namespace.pop('__proxy_methods__', [])
        proxy_class = namespace.pop('__proxy_class__', None)
        if proxy_class is not None:
            bases = bases + (proxy_class, )

        for method_names, make_method in proxy_methods:
            for method_name in method_names:
                method = getattr(list, method_name)
                namespace[method_name] = wraps(method)(make_method(method))
        return super().__new__(mcls, name, bases, namespace)


class ProxyBase(metaclass=ProxyMeta):
    ...


class SwitchableList(ProxyBase):
    def __init__(self, lstobj: list, T, *, host=None, mutable=False):
        self.__lstobj__ = lstobj
        self.__host__ = weakref.ref(host) if host is not None else None
        self.__mutable__ = mutable
        self.T = T
        self.elem_T = typing._elem(T)
        self.T_str = typing.stringify_type(T)

    def as_primitive(self):
        return self.__lstobj__.copy()

    def mutable(self, value):
        if self.__host__ is not None:
            host = self.__host__()

            if host is None:
                raise RuntimeError('Host has been freed')

            caller_frame_locals = sys._getframe(1).f_locals
            if caller_frame_locals.get('self', None) is not host:
                raise RuntimeError(
                    f'`mutable()` should be called within method of {host!r}'
                )

        self.__mutable__ = value

    def _ensure_mutable(self):
        if not self.__mutable__:
            raise RuntimeError('Cannot perform this action on immutable list')

    @wraps(list.append)
    def append(self, object):
        self._ensure_mutable()
        if not typing.check_type(object, self.elem_T):
            raise TypeError(
                f'Cannot append {object!r} to {self.T_str} type list'
            )

        self.__lstobj__.append(object)

    @wraps(list.extend)
    def extend(self, iterable):
        self._ensure_mutable()
        if not typing.check_type(iterable, self.T):
            raise TypeError(
                f'Cannot extend {iterable!r} to {self.T_str} type list'
            )

        self.__lstobj__.extend(iterable)

    @wraps(list.insert)
    def insert(self, index, object):
        self._ensure_mutable()
        if not typing.check_type(object, self.elem_T):
            raise TypeError(
                f'Cannot insert {object!r} into {self.T_str} type list'
            )

        self.__lstobj__.insert(index, object)

    def _make_method(method):
        def _method(self, *args, **kwargs):
            return method(self.__lstobj__, *args, **kwargs)

        return _method

    def _make_mutablility_check_method(method):
        def _method(self, *args, **kwargs):
            self._ensure_mutable()
            return method(self.__lstobj__, *args, **kwargs)

        return _method

    __proxy_class__ = list
    __proxy_methods__ = [
        [
            [
                '__delitem__',
                '__iadd__',
                '__imul__',
                '__setitem__',
                'clear',
                'pop',
                'reverse',
                'sort',
            ], _make_mutablility_check_method
        ],
        [
            [
                '__add__',
                '__contains__',
                '__eq__',
                '__format__',
                '__ge__',
                '__getitem__',
                '__gt__',
                # '__hash__',
                '__iter__',
                '__le__',
                '__len__',
                '__lt__',
                '__mul__',
                '__ne__',
                # '__reduce__',
                # '__reduce_ex__',
                '__repr__',
                '__reversed__',
                '__rmul__',
                '__sizeof__',
                '__str__',
                'copy',
                'count',
                'index',
            ],
            _make_method
        ]
    ]

    del _make_method, _make_mutablility_check_method