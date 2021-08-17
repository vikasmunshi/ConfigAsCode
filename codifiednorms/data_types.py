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
import re
import time
import typing

import attr

T = typing.TypeVar('T', bound='Base')
is_instance_of = attr.validators.instance_of


@attr.s(frozen=True, kw_only=True)
class Repo:
    root = attr.ib(type=pathlib.Path, validator=is_instance_of(pathlib.Path))
    repo_cache = attr.ib(type=dict, factory=dict, init=False)

    @root.default
    def root_default(self):
        return pathlib.Path(os.getcwd().split('repository', 1)[0]).joinpath('repository')

    @root.validator
    def root_validator(self, attribute, value):
        if not value.exists():
            raise ValueError(f'repository {attribute.name} {value} does not exist')
        if not value.is_dir():
            raise ValueError(f'repository {attribute.name} {value} is not a directory')

    def path(self, identifier: str) -> pathlib.Path:
        identifier = identifier.split(':', 1)[1]
        return self.root.joinpath(identifier.replace('.', '/')).with_suffix('.json')

    def is_valid_id(self, identifier: str) -> bool:
        if not identifier.startswith('id:'):
            return False
        if not self.root in self.path(identifier).parents:
            return False
        return True

    def new(self, name: str) -> str:
        path = pathlib.Path(os.getcwd()).relative_to(self.root).joinpath(f'{name}_{str(time.time())}')
        path = str(path).replace('/', '.').replace('\\', '.')
        return f'id:{path}'

    def read(self, identifier: str) -> str:
        try:
            with open(self.path(identifier), 'r') as in_file:
                return in_file.read()
        except FileNotFoundError:
            print(f'file {self.path(identifier)} does not exist')
            raise
        except IOError:
            print(f'file {self.path(identifier)} cannot be read')
            raise

    def write(self, identifier: str, s: str):
        with open(self.path(identifier), 'w') as out_file:
            out_file.write(s)

    def put(self, obj: Serializable):
        self.repo_cache[obj.id] = obj

    def get(self, identifier: str) -> Serializable:
        return self.repo_cache[identifier]

    @property
    def list(self) -> list[str, ...]:
        return list(self.repo_cache.keys())


repo = Repo()


class Specials(str):
    pass


AllValues = Specials('values:AllValues')
id_re = re.compile(r'id:[^\s)(=/*-+]*')
values_re = re.compile(r'values:[^\s)(=/*-+]*')
escape_colon_dot: typing.Callable[[str], str] = lambda key: key.replace(':', '_').replace('.', '_')


@attr.s(frozen=True, kw_only=True)
class Serializable:
    id = attr.ib(type=str, validator=is_instance_of(str))
    type = attr.ib(type=str, eq=False, init=False)
    doc = attr.ib(type=str, eq=False, validator=is_instance_of(str))

    def __attrs_post_init__(self):
        repo.put(obj=self)

    @id.default
    def id_default(self) -> str:
        return repo.new(name=self.__class__.__name__.lower())

    @id.validator
    def id_validator(self, attribute, value):
        if not repo.is_valid_id(identifier=value):
            raise ValueError(f'{value} id not a valid {attribute.name}')

    @type.default
    def type_default(self) -> str:
        return self.__class__.__name__

    @doc.default
    def doc_default(self) -> str:
        return f'doc for {self.__class__.__name__.lower()}'

    def dump(self):
        repo.write(self.id, self.dumps())

    def dumps(self) -> str:
        return json.dumps(obj=attr.asdict(self), indent=4)

    @classmethod
    def load(cls: typing.Type[T], identifier: str) -> T:
        try:
            obj = cls.loads(repo.read(identifier))
            if obj.id != identifier:
                obj = attr.evolve(obj, id=identifier)
                obj.dump()
            return obj
        except (json.JSONDecodeError, TypeError) as e:
            print(f'{type(e).__name__} while loading {identifier} from file')
            raise

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
            if data.startswith('values:'):
                return globals()[data.split(':', 1)[1]]
            if data.startswith('expression:'):
                exp_str = data.split(':', 1)[1]
                value_s = {escape_colon_dot(k): globals()[k.split(':', 1)[1]] for k in set(values_re.findall(exp_str))}
                id_s = {escape_colon_dot(k): cls.load(k) for k in set(id_re.findall(exp_str))}
                return eval(escape_colon_dot(exp_str), globals(), dict(id_s, **value_s))
            # noinspection PyArgumentList
            return cls(data)
        if isinstance(data, (int, bool)):
            # noinspection PyArgumentList
            return cls(data)
        if isinstance(data, (list, tuple, set)):
            return tuple(cls.cast(d) for d in data)
        if isinstance(data, dict):
            return cls(**data)


@attr.s(frozen=True)
class Param(Serializable):
    name = attr.ib(type=str, validator=is_instance_of(str))


