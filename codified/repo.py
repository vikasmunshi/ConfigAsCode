#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Base class for other codified attrs classes providing class methods for read and cast and instance method for write
"""
from __future__ import annotations

import abc
import json
import os
import pathlib
import typing
import uuid

import attr

__all__ = ['RepoCachedAttrs', 'Value', 'Values', 'all_values', 'no_values', 'Policy', 'Param', 'Target']
Callable = typing.Callable
Any = typing.Any
T = typing.TypeVar('T')
is_instance_of = attr.validators.instance_of
is_optional_str = attr.validators.optional(is_instance_of(str))
is_tuple_of: Callable[[Any], None] = lambda t: attr.validators.deep_iterable(is_instance_of(t), is_instance_of(tuple))

__cwd__ = pathlib.Path(os.getcwd())
if __cwd__.stem == 'repository':
    __root__ = __cwd__
elif (r := __cwd__.joinpath('repository')).exists() and r.is_dir():
    __root__ = r
elif r := [p for p in __cwd__.parents if p.stem == 'repository']:
    __root__ = r[-1]
elif r := [rp for p in __cwd__.parents if (rp := p.joinpath('repository')).exists() and rp.is_dir()]:
    __root__ = r[-1]
else:
    __root__ = __cwd__


def __get_path__(obj_id: str) -> str:
    path = __root__.joinpath(obj_id.replace('.', '/')) if '.' in obj_id else __cwd__.joinpath(obj_id)
    path = path if path.exists() else path.with_suffix('.json')
    return str(path)


def __abs_id__(obj_id: str) -> str:
    if '.' in obj_id:
        return obj_id
    return str(__cwd__.joinpath(obj_id).relative_to(__root__)).replace('/', '.').replace('\\', '.')


class RepoCached(abc.ABCMeta):
    __types__: typing.Dict[str, RepoCached] = {}
    __instances__: typing.Dict[str, object] = {}

    def __new__(mcs, name, bases, dct):
        RepoCached.__types__[name] = t = super().__new__(mcs, name, bases, dct)
        return t

    def __object_hook__(cls: typing.Type[T], d: dict) -> T:
        try:
            return RepoCached.__instances__[d['id']]
        except KeyError:
            fields = {a.name for a in attr.fields(cls) if a.init}
            return cls(**{k: v for k, v in d.items() if k in fields})

    @staticmethod
    def read(obj_id: str) -> T:
        obj_id = __abs_id__(obj_id)
        if obj_id not in RepoCached.__instances__:
            with open(__get_path__(obj_id)) as in_file:
                return json.load(fp=in_file, object_hook=lambda d: RepoCached.__types__[d['type']].__object_hook__(d))
        return RepoCached.__instances__[obj_id]

    def cast(cls: typing.Type[T], d: tuple[typing.Union[T, str, dict, list, tuple], ...]) -> tuple[T, ...]:
        def c(o):
            if isinstance(o, cls):
                return o
            if isinstance(o, str):
                try:
                    return cls.read(o)
                except FileNotFoundError:
                    return cls(o)
            if isinstance(o, dict):
                return cls(**o)
            if isinstance(o, (list, tuple)):
                return cls(*o)
            return

        return tuple(v for obj in (d if isinstance(d, (list, tuple)) else (d,)) if isinstance(v := c(obj), cls))


@attr.s(frozen=True, kw_only=True)
class RepoCachedAttrs(metaclass=RepoCached):
    id = attr.ib(type=typing.Optional[str], cmp=False, default=None, validator=is_optional_str)
    type = attr.ib(type=str, init=False)
    doc = attr.ib(type=typing.Optional[str], cmp=False, default='', validator=is_instance_of(str))

    @type.default
    def __type_default__(self) -> str:
        return self.__class__.__name__

    def write(self):
        with open(__get_path__(self.id), 'w') as out_file:
            json.dump(obj=attr.asdict(self, filter=lambda a, v: a.repr), fp=out_file, indent=4)

    def __attrs_post_init__(self):
        if self.id is None or '~' not in self.id:
            id_name = self.__class__.__name__.lower()
            id_content = self.__dict__.get(id_name)
            if id_content is None:
                id_content = str(uuid.uuid5(uuid.NAMESPACE_DNS,
                                            str(sorted(str(attr.asdict(self, filter=lambda a, v: a.eq and a.init))))))
            if isinstance(id_content, tuple):
                id_content = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(sorted(id_content))))
            object.__setattr__(self, 'id', __abs_id__(f'{id_name}_{id_content}'))
        RepoCached.__instances__[self.id] = self


@attr.s(frozen=True)
class Value(RepoCachedAttrs):
    value = attr.ib(type=typing.Optional[typing.Union[bool, int, str]],
                    validator=attr.validators.optional(attr.validators.instance_of((bool, int, str))))

    def __matmul__(self: Value, policy: Policy) -> bool:
        """ value @ policy"""
        return self.value in policy.allowed and self.value not in policy.denied


@attr.s(frozen=True)
class Values(RepoCachedAttrs):
    values = attr.ib(type=typing.Tuple[Value, ...], converter=Value.cast, default=(), validator=is_tuple_of(Value))

    def __iter__(self):
        yield from self.values

    def __contains__(self, item: Value) -> bool:
        if self is all_values:
            return True
        return item.value in self.values


all_values = Values(id='values~all', doc='special values that contains all values')
no_values = Values(id='values~none', doc='empty list of values')


@attr.s(frozen=True, kw_only=True)
class Policy(RepoCachedAttrs):
    policy = attr.ib(type=str, default='deny-all', validator=is_instance_of(str))
    allowed = attr.ib(type=Values, default=no_values, converter=Value.cast, validator=is_instance_of(Values))
    denied = attr.ib(type=Values, default=all_values, converter=Value.cast, validator=is_instance_of(Values))

    def __matmul__(self: Policy, value: Value) -> bool:
        """ policy @ value """
        val = value.value if isinstance(value, Value) else value
        return val in self.allowed and val not in self.denied

    def __add__(self: Policy, other: Policy) -> Policy:
        """ p = p1 + p2 => for any value v: p @ v == (p1 + p2) @ v """
        if self.denied is all_values or other.denied is all_values:
            denied = all_values
        else:
            denied = self.denied + tuple(v for v in other.denied if v not in self.denied)
        if self.allowed is all_values or other.allowed is all_values:
            allowed = all_values
        else:
            allowed = tuple(v for v in self.allowed if v in other.allowed and v not in denied)
        return Policy(doc=f'policy {self.id} plus {other.id}:\n{self.doc}\n{other.doc}',
                      policy=f'{self.policy}+{other.policy}', allowed=allowed, denied=denied, )


@attr.s(frozen=True)
class Param(RepoCachedAttrs):
    param = attr.ib(type=str, validator=is_instance_of(str))
    policy = attr.ib(type=Policy, factory=Policy, validator=is_instance_of(Policy))


@attr.s(frozen=True)
class Target(RepoCachedAttrs):
    target = attr.ib(type=str, validator=is_instance_of(str))
    uri = attr.ib(type=str, cmp=False, default='', validator=is_instance_of(str))
    params = attr.ib(type=tuple[Param, ...], default=(), converter=Param.cast, validator=is_instance_of(Param))
