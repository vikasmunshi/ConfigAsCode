#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Base class for other codified attrs classes providing a class method for read and an instance method for write
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

T = typing.TypeVar('T')
is_optional_str = attr.validators.optional(attr.validators.instance_of(str))

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
    __types__: typing.Dict[str, type] = {}
    __instances__: typing.Dict[str, object] = {}

    def __new__(mcs, name, bases, dct):
        RepoCached.__types__[name] = t = super().__new__(mcs, name, bases, dct)
        return t

    def __object_hook__(cls: typing.Type[T], d: dict) -> T:
        fields = {a.name for a in attr.fields(cls) if a.init}
        return cls.__types__.get(d.get('type'), dict)(**{k: v for k, v in d.items() if k in fields})

    def read(cls: typing.Type[T], obj_id: str) -> T:
        if obj_id not in RepoCached.__instances__:
            with open(__get_path__(obj_id)) as in_file:
                return json.load(fp=in_file, object_hook=cls.__object_hook__)
        return RepoCached.__instances__[obj_id]


@attr.s(frozen=True, kw_only=True)
class RepoCachedAttrs(metaclass=RepoCached):
    id = attr.ib(type=typing.Optional[str], cmp=False, default=None, validator=is_optional_str)
    type = attr.ib(type=str, init=False)
    doc = attr.ib(type=typing.Optional[str], cmp=False, default=None, validator=is_optional_str)

    def __attrs_post_init__(self):
        if self.id is None:
            obj_dict = attr.asdict(self, filter=lambda a, v: a.eq and v is not None)
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(sorted(str(obj_dict)))))
            object.__setattr__(self, 'id', uid)
        RepoCached.__instances__[self.id] = self

    @type.default
    def __type_default__(self) -> str:
        return self.__class__.__name__

    @functools.cached_property
    def as_dict(self):
        return attr.asdict(self, filter=lambda a, v: a.repr and v is not None)

    def write(self):
        with open(__get_path__(self.id), 'w') as out_file:
            json.dump(obj=self.as_dict, fp=out_file, indent=4)
