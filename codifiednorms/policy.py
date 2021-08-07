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
import uuid
import time

try:
    from .freezer import *
except ImportError:
    from freezer import *

T = typing.TypeVar('T', bound='BasePolicy')
V = typing.Union[str, bool, None]


@enforce_types
def ls_repo(path: typing.Optional[pathlib.Path] = None) -> typing.Generator[pathlib.Path, None, None]:
    path = path or pathlib.Path(os.getcwd())
    for file in path.iterdir():
        if file.is_dir():
            yield from ls_repo(file)
        else:
            yield file


@enforce_types
def intersection(l1: typing.Optional[typing.Iterable[str]], l2: typing.Optional[typing.Iterable[str]]) -> \
        typing.Tuple[str, ...]:
    l1 = tuple(l1) if l1 is not None else tuple()
    l2 = tuple(l2) if l2 is not None else tuple()
    return tuple(set(l1 or l2).intersection(set(l2 or l1)))


@enforce_types
def union(l1: typing.Optional[typing.Iterable[str]], l2: typing.Optional[typing.Iterable[str]]) -> \
        typing.Tuple[str, ...]:
    l1 = tuple(l1) if l1 is not None else tuple()
    l2 = tuple(l2) if l2 is not None else tuple()
    return tuple(set(l1 or l2).union(set(l2 or l1)))


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
        return {param: data[param] for param in (field.name for field in dataclasses.fields(BasePolicy))}

    @functools.cached_property
    def as_dict(self) -> typing.Dict:
        return {'id': self.id, **dataclasses.asdict(self), 'ts': str(int(time.time()))}

    @functools.cached_property
    def id(self) -> str:
        content = dataclasses.asdict(self)
        content.pop('doc')
        return f'{self.namespace}:{str(uuid.uuid5(uuid.NAMESPACE_URL, str(sorted(content.items()))))}'

    @functools.cached_property
    def proper_name(self) -> str:
        return f'{self.name} v{self.version}' if self.version else self.name

    def dump(self, file: pathlib.Path) -> None:
        with open(file, 'w') as out_file:
            json.dump(self.as_dict, out_file, indent=4)

    @classmethod
    def from_dict(cls: typing.Type[T], data: typing.Dict) -> typing.Optional[T]:
        if data['type'] == cls.__name__:
            return cls(**cls.__data_mapper__(data))

    @classmethod
    def subclass_from_dict(cls: typing.Type[T], data: typing.Dict) -> typing.Optional[T]:
        try:
            policy_type = {c.__name__: c for c in (cls, *cls.__subclasses__())}[data['type']]
            return policy_type(**policy_type.__data_mapper__(data))
        except (KeyError, TypeError):
            return

    @classmethod
    def load(cls: typing.Type[T], file: pathlib.Path) -> typing.Optional[T]:
        try:
            with open(file) as in_file:
                return cls.from_dict(dict(json.load(in_file), **{'namespace': file.parent.stem}))
        except (IOError, json.JSONDecodeError, KeyError, UnicodeDecodeError, ValueError):
            return

    @classmethod
    @functools.lru_cache
    def get_cached_repo(cls: typing.Type[T]) -> typing.Dict[str, T]:
        return {obj.id: obj for file in ls_repo() if (obj := cls.load(file=file)) is not None}

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
                                                         'required': tuple(data.get('required', tuple())),
                                                         'possible': tuple(data.get('possible', tuple())), })

    @functools.cached_property
    def params(self) -> typing.Tuple[str, ...]:
        return tuple(functools.reduce(union, (self.allowed.keys(), self.blocked.keys(),
                                              self.enforced.keys(), self.required)))

    @functools.cached_property
    def is_consistent(self) -> bool:
        if self.possible and any(param not in self.possible for param in self.params):
            return False
        if self.enforced and not self.validate(assigned=self.enforced):
            return False
        if self.blocked and any(any(value in self.allowed.get(param, tuple()) for value in values)
                                for param, values in self.blocked.items()):
            return False
        return True

    def __post_init__(self):
        if not self.is_consistent:
            c = '; '.join(f'{a}:{getattr(self, a)}' for a in ('allowed', 'blocked', 'enforced', 'required', 'possible'))
            raise ValueError(f'Policy {self.id} ({self.name}) is inconsistent; {c}')

    def __add__(self: Policy, other: Policy) -> typing.Union[Policy, PolicySet]:
        if not (isinstance(self, Policy) and isinstance(other, Policy)):
            return NotImplemented(f'Cannot combine type "{type(self)}" with "{type(other)}"')
        if self.target != other.target:
            return NotImplemented(f'Cannot combine target "{self.target}" with "{other.target}"')
        if ev := [param for param, value in self.enforced.items() if value != other.enforced.get(param, value)]:
            raise ValueError(f'inconsistent values for enforced Parameters: "{", ".join(ev)}"')

        return Policy.from_dict(dict(
            name=f'{self.proper_name} (+) {other.proper_name}',
            version='',
            doc=f'{self.doc} (+) {other.doc}',
            target=self.target,
            namespace=self.namespace,
            type=self.type,
            allowed={param: intersection(self.allowed.get(param), other.allowed.get(param))
                     for param in union(self.allowed.keys(), other.allowed.keys())},
            blocked={param: union(self.blocked.get(param), other.blocked.get(param))
                     for param in union(self.blocked.keys(), other.blocked.keys())},
            enforced=dict(other.enforced, **self.enforced),
            required=tuple(set(self.required + other.required)),
            possible=tuple() if not (self.possible and other.possible) else union(self.possible, other.possible)))

    def __sub__(self: Policy, other: Policy) -> Policy:
        if not (isinstance(self, Policy) and isinstance(other, Policy)):
            return NotImplemented(f'Cannot exempt type "{type(self)}" by "{type(other)}"')
        if self.target != other.target:
            return NotImplemented(f'Cannot exempt target "{self.target}" with "{other.target}"')
        if not (other.allowed and all(not getattr(other, o) for o in ('blocked', 'enforced', 'required', 'possible'))):
            offending = tuple(k for k in ('blocked', 'enforced', 'required', 'possible') if getattr(other, k))
            raise ValueError(f'Exemption Policy should only have values in allowed and not in "{offending}"')

        return Policy.from_dict(dict(
            name=f'{self.proper_name} (-) {other.proper_name}',
            version='',
            doc=f'{self.doc} (-) {other.doc}',
            target=self.target,
            namespace=self.namespace,
            type=self.type,
            allowed={param: union(self.allowed.get(param), other.allowed.get(param))
                     for param in union(self.allowed.keys(), other.allowed.keys())},
            blocked={param: tuple(value for value in values if value not in other.allowed.get(param, tuple()))
                     for param, values in self.blocked.items()},
            enforced={param: value for param, value in self.enforced.items() if value != other.allowed.get(param)},
            required=tuple(set(self.required) - set(other.allowed.keys())),
            possible=tuple() if not self.possible else union(self.possible, other.allowed.keys())))

    def apply_policy(self: Policy, policy: Policy) -> Policy:
        try:
            return self + policy
        except (TypeError, ValueError):
            return self

    def apply_exemption(self: Policy, exemption: Policy) -> Policy:
        try:
            return self - exemption
        except (TypeError, ValueError):
            return self

    def validate(self, assigned: FrozenDict[str, str]) -> bool:
        return not any((value not in self.allowed.get(param, (value,)) or value in self.blocked.get(param, tuple())
                        or value != self.enforced.get(param, value) or param not in (self.possible or (param,)))
                       for param, value in assigned.items())

    def violations(self, assigned: FrozenDict[str, str]) -> typing.Tuple[str]:
        v = tuple()
        for param, value in assigned.items():
            if value not in self.allowed.get(param, (value,)):
                v += f'"{param}"="{value}" not allowed, allowed values are: {self.allowed[param]}',
            if value in self.blocked.get(param, tuple()):
                v += f'"{param}"="{value}" is blocked, blocked values are: {self.blocked[param]}',
            if value != self.enforced.get(param, value):
                v += f'"{param}"="{value}" is enforced to be "{self.enforced[param]}"',
            if param not in (self.possible or (param,)):
                v += f'param "{param}" is not possible, possible params are: {self.possible}',
        return v


