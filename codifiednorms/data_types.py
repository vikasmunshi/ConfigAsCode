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
import typing

import attr

T = typing.TypeVar('T', bound='Base')


@attr.s(frozen=True, kw_only=True)
class Repo:
    root = attr.ib(type=pathlib.Path)

    @root.default
    def default_root(self):
        return pathlib.Path(os.getcwd().split('repository')[0]).joinpath('repository')

    def path(self, identifier: str) -> pathlib.Path:
        identifier = identifier.split(':', 1)[1]
        return self.root.joinpath(identifier.replace('.', '/')).with_suffix('.json')

    def new(self, name: str) -> str:
        path = pathlib.Path(os.getcwd()).relative_to(self.root).joinpath(f'{name}_{str(int(time.time()))}')
        return f'id:{str(path).replace("/", ".")}'


repo = Repo()


class Specials(str):
    pass


AllValues = Specials('Values.AllValues')
NoValues = Specials('Values.NoValues')


# noinspection PyArgumentList
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
    def cast(cls: typing.Type[T], data: typing.Union[T, typing.Iterable, bool, int, str]) \
            -> typing.Optional[typing.Union[T, typing.Tuple[T]]]:
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            if data.startswith('id:'):
                return cls.load(data)
            if data.startswith('Values.'):
                print('data', type(data), data)
                return globals()[data.split('.')[1]]
        if isinstance(data, (list, tuple, set)):
            return tuple(cls.cast(d) for d in data)
        if isinstance(data, dict):
            return cls(**data)
        if isinstance(data, (str, int, bool)):
            return cls(data)


@attr.s(frozen=True)
class Param(Serializable):
    name = attr.ib(type=str, validator=attr.validators.instance_of(str))


@attr.s(frozen=True)
class Target(Param):
    url = attr.ib(type=str, default=None)

    @url.validator
    def validator_url(self, attribute, value):
        if not (value is None or (isinstance(value, str) and value.startswith('https://'))):
            raise ValueError(f'{value} is not a valid {attribute.name}')


@attr.s(frozen=True)
class Value(Serializable):
    value = attr.ib(type=typing.Union[bool, int, str],
                    validator=attr.validators.instance_of((bool, int, str)))

    def __bool__(self) -> bool:
        return bool(self.value)


@attr.s(frozen=True)
class Values(Serializable):
    values = attr.ib(type=typing.Union[typing.Tuple[Value, ...], Specials],
                     converter=Value.cast, factory=tuple,
                     validator=attr.validators.instance_of((tuple, Specials)))

    def __bool__(self) -> bool:
        return bool(self.values)

    def __contains__(self, item: typing.Union[Value, bool, int, str]) -> bool:
        if self.values is AllValues:
            return True
        if self.values is NoValues:
            return False
        return item.value in self.values if isinstance(item, Value) else item in self.values

    def __iter__(self) -> typing.Generator[typing.Union[bool, int, str], None, None]:
        if isinstance(self.values, Specials):
            yield from tuple()
        yield from self.values

    def __add__(self, other: Values) -> typing.Union[Values, Specials]:
        """ add values, return values that are in either i.e. union of sets"""
        if self.values is AllValues or other.values is AllValues:
            return AllValues
        if self.values is NoValues:
            return other.values
        if other.values is NoValues:
            return self.values
        values = self.values + tuple(v for v in other.values if v not in self.values)
        return Values(values=values, doc=f'{self.doc} (+) {other.doc}')

    def __sub__(self, other: Values) -> typing.Union[Values, Specials]:
        """ remove values from self that are also in other"""
        if other.values is AllValues or self.values is NoValues:
            return NoValues
        if other.values is NoValues or self.values is AllValues:
            return self.values
        values = tuple(v for v in self.values if v not in other.values)
        return Values(values=values, doc=f'{self.doc} (-) {other.doc}')

    def __mod__(self, other: Values) -> typing.Union[Values, Specials]:
        """ return values that are in both i.e. intersection of sets"""
        if self.values is AllValues:
            return other.values
        if other.values is AllValues:
            return self.values
        if self.values is NoValues or other.values is NoValues:
            return NoValues
        values = tuple(v for v in self.values if v in other.values)
        return Values(values=values, doc=f'{self.doc} (%) {other.doc}')


@attr.s(frozen=True)
class ParamPolicy(Serializable):
    target = attr.ib(type=Target, converter=Target.cast, validator=attr.validators.instance_of(Target))
    param = attr.ib(type=Param, converter=Param.cast, validator=attr.validators.instance_of(Param))
    allowed = attr.ib(type=Values, converter=Values.cast, default=Values(AllValues),
                      validator=attr.validators.instance_of((Values, Specials)))
    denied = attr.ib(type=Values, converter=Values.cast, default=Values(NoValues),
                     validator=attr.validators.instance_of((Values, Specials)))

    def __add__(self, other: ParamPolicy) -> ParamPolicy:
        if self.target == other.target and self.param == other.param:
            allowed = self.allowed % other.allowed
            denied = self.denied + other.denied
            doc = f'{self.doc} (+) {other.doc}'
            return ParamPolicy(target=self.target, param=self.param, doc=doc, allowed=allowed, denied=denied)
        raise NotImplemented

    def __sub__(self, other: ParamPolicy) -> ParamPolicy:
        if self.target == other.target and self.param == other.param:
            allowed = self.allowed + other.allowed
            denied = self.denied - other.allowed
            doc = f'{self.doc} (-) {other.doc}'
            return ParamPolicy(target=self.target, param=self.param, doc=doc, allowed=allowed, denied=denied)
        raise NotImplemented


if __name__ == '__main__':
    print(p1 := Param('some_param'))
    print(v1 := Value('some value'))
    print(t1 := Target('some target', url='https://localhost'))
    # noinspection PyTypeChecker
    print(vany := Values('Values.AllValues'))
    # noinspection PyTypeChecker
    print(vnov := Values('Values.NoValues'))
    print(vany2 := Values.load('id:policies.test.values_1628881815'))
    print(v1 in vany, v1 in vnov)

    print(valuesx := Values(['val1', 'val2', 'val0'], id='id:policies.test.valuesx'))
    print('val1' in valuesx)
    print(Value('val0') in valuesx)
    print('check', valuex_str := valuesx.dumps())
    print(valuesx2 := Values.loads(valuex_str))
    print(valuesx + Values(['val2', 'val3']))
    print(valuesx % Values(['val2', 'val3']))
    print(valuesx - Values(['val2', 'val3']))
    valuesx.dump()

    print(parampolicyx := ParamPolicy(target=Target('some target'), param=('some param'),
                                      allowed='id:policies.test.valuesx',
                                      id='id:policies.test.parampolicyx'
                                      ))
    print(parampolicyx)
    parampolicyx.dump()
    parampolicyx2 = ParamPolicy.load(identifier='id:policies.test.parampolicyx')
    print(parampolicyx + parampolicyx2)
