#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Python3 library to Manage Codified Norms and Config as Code
Class Serializable, Param, Value, Values, ParamPolicy
"""
from __future__ import annotations

import functools
import json
import os
import pathlib
import re
import typing
import uuid

import attr

try:
    from .freezer import FrozenDict
except ImportError:
    from freezer import FrozenDict

T = typing.TypeVar('T', bound='Serializable')
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

    def identifier(self, path: pathlib.Path) -> str:
        return 'id:' + str(path.relative_to(self.root)).replace('/', '.').replace('\\', '.')

    def is_valid_id(self, identifier: str) -> bool:
        if not identifier.startswith('id:'):
            return False
        if self.root not in self.path(identifier).parents:
            return False
        return True

    def new(self, name: str) -> str:
        path = pathlib.Path(os.getcwd()).relative_to(self.root).joinpath(f'{name}')
        path = str(path).replace('/', '.').replace('\\', '.')
        return f'id:{path}'

    def read(self, identifier: str) -> str:
        with open(self.path(identifier), 'r') as in_file:
            return in_file.read()

    def write(self, identifier: str, s: str):
        with open(self.path(identifier), 'w') as out_file:
            out_file.write(s)

    def put(self, obj: Serializable):
        if obj.id not in self.repo_cache:
            self.repo_cache[obj.id] = obj

    def get(self, identifier: str) -> Serializable:
        return self.repo_cache.get(identifier, None)

    @property
    def list(self) -> list[str, ...]:
        return list(self.repo_cache.keys())


repo = Repo()


class Specials(str):
    def __eq__(self, other: typing.Union[Specials, str]) -> bool:
        r = ((False, False, False),
             (False, None, True),
             (False, True, True))[
            0 if int(self is NoValue) else 2 if int(self is AnyValue or self is AllValues) else 1][
            0 if int(other is NoValue) else 2 if int(other is AnyValue or other is AllValues) else 1]
        if r is not None:
            return r
        return super(Specials, self).__eq__(other)


AnyValue = Specials('value:AnyValue')
NoValue = Specials('value:NoValue')
AllValues = Specials('value:AllValues')
id_re = re.compile(r'id:[^\s)(=/*-+]*')
value_re = re.compile(r'value:[^\s)(=/*-+]*')
escape_colon_dot: typing.Callable[[str], str] = lambda key: key.replace(':', '_').replace('.', '_')


@attr.s(frozen=True, kw_only=True)
class Serializable:
    id = attr.ib(type=str, eq=False, default='', validator=is_instance_of(str))
    type = attr.ib(type=str, eq=False, init=False)
    doc = attr.ib(type=str, eq=False, default='', validator=is_instance_of(str))

    def __attrs_post_init__(self):
        obj_name = ''.join(self.name.split()) if hasattr(self, 'name') \
            else ''.join(self.value.split()) if hasattr(self, 'value') \
            else uuid.uuid5(uuid.NAMESPACE_URL, str(attr.asdict(self, filter=lambda a, v: a.eq))).hex
        if self.id == '':
            object.__setattr__(self, 'id', repo.new(f'{self.__class__.__name__.lower()}_{obj_name}'))
        if self.doc == '':
            object.__setattr__(self, 'doc', f'doc for {obj_name}')
        repo.put(obj=self)

    @type.default
    def type_default(self) -> str:
        return self.__class__.__name__

    def dump(self):
        repo.write(self.id, self.dumps())

    def dumps(self) -> str:
        return json.dumps(obj=attr.asdict(self), indent=4)

    @classmethod
    def load(cls: typing.Type[T], identifier: str) -> T:
        return cls.loads(repo.read(identifier))

    @classmethod
    def loads(cls: typing.Type[T], data: str) -> T:
        return json.loads(s=data, object_hook=lambda d: globals().get(d.pop('type'), lambda **kw: kw)(**d))

    @classmethod
    def cast(cls: typing.Type[T], data: typing.Union[T, typing.Iterable, bool, int, str]) \
            -> typing.Optional[typing.Union[T, typing.Tuple[T, ...]]]:
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            if data.startswith('id:'):
                return repo.get(data) or cls.load(data)
            if data.startswith('value:'):
                return globals()[data.split(":", 1)[1]]
            if data.startswith('expression:'):
                exp_str = data.split(':', 1)[1]
                value_s = {escape_colon_dot(k): globals()[k.split(':', 1)[1]] for k in set(value_re.findall(exp_str))}
                id_s = {escape_colon_dot(k): (repo.get(k) or cls.load(k)) for k in set(id_re.findall(exp_str))}
                return eval(escape_colon_dot(exp_str), globals(), dict(id_s, **value_s))
            # noinspection PyArgumentList
            return cls(data)
        if isinstance(data, (int, bool)):
            # noinspection PyArgumentList
            return cls(data)
        if isinstance(data, (list, tuple, set)):
            if hasattr(cls, '__iter__'):
                # noinspection PyArgumentList
                return cls(tuple(data))
            return tuple(cls.cast(d) for d in data)
        if isinstance(data, dict):
            return cls(**data)

    def compile(self: T) -> T:
        out_folder = repo.root.joinpath('compiled')
        file_path = out_folder.joinpath((fp := repo.path(self.id)).parent.relative_to(repo.root), fp.stem)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        obj = attr.evolve(self, id=repo.identifier(file_path))
        obj.dump()
        return obj


@attr.s(frozen=True)
class Value(Serializable):
    value = attr.ib(type=typing.Union[bool, int, str, Specials], validator=is_instance_of((bool, int, str, Specials)))

    def __bool__(self) -> bool:
        return bool(self.value)

    def __matmul__(self, policy: ParamPolicy) -> bool:
        """ Value @ Policy"""
        return self in policy.param.possible and self in policy.allowed and self not in policy.denied

    def __pow__(self, policy: ParamPolicy) -> dict[str, str]:
        """ Value ** Policy"""
        return policy.param.get_implementation(self.value if self @ policy else NoValue)


@attr.s(frozen=True)
class Values(Serializable):
    values = attr.ib(type=typing.Tuple[Value, ...], converter=Value.cast, factory=tuple,
                     validator=attr.validators.deep_iterable(is_instance_of(Value), is_instance_of(tuple)))

    def __bool__(self) -> bool:
        return bool(self.values)

    def __contains__(self, item: Value) -> bool:
        if self.values is AllValues:
            return item.value == AnyValue
        return item.value in self.values

    def __iter__(self) -> typing.Generator[Value, None, None]:
        yield from self.values

    def __add__(self, other: Values) -> typing.Union[Values, Specials]:
        """ add values, return values that are in either i.e. union of sets"""
        if self.values is AllValues or other.values is AllValues:
            values = AllValues
        else:
            values = self.values + tuple(v for v in other.values if v not in self.values)
        return attr.evolve(self, values=values, doc=f'{self.doc} (+) {other.doc}', id='')

    def __sub__(self, other: Values) -> typing.Union[Values, Specials]:
        """ remove values from self that are also in other"""
        if self.values is AllValues:
            values = self.values
        elif other.values is AllValues:
            values = tuple()
        else:
            values = tuple(v for v in self.values if v not in other.values)
        return attr.evolve(self, values=values, doc=f'{self.doc} (-) {other.doc}', id='')

    def __mod__(self, other: Values) -> typing.Union[Values, Specials]:
        """ return values that are in both i.e. intersection of sets"""
        if self.values is AllValues:
            return other
        if other.values is AllValues:
            return self
        values = tuple(v for v in self.values if v in other.values)
        return attr.evolve(self, values=values, doc=f'{self.doc} (%) {other.doc}', id='')


AllVals = Values(values=(Value(AnyValue),), id='id:AllVals')
NoVals = Values(values=tuple(), id='id:NoVals')


@attr.s(frozen=True)
class Target(Serializable):
    name = attr.ib(type=str, validator=is_instance_of(str))
    uri = attr.ib(type=str, default='', eq=False, validator=is_instance_of(str))


@attr.s(frozen=True, kw_only=True)
class Param(Serializable):
    name = attr.ib(type=str, validator=is_instance_of(str))
    target = attr.ib(type=Target, validator=is_instance_of(Target))
    possible = attr.ib(type=Values, eq=False, default=AllVals, validator=is_instance_of(Values))
    implementation = attr.ib(type=str, eq=False, default='as_dict', validator=is_instance_of(str))

    @staticmethod
    def register_implementation(func: typing.Callable[[str, typing.Union[bool, int, str, Specials]], dict[str, str]],
                                name: str):
        implementation_repo[name] = func

    @property
    def get_implementation(self):
        return lambda v: implementation_repo.get(self.implementation)(self.name, v)


implementation_repo = {'as_dict': lambda p, v: {p: v}}


@attr.s(frozen=True)
class ParamPolicy(Param):
    param = attr.ib(type=Param, converter=Param.cast, validator=is_instance_of(Param))
    allowed = attr.ib(type=Values, converter=Values.cast, default=AllVals, validator=is_instance_of(Values))
    denied = attr.ib(type=Values, converter=Values.cast, default=NoVals, validator=is_instance_of(Values))

    def __add__(self: ParamPolicy, other: ParamPolicy) -> typing.Union[ParamPolicy, ParamsPolicies]:
        if self.param == other.param:
            denied = self.denied + other.denied
            allowed = (self.allowed % other.allowed) - denied
            doc = f'{self.doc} (+) {other.doc}'
            name = f'{self.name}+{other.name}'
            return ParamPolicy(target=self.target, param=self.param, id='', doc=doc, name=name,
                               allowed=allowed, denied=denied)
        return attr.evolve(NullParamsPolicies, policy=FrozenDict({self.id: self, other.id: other}), id='', doc='')

    def __sub__(self, other: ParamPolicy) -> ParamPolicy:
        if self.param == other.param:
            allowed = self.allowed + other.allowed
            denied = self.denied - other.allowed
            doc = f'{self.doc} (-) {other.doc}'
            name = f'{self.name}-{other.name}'
            return ParamPolicy(target=self.target, param=self.param, id='', doc=doc, name=name,
                               allowed=allowed, denied=denied)
        return self

    def __bool__(self: ParamPolicy) -> bool:
        if self.denied is AllValues:
            return False
        return bool(self.allowed - self.denied)


@attr.s(frozen=True)
class ParamsPolicies(Param):
    policies = attr.ib(type=tuple[typing.Union[str, ParamPolicy], ...], default='',
                       validator=attr.validators.deep_iterable(is_instance_of(ParamPolicy),
                                                               is_instance_of((str, ParamPolicy))))
    expression = attr.ib(type=str, default='', validator=is_instance_of(str))
    policy = attr.ib(type=FrozenDict[str, ParamPolicy])

    @policy.default
    def policy_default(self):
        if self.expression:
            return ParamPolicy.cast(self.expression)
        if self.policies:
            return functools.reduce(lambda x, y: x + y, (ParamPolicy.cast(p) for p in self.policies))
        return FrozenDict({})

    @functools.cached_property
    def policy_map(self) -> dict[str, dict[str, str]]:
        policy_map = {}
        for pid, p in self.policy.items():
            if p.target.id not in policy_map:
                policy_map[p.target.id] = {}
            policy_map[p.target.id][p.param.id] = pid
        return FrozenDict(policy_map)

    def __add__(self, other: typing.Union[ParamsPolicies, ParamPolicy]) -> ParamsPolicies:
        if isinstance(other, ParamPolicy):
            if other.target.id in self.policy_map:
                if other.param.id in self.policy_map[other.target.id]:
                    pid = self.policy_map[other.target.id][other.param.id]
                    param_policy = self.policy[pid] + other
                    policy = FrozenDict({param_policy.id: param_policy,
                                         **{k: v for k, v in self.policy.items() if k != pid}})
                    return attr.evolve(self, policy=policy, id='')
            policy = FrozenDict(dict(self.policy, **{other.id: other}))
            return attr.evolve(self, policy=policy, id='')
        return functools.reduce(lambda p, q: p + q, other.policy.values(), self)

    def __sub__(self, other: typing.Union[ParamsPolicies, ParamPolicy]) -> ParamsPolicies:
        if isinstance(other, ParamPolicy):
            if other.target.id in self.policy_map:
                if other.param.id in self.policy_map[other.target.id]:
                    pid = self.policy_map[other.target.id][other.param.id]
                    param_policy = self.policy[pid] - other
                    policy = FrozenDict({param_policy.id: param_policy,
                                         **{k: v for k, v in self.policy.items() if k != pid}})
                    return attr.evolve(self, policy=policy, id='')
            return self
        return functools.reduce(lambda p, q: p - q, other.policy.values(), self)


NullParamsPolicies = ParamsPolicies(id='id:NullParamsPolicies', name='Param Policies', target=Target(name=AnyValue))

if __name__ == '__main__':
    param1 = Param.load(identifier='id:policies.test.param_param1')
    # param1.dump()
    target1 = Target.load(identifier='id:policies.test.target_target1')
    # target1.dump()
    value1 = Value.load(identifier='id:policies.test.value_value1')
    # value1.dump()
    value2 = Value.load(identifier='id:policies.test.value_value2')
    # value2.dump()
    values1 = Values.load(identifier='id:policies.test.values_values1')
    values2 = repo.get('id:AllVals')
    param1policy = ParamPolicy.load(identifier='id:policies.test.parampolicy_Param1Policy1')
    param1policy2 = ParamPolicy.load(identifier='id:policies.test.parampolicy_Param1Policy2')
    param1policy3 = param1policy + param1policy2

    params_pol1 = ParamsPolicies.load(identifier='id:policies.test.paramspolicies_ParamPolicies1')

    print(repo.list)
    for pol_id, pol in tuple(repo.repo_cache.items()):
        pol.compile()
