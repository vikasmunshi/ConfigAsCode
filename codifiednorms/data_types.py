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
TypeValue = typing.Union[bool, int, str]
type_value = (bool, int, str)


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
    def cast_as(cls: typing.Type[T], data: typing.Union[T, typing.Iterable, dict]) -> T:
        if data is None or isinstance(data, cls):
            return data
        if isinstance(data, str):
            if data.startswith('id:'):
                return cls.load(data)
            # noinspection PyArgumentList
            return cls(data)
        if isinstance(data, (list, tuple, set)):
            if hasattr(cls, '__iter__'):
                # noinspection PyArgumentList
                return cls(data)
            # noinspection PyArgumentList
            return set(v if isinstance(v, cls) else cls(v) for v in data)
        if isinstance(data, dict):
            return cls(**data)
        raise ValueError(f'expected data to be {cls.__name__} or Iterable or Dict, got {data}')


@attr.s(frozen=True)
class Param(Serializable):
    name = attr.ib(type=str, validator=attr.validators.instance_of(str))


@attr.s(frozen=True)
class Target(Param):
    url = attr.ib(type=str, default=None,
                  validator=lambda i, a, v: v is None or (isinstance(v, str) and v.startswith('https://')))


@attr.s(frozen=True)
class Value(Serializable):
    value = attr.ib(type=TypeValue, validator=attr.validators.instance_of(type_value))

    def __bool__(self) -> bool:
        return bool(self.value)


@attr.s(frozen=True)
class Values(Serializable):
    values = attr.ib(type=typing.Tuple[Value], converter=Value.cast_as)

    def __bool__(self) -> bool:
        return bool(self.values)

    def __contains__(self, item: typing.Union[TypeValue, Value]) -> bool:
        return item.value in self.values if isinstance(item, Value) else item in self.values

    def __iter__(self) -> typing.Generator[TypeValue, None, None]:
        yield from self.values

    def __add__(self, other: Values) -> Values:
        return Values(values=self.values.union(other.values), doc=f'{self.doc} (+) {other.doc}')

    def __mul__(self, other: Values) -> Values:
        return Values(values=self.values.intersection(other.values), doc=f'{self.doc} (*) {other.doc}')

    def __sub__(self, other: Values) -> Values:
        return Values(values=self.values - other.values, doc=f'{self.doc} (-) {other.doc}')