@attr.s(frozen=True)
class Target(Param):
    url = attr.ib(type=str, default=None, validator=attr.validators.optional(is_instance_of(str)))

    @url.validator
    def url_validator(self, attribute, value):
        if value and not value.startswith('https://'):
            raise ValueError(f'{value} is not a valid {attribute.name}')


@attr.s(frozen=True)
class Value(Serializable):
    value = attr.ib(type=typing.Union[bool, int, str], validator=is_instance_of((bool, int, str)))

    def __bool__(self) -> bool:
        return bool(self.value)


@attr.s(frozen=True)
class Values(Serializable):
    values = attr.ib(type=typing.Union[typing.Tuple[Value, ...], Specials], converter=Value.cast, factory=tuple,
                     validator=is_instance_of((tuple, Specials)))

    @values.validator
    def values_validator(self, attribute, value):
        if isinstance(value, Specials):
            return
        errors = ''
        for v in value:
            errors += '' if isinstance(v, Value) else f'{v} is not of type Value'
        if errors:
            raise ValueError(f'errors in {attribute.name}: {errors.strip()}')

    def __bool__(self) -> bool:
        return bool(self.values)

    def __contains__(self, item: typing.Union[Value, bool, int, str]) -> bool:
        if self.values is AllValues:
            return True
        return item.value in self.values if isinstance(item, Value) else item in self.values

    def __iter__(self) -> typing.Generator[typing.Union[bool, int, str], None, None]:
        if isinstance(self.values, Specials):
            yield from tuple()
        yield from self.values

    def __add__(self, other: Values) -> typing.Union[Values, Specials]:
        """ add values, return values that are in either i.e. union of sets"""
        if self.values is AllValues or other.values is AllValues:
            values = AllValues
        else:
            values = self.values + tuple(v for v in other.values if v not in self.values)
        return Values(values=values, doc=f'{self.doc} (+) {other.doc}')

    def __sub__(self, other: Values) -> typing.Union[Values, Specials]:
        """ remove values from self that are also in other"""
        if self.values is AllValues:
            values = self.values
        elif other.values is AllValues:
            values = tuple()
        else:
            values = tuple(v for v in self.values if v not in other.values)
        return Values(values=values, doc=f'{self.doc} (-) {other.doc}')

    def __mod__(self, other: Values) -> typing.Union[Values, Specials]:
        """ return values that are in both i.e. intersection of sets"""
        if self.values is AllValues:
            return other.values
        if other.values is AllValues:
            return self.values
        values = tuple(v for v in self.values if v in other.values)
        return Values(values=values, doc=f'{self.doc} (%) {other.doc}')


AllVals = Values(AllValues, id='id:AllVals')
NoVals = Values(id='id:NoVals')


@attr.s(frozen=True)
class ParamPolicy(Serializable):
    target = attr.ib(type=Target, converter=Target.cast, validator=is_instance_of(Target))
    param = attr.ib(type=Param, converter=Param.cast, validator=is_instance_of(Param))
    allowed = attr.ib(type=Values, converter=Values.cast, default=AllVals, validator=is_instance_of(Values))
    denied = attr.ib(type=Values, converter=Values.cast, default=NoVals, validator=is_instance_of(Values))

    def __add__(self: ParamPolicy, other: ParamPolicy) -> typing.Union[ParamPolicy, ParamsPolicies]:
        if self.target == other.target and self.param == other.param:
            denied = self.denied + other.denied
            allowed = (self.allowed % other.allowed) - denied
            doc = f'{self.doc} (+) {other.doc}'
            return ParamPolicy(target=self.target, param=self.param, doc=doc, allowed=allowed, denied=denied)
        return NotImplemented

    def __sub__(self, other: ParamPolicy) -> typing.Union[ParamPolicy, ParamsPolicies]:
        if self.target == other.target and self.param == other.param:
            allowed = self.allowed + other.allowed
            denied = self.denied - other.allowed
            doc = f'{self.doc} (-) {other.doc}'
            return ParamPolicy(target=self.target, param=self.param, doc=doc, allowed=allowed, denied=denied)
        return NotImplemented

    def __bool__(self: ParamPolicy) -> bool:
        if self.denied is AllValues:
            return False
        return bool(self.allowed - self.denied)

    def __matmul__(self: ParamPolicy, value: typing.Union[bool, int, str]) -> bool:
        """ Policy @ Value"""
        return value in self.allowed and value not in self.denied


@attr.s(frozen=True)
class ParamsPolicies(Serializable):
    policies = attr.ib(type=typing.Dict[str, ParamPolicy])


if __name__ == '__main__':
    param1 = Param.load('id:policies.test.param_param1')
    param1.dump()
    print(param1)
    print(repo.list)
