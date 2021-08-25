#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Base class for other codified attrs classes providing class methods for read and cast and instance method for write
"""
from __future__ import annotations

import abc
import functools
import json
import os
import pathlib
import typing
import uuid

import attr

__all__ = ['RepoCachedAttrs', 'attr']
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


class RepoCached(abc.ABCMeta):
    __types__: typing.Dict[str, RepoCached] = {}
    __instances__: typing.Dict[str, object] = {}

    def __new__(mcs, name, bases, dct):
        RepoCached.__types__[name] = t = super().__new__(mcs, name, bases, dct)
        return t

    def __object_hook__(cls: typing.Type[T], d: dict) -> T:
        fields = {a.name for a in attr.fields(cls) if a.init}
        return cls(**{k: v for k, v in d.items() if k in fields})

    @staticmethod
    def read(obj_id: str) -> T:
        if obj_id not in RepoCached.__instances__:
            with open(__get_path__(obj_id)) as in_file:
                return json.load(fp=in_file, object_hook=lambda d: RepoCached.__types__[d['type']].__object_hook__(d))
        return RepoCached.__instances__[obj_id]

    def cast(cls: typing.Type[T], d: tuple[typing.Union[T, str, dict, list, tuple], ...]) -> tuple[T, ...]:
        def c(o):
            if isinstance(o, cls):
                return o
            if isinstance(o, str):
                return cls.read(o)
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

    def __attrs_post_init__(self):
        if self.id is None:
            id_name = self.__class__.__name__.lower()
            id_content = self.__dict__.get(id_name, '')
            if isinstance(id_content, tuple):
                id_content = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(sorted(id_content))))
            object.__setattr__(self, 'id', f'{id_name}_{id_content}')
        RepoCached.__instances__[self.id] = self

    @type.default
    def __type_default__(self) -> str:
        return self.__class__.__name__

    def write(self):
        with open(__get_path__(self.id), 'w') as out_file:
            json.dump(obj=attr.asdict(self, filter=lambda a, v: a.repr), fp=out_file, indent=4)