@attr.s(frozen=True)
class ParamPolicy(Serializable):
    target = attr.ib(type=Target, converter=Target.cast_as)
    param = attr.ib(type=Param, converter=Param.cast_as)
    allowed = attr.ib(type=Values, converter=Values.cast_as)
    denied = attr.ib(type=Values, converter=Values.cast_as)
    enforced = attr.ib(type=Value, converter=Value.cast_as, default=None)

    def __add__(self, other: ParamPolicy) -> ParamPolicy:
        if self.target == other.target and self.param == other.param:
            if self.enforced and other.enforced and self.enforced != other.enforced:
                raise ValueError(f'cannot enforce {self.enforced} and {other.enforced} for {self.param}')
            allowed = (self.allowed * other.allowed) - other.denied
            denied = self.denied + other.denied
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

    #
    #
    # import dataclasses
    # import functools
    # import json
    # import typing
    # import uuid
    #
    # from freezer import enforce_strict_types
    #
    # TypeDataclass = typing.TypeVar('TypeDataclass', bound='BaseDataClass')
    # TypeValue = typing.Union[str, bool, None]
    #
    #
    # class DataclassJSON(json.JSONEncoder):
    #     def default(self, o: typing.Any()) -> typing.Union[str, dict]:
    #         if dataclasses.is_dataclass(o) and isinstance(o, object):
    #             return dict(vars(o), **{'__dataclass__': o.__class__.__name__})
    #         return super(DataclassJSON, self).default(o)
    #
    #     @staticmethod
    #     def dataclass_object_hook(data: dict) -> typing.Union[dataclasses.dataclass, dict]:
    #         if (dataclass := globals().get(data.pop('__dataclass__', None))) is not None:
    #             if dataclasses.is_dataclass(dataclass) and isinstance(dataclass, type):
    #                 return dataclass(**data)
    #         return data
    #
    #
    # @enforce_strict_types
    # @dataclasses.dataclass(frozen=True)
    # class BaseDataclass:
    #     doc: str = ''
    #
    #     @functools.cached_property
    #     def id(self) -> str:
    #         return str(uuid.uuid5(uuid.NAMESPACE_URL, str(sorted(dataclasses.asdict(self).items()))))
    #
    #     @functools.cached_property
    #     def dumps(self) -> str:
    #         return json.dumps(self, cls=DataclassJSON, indent=4)
    #
    #     @classmethod
    #     def loads(cls: typing.Type[TypeDataclass], data: typing.Union[bytes, str]) -> TypeDataclass:
    #         return json.loads(data, object_hook=DataclassJSON.dataclass_object_hook)
    #
    #
    # @enforce_strict_types
    # @dataclasses.dataclass(frozen=True)
    # class Value(BaseDataclass):
    #     value: TypeValue
    #
    #     def __eq__(self, other: typing.Union[Value, str, bool, None]) -> bool:
    #         return self.value == (other.value if isinstance(other, Value) else other)
    #
    #     def __bool__(self) -> bool:
    #         return self.value is not None
    #
    #
    # # noinspection PyDataclass
    # @enforce_strict_types
    # @dataclasses.dataclass(frozen=True)
    # class Param(Value):
    #     value: str
    #
    #
    # # noinspection PyDataclass
    # @enforce_strict_types
    # @dataclasses.dataclass(frozen=True)
    # class Target(Value):
    #     value: str
    #     url: str = None
    #     console: str = None
    #
    #
    # # noinspection PyDataclass
    # @enforce_strict_types
    # @dataclasses.dataclass(frozen=True)
    # class Values(BaseDataclass):
    #     values: typing.List[Value]
    #
    #     @functools.cached_property
    #     def values_set(self) -> typing.Set[TypeValue]:
    #         return set(v.value for v in self.values)
    #
    #     def __iter__(self) -> typing.Generator[TypeValue, None, None]:
    #         for v in self.values_set:
    #             yield v
    #
    #     def __bool__(self) -> bool:
    #         return len(self.values) > 0
    #
    #     def __contains__(self, item: typing.Union[Value, TypeValue]) -> bool:
    #         return item.value in self.values_set if isinstance(item, Value) else item in self.values_set
    #
    #
    # # noinspection PyDataclass
    # @enforce_strict_types
    # @dataclasses.dataclass(frozen=True)
    # class ParamPolicy(BaseDataclass):
    #     param: Param
    #     allowed: Values = Values()
    #     blocked: Values = Values()
    #     enforced: Value = Value()
    #
    #     @functools.cached_property
    #     def errors(self) -> str:
    #         errors = ''
    #         if not any([self.allowed, self.blocked, self.enforced]):
    #             errors += f'policy for param {self.param.value} is empty'
    #         else:
    #             if self.allowed and self.blocked:
    #                 errors += f'allowed values {v} are blocked' if (
    #                         len(v := self.allowed.values_set.intersection(self.blocked.values_set)) > 0) else ''
    #             if self.enforced and self.allowed:
    #                 errors += f'enforced value {v} is not allowed' if (v := self.enforced.value) not in self.allowed else ''
    #             if self.enforced and self.blocked:
    #                 errors += f'enforced value {v} is blocked' if (v := self.enforced.value) in self.blocked else ''
    #
    #         return errors
    #
    #     def check(self, assigned: typing.Union[Value, str]) -> bool:
    #         return assigned in self.allowed and assigned not in self.blocked and self.enforced == assigned
    #
    #     def __add__(self, other: ParamPolicy) -> ParamPolicy:
    #         if self.param != other.param:
    #             return NotImplemented
    #         if self.enforced and other.enforced:
    #             return NotImplemented
    #         if self.default and other.default:
    #             return NotImplemented
    #
    #         return ParamPolicy(
    #             param=self.param,
    #             allowed=AllowedValues([v for v in self.allowed if v in other.allowed]),
    #             blocked=BlockedValues(list(self.blocked) + list(v for v in other.blocked if v not in self.blocked)),
    #             enforced=self.enforced or other.enforced,
    #             default=self.default or other.default,
    #             doc=f'{self.doc} (+) {other.doc}', )
    #
    #     def __sub__(self, other: ParamPolicy) -> ParamPolicy:
    #         if self.param != other.param:
    #             return NotImplemented
    #         if other.blocked or other.enforced.value is not None or other.default.value is not None:
    #             return NotImplemented
    #
    #         return ParamPolicy(
    #             param=self.param,
    #             allowed=AllowedValues(list(self.allowed) + list(v for v in other.allowed if v not in self.allowed)),
    #             blocked=BlockedValues([v for v in self.blocked if v not in other.allowed]),
    #             enforced=self.enforced,
    #             default=self.default,
    #             doc=f'{self.doc} (-) {other.doc}', )
    #
    #
    # @enforce_strict_types
    # @dataclasses.dataclass(frozen=True)
    # class TargetPolicy(BaseDataclass):
    #     target: Target
    #     policy: typing.List[ParamPolicy]
    #
    #
    # if __name__ == '__main__':
    #     policy = ParamPolicy(param=Param('some param', doc='some doc'),
    #                          allowed=AllowedValues([Value('val1'), Value('val2')]),
    #                          blocked=BlockedValues([Value('val0')]))
    #     policy1 = ParamPolicy(param=Param('some param', doc='some doc'),
    #                           allowed=AllowedValues([Value('val1'), Value('val3')]),
    #                           blocked=BlockedValues([Value('val0'), Value('val9')]))
    #     policy3 = ParamPolicy(param=Param('some param', doc='some doc'),
    #                           allowed=AllowedValues([Value('val1'), Value('val0')]), )
    #     print(policy)
    #     policy_json = policy.dumps
    #     policy2 = ParamPolicy.loads(policy_json)
    #     print(policy_json)
    #     print(policy)
    #     print(policy2)
    #     print(dataclasses.asdict(policy))
    #     print(policy2.id)
    #     print('val1' in AllowedValues([Value('val1'), Value('val2')]))
    #     print('val0' in BlockedValues([Value('val0')]))
    #     print(policy.check('val1'))
    #     policy4 = policy1 - policy3
    #     print(policy4)
