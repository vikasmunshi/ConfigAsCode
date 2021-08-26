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

__all__ = ['RepoCachedAttrs', 'Value', 'any_value', 'Values', 'all_values', 'no_values', 'Target']
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


@attr.s(frozen=True, cmp=False)
class Value(RepoCachedAttrs):
    value = attr.ib(type=typing.Optional[typing.Union[bool, int, str]],
                    validator=attr.validators.optional(attr.validators.instance_of((bool, int, str))))

    def __eq__(self: Value, other: Value) -> bool:
        if self is any_value or other is any_value:
            return True
        return self.value == other.value

    def __ne__(self: Value, other: Value) -> bool:
        if self is any_value or other is any_value:
            return False
        return self.value != other.value


any_value = Value(id='value~any', value=None, doc='special value that matches all values')


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


@attr.s(frozen=True)
class Target(RepoCachedAttrs):
    target = attr.ib(type=str, validator=is_instance_of(str))
    uri = attr.ib(type=str, cmp=False, default='', validator=is_optional_str)
    params = attr.ib(type=tuple[str, ...], default=(), converter=tuple, validator=is_instance_of(str))


@attr.s(frozen=True)
class Param(RepoCachedAttrs):
    param = attr.ib(type=str, validator=is_instance_of(str))
    target = attr.ib(type=Target, validator=is_instance_of(Target))


@attr.s(frozen=True)
class Policy(RepoCachedAttrs):
    policy = attr.ib(type=str, validator=is_instance_of(str))
    param = attr.ib(type=Param, validator=is_instance_of(Param))
    allowed = attr.ib(type=Values, default=all_values, validator=is_instance_of(Values))
    denied = attr.ib(type=Values, default=no_values, validator=is_instance_of(Values))

# @attr.s(frozen=True)
# class Target(Target):
#     params = attr.ib(type=tuple[Param, ...], default=(), validator=is_tuple_of(Param))
