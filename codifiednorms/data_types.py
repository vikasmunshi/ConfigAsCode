#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Python3 library to Manage Codified Norms and Config as Code
Class Serializable, Param, Value, Values, ParamPolicy
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import types
import typing

import attr

T = typing.TypeVar('T', bound='Base')
type_value = (set, bool, int, str)
TypeValue = typing.Optional[typing.Union[typing.Set[typing.Union[bool, int, str]], bool, int, str]]


@attr.s(frozen=True, kw_only=True)
class Repo:
    root = attr.ib(type=pathlib.Path,
                   factory=lambda: pathlib.Path(os.getcwd().split('repository')[0]).joinpath('repository'))

    def path(self, identifier: str) -> pathlib.Path:
        identifier = identifier.split(':', 1)[1]
        return self.root.joinpath(identifier.replace('.', '/')).with_suffix('.json')

    def new(self, name: str) -> str:
        path = pathlib.Path(os.getcwd()).relative_to(self.root).joinpath(f'{name}_{str(int(time.time()))}')
        return f'id:{str(path).replace("/", ".")}'


repo = Repo()


@attr.s(frozen=True, kw_only=True)
class Serializable:
    id = attr.ib(type=str)
    type = attr.ib(type=str, eq=False, init=False)
    doc = attr.ib(type=str, eq=False, validator=attr.validators.instance_of(str))

    @id.default
    def default_id(self) -> str:
        return repo.new(name=self.__class__.__name__.lower())

    @doc.default
    def default_doc(self) -> str:
        return f'replace with doc for {self.__class__.__name__.lower()}'

    @type.default
    def default_type(self) -> str:
        return self.__class__.__name__

    def dump(self):
        with open(repo.path(self.id), 'w') as out_file:
            out_file.write(self.dumps())

    def dumps(self) -> str:
        return json.dumps(obj=attr.asdict(self), indent=4)

    @classmethod
    def load(cls: typing.Type[T], identifier: str) -> T:
        with open(repo.path(identifier)) as in_file:
            return cls.loads(in_file.read())

    @classmethod
    def loads(cls: typing.Type[T], data: str) -> T:
        return json.loads(s=data, object_hook=lambda d: globals().get(d.pop('type'), lambda **kw: kw)(**d))

    @classmethod
    def cast(cls: typing.Type[T], data: typing.Union[T, typing.Iterable, str], as_set: bool = False) \
            -> typing.Optional[typing.Union[typing.Set[T], T]]:
        if data is None or not data:
            return set() if as_set else cls()
        if isinstance(data, cls):
            return set(data) if as_set else data
        if isinstance(data, str) and data.startswith('id:'):
            return cls.load(data)
        if as_set and isinstance(data, (list, tuple, set)):
            return set(cls.cast(d) for d in data)
        args = (data,) if isinstance(data, str) else data if isinstance(data, (list, tuple, str)) else tuple()
        kwargs = data if isinstance(data, dict) else dict()
        return cls(*args, **kwargs)


@attr.s(frozen=True)
class Param(Serializable):
    name = attr.ib(type=str, validator=attr.validators.instance_of(str))


@attr.s(frozen=True)
class Target(Param):
    url = attr.ib(type=str, default=None,
                  validator=lambda i, a, v: v is None or (isinstance(v, str) and v.startswith('https://')))


@attr.s(frozen=True)
class Value(Serializable):
    value = attr.ib(type=TypeValue, validator=attr.validators.optional(attr.validators.instance_of(type_value)),
                    default=None)

    def __bool__(self) -> bool:
        return bool(self.value)

    def __add__(self, other: Value) -> Value:
        pass


@attr.s(frozen=True)
class Values(Serializable):
    values = attr.ib(type=typing.Set[Value], converter=lambda v: Value.cast(v, as_set=True), factory=set)

    def __bool__(self) -> bool:
        return bool(self.values)

    def __contains__(self, item: typing.Union[TypeValue, Value]) -> bool:
        return item.value in self.values if isinstance(item, Value) else item in self.values

    def __iter__(self) -> typing.Generator[TypeValue, None, None]:
        yield from self.values

    def __add__(self, other: Values) -> Values:
        return Values(values=self.values.union(other.values), doc=f'{self.doc} (+) {other.doc}')

    def __mul__(self, other: Values) -> Values:
        return Values(values=self.values.intersection(other.values), doc=f'{self.doc} (*) {other.doc}') \
            if other else self

    def __sub__(self, other: Values) -> Values:
        return Values(values=self.values - other.values, doc=f'{self.doc} (-) {other.doc}')

    def union(self, other: Values) -> Values:
        return self + other

    def intersection(self, other: Values) -> Values:
        return self * other

    def remove(self, other: Values) -> Values:
        return self - other


@attr.s(frozen=True)
class ParamPolicy(Serializable):
    target = attr.ib(type=Target, converter=Target.cast)
    param = attr.ib(type=Param, converter=Param.cast)
    allowed = attr.ib(type=Values, converter=Values.cast, factory=Values)
    denied = attr.ib(type=Values, converter=Values.cast, factory=Values)
    enforced = attr.ib(type=Value, converter=Value.cast, factory=Value)

    def __add__(self, other: ParamPolicy) -> ParamPolicy:
        if self.target == other.target and self.param == other.param:
            if self.enforced and other.enforced and self.enforced != other.enforced:
                raise ValueError(f'cannot enforce {self.enforced} and {other.enforced} for {self.param}')
            allowed = self.allowed.intersection(other.allowed).remove(other.denied)
            denied = self.denied.union(other.denied)
            enforced = self.enforced if self.enforced else other.enforced
            doc = f'{self.doc} (+) {other.doc}'
            return ParamPolicy(target=self.target, param=self.param, doc=doc,
                               allowed=allowed, denied=denied, enforced=enforced)
        raise NotImplemented

    def __sub__(self, other: ParamPolicy) -> ParamPolicy:
        if self.target == other.target and self.param == other.param:
            if other.enforced or other.denied:
                raise ValueError(f'trying to use policy {other.id} as an exemption is not possible')
            allowed = self.allowed + other.allowed
            denied = self.denied - other.allowed
            enforced = self.enforced
            doc = f'{self.doc} (-) {other.doc}'
            return ParamPolicy(target=self.target, param=self.param, doc=doc,
                               allowed=allowed, denied=denied, enforced=enforced)
        raise NotImplemented


if __name__ == '__main__':
    print(Param('some_param'))
    print(Value('some value'))
    print(Target('some target'))
    print(valuesx := Values(['val1', 'val2', 'val0'], id='id:policies.test.valuesx'))
    print('val1' in valuesx)
    print(Value('val0') in valuesx)
    print('check', valuex_str := valuesx.dumps())
    print(valuesx2 := Values.loads(valuex_str))
    print(valuesx + Values(['val2', 'val3']))
    print(valuesx * Values(['val2', 'val3']))
    print(valuesx - Values(['val2', 'val3']))
    valuesx.dump()

    print(parampolicyx := ParamPolicy(target=Target('some target'), param=('some param'),
                                      allowed='id:policies.test.valuesx',
                                      denied=[],
                                      id='id:policies.test.parampolicyx'
                                      ))
    print(parampolicyx)
    parampolicyx.dump()
    parampolicyx2 = ParamPolicy.load(identifier='id:policies.test.parampolicyx')
    print(parampolicyx + parampolicyx2)
