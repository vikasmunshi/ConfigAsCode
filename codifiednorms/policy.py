#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Class BasePolicy, Policy, PolicySet, Config
"""
from __future__ import annotations

import dataclasses
import itertools
import json
import os
import pathlib
import time
import uuid

try:
    from .freezer import *
except ImportError:
    from freezer import *

T = typing.TypeVar('T', bound='BasePolicy')
V = typing.Union[str, bool, None]

repo_root = pathlib.Path(os.getcwd().split('repository')[0]).joinpath('repository')


@enforce_strict_types
def ns(file: pathlib.Path) -> str:
    return str(file.relative_to(repo_root).parent).replace('/', '.')


@enforce_strict_types
def ls_repo(path: typing.Optional[pathlib.Path] = None) -> typing.Generator[pathlib.Path, None, None]:
    if (not repo_root.exists()) or (not repo_root.is_dir()):
        raise RuntimeError(f'cwd {os.getcwd()} does not contain and is not in a folder named repository')
    path = path or repo_root
    for file in path.iterdir():
        if file.is_dir():
            yield from ls_repo(file)
        else:
            yield file


@enforce_strict_types
def intersection(l1: typing.Iterable[str], l2: typing.Iterable[str]) -> typing.Tuple[str, ...]:
    return tuple(set(l1 or l2).intersection(set(l2 or l1)))


@enforce_strict_types
def union(l1: typing.Iterable[str], l2: typing.Iterable[str]) -> typing.Tuple[str, ...]:
    return tuple(set(l1).union(set(l2)))


@enforce_strict_types
@dataclasses.dataclass(frozen=True)
class BasePolicy:
    name: str
    version: str
    doc: str
    target: str
    namespace: str
    type: str

    @staticmethod
    def __data_mapper__(data: dict) -> dict:
        return {param: data.get(param, f'replace with {param} value')
                for param in (field.name for field in dataclasses.fields(BasePolicy))}

    @functools.cached_property
    def as_dict(self) -> typing.Dict:
        return {'id': self.id, **dataclasses.asdict(self)}

    @functools.cached_property
    def id(self) -> str:
        content = dataclasses.asdict(self)
        content.pop('doc')
        return f'{self.namespace}:{str(uuid.uuid5(uuid.NAMESPACE_URL, str(sorted(content.items()))))}'

    @functools.cached_property
    def proper_name(self) -> str:
        return f'{self.name} v{self.version}' if self.version else self.name

    @functools.cached_property
    def is_empty(self) -> bool:
        fields = set(field.name for field in dataclasses.fields(self.__class__)) - \
                 set(field.name for field in dataclasses.fields(BasePolicy))
        return all(not getattr(self, field) for field in fields) if fields else False

    def dump(self, file: pathlib.Path) -> None:
        data = dict(self.as_dict, **{'ts': str(int(time.time()))})
        with open(file, 'w') as out_file:
            json.dump(data, out_file, indent=4)

    @classmethod
    def from_dict(cls: typing.Type[T], data: typing.Dict, register: bool = True) -> typing.Optional[T]:
        if data['type'] == cls.__name__:
            obj = cls(**cls.__data_mapper__(data))
            if register:
                cls.register(obj)
            return obj

    @classmethod
    def subclass_from_dict(cls: typing.Type[T], data: typing.Dict) -> typing.Optional[T]:
        try:
            policy_type = {c.__name__: c for c in (cls, *cls.__subclasses__())}[data['type']]
            return policy_type.from_dict(data)
        except (KeyError, TypeError, ValueError):
            return

    @classmethod
    def load(cls: typing.Type[T], file: pathlib.Path, register: bool = True) -> typing.Optional[T]:
        try:
            with open(file) as in_file:
                return cls.from_dict(dict(json.load(in_file), **{'namespace': ns(file)}), register=register)
        except (IOError, json.JSONDecodeError, KeyError, UnicodeDecodeError, ValueError):
            return

    @classmethod
    @functools.lru_cache
    def get_cached_repo(cls: typing.Type[T]) -> typing.Dict[str, T]:
        return {obj.id: obj for file in ls_repo() if (obj := cls.load(file=file, register=False)) is not None}

    @classmethod
    def get(cls: typing.Type[T], obj_id: str) -> typing.Optional[T]:
        return cls.get_cached_repo().get(obj_id)

    @classmethod
    def register(cls: typing.Type[T], obj: T) -> None:
        if obj.id not in cls.get_cached_repo():
            cls.get_cached_repo()[obj.id] = obj


@enforce_strict_types
@dataclasses.dataclass(frozen=True)
class Policy(BasePolicy):
    allowed: FrozenDict[str, typing.Tuple[V, ...]]
    blocked: FrozenDict[str, typing.Tuple[V, ...]]
    enforced: FrozenDict[str, V]
    required: typing.Tuple[str, ...]
    possible: typing.Tuple[str, ...]

    @staticmethod
    def __data_mapper__(data: dict) -> dict:
        return dict(BasePolicy.__data_mapper__(data), **{'allowed': FrozenDict(data.get('allowed', {})),
                                                         'blocked': FrozenDict(data.get('blocked', {})),
                                                         'enforced': FrozenDict(data.get('enforced', {})),
                                                         'required': tuple(data.get('required', [])),
                                                         'possible': tuple(data.get('possible', [])), })

    @functools.cached_property
    def params(self) -> typing.Tuple[str, ...]:
        return tuple(functools.reduce(union, (self.allowed.keys(), self.blocked.keys(),
                                              self.enforced.keys(), self.required)))

    @functools.cached_property
    def inconsistencies(self) -> str:
        errors = ''
        if self.possible:
            for param_list, params in (('allowed', self.allowed.keys()), ('blocked', self.blocked.keys()),
                                       ('required', self.required), ('enforced', self.enforced)):
                for param in params:
                    if param not in self.possible:
                        errors += f'param {param} defined in "{param_list}" is not in "possible": {self.possible}\n'
        for param, value in self.enforced.items():
            if param in self.blocked and value in self.blocked[param]:
                errors += f'enforced value "{value}" for "{param}" is blocked: {self.blocked}\n'
            if param in self.allowed and value not in self.allowed[param]:
                errors += f'enforced value "{value}" for "{param}" is not allowed: {self.allowed}\n'
        if self.blocked:
            for param, values in self.allowed.items():
                for value in values:
                    if param in self.blocked and value in self.blocked[param]:
                        errors += f'allowed value "{value}" for "{param}" is also blocked: {self.blocked}\n'
        for param, values in self.allowed.items():
            if not values:
                errors += f'param {param} cannot be assigned any value\n'
        return errors.strip()

    def evaluate_policy(self, assigned: FrozenDict[str, str]) -> str:
        errors = self.inconsistencies
        for param, value in assigned.items():
            if value not in self.allowed.get(param, (value,)):
                errors += f'"{param}"="{value}" not allowed, allowed values are: {self.allowed[param]}\n'
            if value in self.blocked.get(param, tuple()):
                errors += f'"{param}"="{value}" is blocked, blocked values are: {self.blocked[param]}\n'
            if value != self.enforced.get(param, value):
                errors += f'"{param}"="{value}" is enforced to be "{self.enforced[param]}"\n'
            if param not in (self.possible or (param,)):
                errors += f'param "{param}" is not possible, possible params are: {self.possible}\n'
        for param in self.required:
            if param not in assigned:
                errors += f'param {param} is required to be assigned, required params are: {self.required}\n'
        return errors.strip()

    def policy_arithematic_checks(self: Policy, other: Policy) -> None:
        if not (isinstance(self, Policy) and isinstance(other, Policy)):
            return NotImplemented(f'Cannot add/subtract non-Policy types "{type(self)}" and "{type(other)}"')
        errors = ''
        if self.inconsistencies != '':
            errors += f'resolve consistency errors in {self.id}\n{self.consistency_errors}'
        if other.inconsistencies != '':
            errors += f'resolve consistency errors in {self.id}\n{other.consistency_errors}'
        if errors:
            return NotImplemented(errors)

    def __add__(self: Policy, other: typing.Union[Policy, PolicySet]) -> typing.Union[Policy, FrozenDict[str, Policy]]:
        if isinstance(other, PolicySet):
            return other + self

        self.policy_arithematic_checks(other)

        if self.target != other.target:
            return PolicySet.from_dict(dict(
                name=f'{self.proper_name} (+) {other.proper_name}',
                version='',
                doc=f'{self.doc} (+) {other.doc}',
                target=self.target,
                namespace=self.namespace,
                type='PolicySet',
                policies=(self.id, other.id),
                exemptions=tuple(), ))

        if ev := [f'param {p} enforced to be {v1} by {self.id} and {v2} by {other.id}'
                  for p, v1 in self.enforced.items() if v1 != (v2 := other.enforced.get(p, v1))]:
            return NotImplemented(f'inconsistent values for enforced parameters {ev}')

        return Policy.from_dict(dict(
            name=f'{self.proper_name} (+) {other.proper_name}',
            version='',
            doc=f'{self.doc} (+) {other.doc}',
            target=self.target,
            namespace=self.namespace,
            type='Policy',
            allowed={param: intersection(self.allowed.get(param, []), other.allowed.get(param, []))
                     for param in union(self.allowed.keys(), other.allowed.keys())},
            blocked={param: union(self.blocked.get(param, []), other.blocked.get(param, []))
                     for param in union(self.blocked.keys(), other.blocked.keys())},
            enforced=dict(other.enforced, **self.enforced),
            required=union(self.required, other.required),
            possible=intersection(self.possible, other.possible)))

    def __sub__(self: Policy, other: typing.Union[Policy, PolicySet]) -> typing.Union[Policy, FrozenDict[str, Policy]]:
        if isinstance(other, PolicySet):
            return PolicySet.from_dict(dict(
                name=f'{self.proper_name}',
                version='',
                doc=f'{self.doc}',
                target=self.target,
                namespace=self.namespace,
                type='PolicySet',
                policies=(self.id,),
                exemptions=tuple(), )) - other

        self.policy_arithematic_checks(other)

        if not (other.allowed and all(not getattr(other, o) for o in ('blocked', 'enforced', 'required', 'possible'))):
            offending = tuple(k for k in ('blocked', 'enforced', 'required', 'possible') if getattr(other, k))
            raise ValueError(f'Exemption Policy should only have values in allowed and not in "{offending}"')

        if self.target != other.target:
            return PolicySet.from_dict(dict(
                name=f'{self.proper_name} (-) {other.proper_name}',
                version='',
                doc=f'{self.doc} (-) {other.doc}',
                target=self.target,
                namespace=self.namespace,
                type='PolicySet',
                policies=(self.id,),
                exemptions=(other.id,), ))

        return Policy.from_dict(dict(
            name=f'{self.proper_name} (-) {other.proper_name}',
            version='',
            doc=f'{self.doc} (-) {other.doc}',
            target=self.target,
            namespace=self.namespace,
            type='Policy',
            allowed={param: union(self.allowed.get(param, []), other.allowed.get(param, []))
                     for param in union(self.allowed.keys(), other.allowed.keys())},
            blocked={param: tuple(set(values) - set(other.allowed.get(param, [])))
                     for param, values in self.blocked.items()},
            enforced={param: value for param, value in self.enforced.items() if value not in other.allowed.get(param)},
            required=tuple(set(self.required) - set(other.allowed.keys())),
            possible=tuple() if not self.possible else union(self.possible, other.allowed.keys())))

    @property
    def policy(self) -> FrozenDict[str, Policy]:
        return FrozenDict({self.target: self})


@enforce_strict_types
@dataclasses.dataclass(frozen=True)
class PolicySet(BasePolicy):
    policies: typing.Tuple[str, ...]
    exemptions: typing.Tuple[str, ...]

    @staticmethod
    def __data_mapper__(data: dict) -> dict:
        return dict(BasePolicy.__data_mapper__(data), **{'policies': tuple(data.get('policies', [])),
                                                         'exemptions': tuple(data.get('exemptions', []))})

    @functools.cached_property
    def as_dict(self) -> typing.Dict:
        return {'id': self.id, **dataclasses.asdict(self), 'policy': {t: p.as_dict for t, p in self.policy.items()}}

    @functools.cached_property
    def policy(self) -> FrozenDict[str, Policy]:
        def key(policy):
            return policy.target

        try:
            policies = {
                k: list(v)
                for k, v in itertools.groupby(sorted([Policy.get(pid) for pid in self.policies], key=key), key=key)}
            exemptions = {
                k: list(v)
                for k, v in itertools.groupby(sorted([Policy.get(pid) for pid in self.exemptions], key=key), key=key)}

            return FrozenDict({
                target: functools.reduce(lambda x, y: x - y, exemptions.get(target, []),
                                         functools.reduce(lambda x, y: x + y, policies[target]))
                for target in policies.keys()})
        except AttributeError as e:
            return FrozenDict({})

    @functools.cached_property
    def inconsistencies(self) -> str:
        errors = ''
        if not self.policy:
            errors += f'PolicySet {self.id} has an invalid policy'
        else:
            errors += '\n'.join(f'policy for {target} has errors:\n{policy.inconsistencies}\n'
                                for target, policy in self.policy.items() if policy.inconsistencies != '')
        return errors.strip()

    def __add__(self: PolicySet, other: typing.Union[Policy, PolicySet]) -> FrozenDict[str, Policy]:
        return FrozenDict({
            target:
                self.policy[target] + other.policy[target]
                if (target in self.policy and target in other.policy)
                else (self.policy.get(target) or other.policy[target])
            for target in union(self.policy.keys(), other.policy.keys())})

    def __sub__(self: PolicySet, other: typing.Union[Policy, PolicySet]) -> PolicySet:
        return FrozenDict({target: policy - other.policy[target] if target in other.policy else policy
                           for target, policy in self.policy.items()})


@enforce_strict_types
@dataclasses.dataclass(frozen=True)
class Config(BasePolicy):
    assigned: FrozenDict[str, FrozenDict[str, V]]
    applicable: str

    @staticmethod
    def __data_mapper__(data: dict) -> dict:
        return dict(BasePolicy.__data_mapper__(data), **{'assigned': FrozenDict(data.get('assigned', {})),
                                                         'applicable': data.get('applicable', '')})

    @functools.cached_property
    def as_dict(self) -> typing.Dict:
        return {'id': self.id, **dataclasses.asdict(self), 'policy': {t: p.as_dict for t, p in self.policy.items()}}

    @functools.cached_property
    def policy(self) -> FrozenDict[str, Policy]:
        if self.applicable in Policy.get_cached_repo():
            return PolicySet.from_dict(dict(self.as_dict, **{'policies': [self.applicable]})).policy
        elif self.applicable in PolicySet.get_cached_repo():
            return PolicySet.get(self.applicable).policy
        else:
            return FrozenDict({})

    @functools.cached_property
    def inconsistencies(self) -> str:
        errors = ''
        if not self.policy:
            errors += f'PolicySet {self.id} has an invalid policy'
        else:
            errors += '\n'.join(f'policy for {target} has errors:\n{policy.inconsistencies}\n'
                                for target, policy in self.policy.items() if policy.inconsistencies != '')
            for target in self.assigned.keys():
                if target not in self.policy:
                    errors += f'no policy defined in applicable for target {target}'
        return errors.strip()

    @functools.cached_property
    def policy_violations(self) -> str:
        errors = self.inconsistencies
        for target, assigned in self.assigned.items():
            if target in self.policy:
                errors += self.policy[target].evaluate_policy(assigned=assigned)
        return errors.strip()

    @functools.cached_property
    def config(self) -> typing.Optional[FrozenDict[str, FrozenDict[str, V]]]:
        if self.inconsistencies == '' and self.policy_violations == '':
            return FrozenDict({target: dict(assigned, **self.policy[target].enforced)
                               for target, assigned in self.assigned.items()})