@enforce_strict_types
@dataclasses.dataclass(frozen=True)
class PolicySet(BasePolicy):
    policies: typing.Tuple[str, ...]
    exemptions: typing.Tuple[str, ...]

    @staticmethod
    def __data_mapper__(data: dict) -> dict:
        return dict(BasePolicy.__data_mapper__(data), **{'policies': tuple(data.get('policies', tuple())),
                                                         'exemptions': tuple(data.get('exemptions', tuple()))})

    @functools.cached_property
    def as_dict(self) -> typing.Dict:
        return {'id': self.id, **dataclasses.asdict(self), 'policy': {t: p.as_dict for t, p in self.policy.items()}}

    @functools.cached_property
    def policy(self) -> FrozenDict[str, Policy]:
        def key(policy):
            return policy.target

        try:
            policies = {k: list(v) for k, v in
                        itertools.groupby(sorted([Policy.get(pid) for pid in self.policies], key=key), key=key)}
            exemptions = {k: list(v) for k, v in
                          itertools.groupby(sorted([Policy.get(pid) for pid in self.exemptions], key=key), key=key)}

            return FrozenDict({
                target: functools.reduce(lambda x, y: x - y, exemptions.get(target, []),
                                         functools.reduce(lambda x, y: x + y, policies[target]))
                for target in policies.keys()})
        except AttributeError as e:
            raise ValueError(f'PolicySet {self.id} refers to invalid policies')


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
