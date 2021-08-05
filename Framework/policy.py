#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Definition and management of policies as codified norms used for generating target configuration.
"""
from __future__ import annotations
from __future__ import print_function

from dataclasses import asdict, dataclass
from functools import cached_property, lru_cache
from json import JSONDecodeError, dump, load
from pathlib import Path
from typing import Dict, Generator, Optional, Set, TypeVar, Tuple, Union
from uuid import NAMESPACE_URL, uuid5

from frozen import FrozenDict

__all__ = ['Config', 'ConfigSet', 'Policy', 'PolicyExemption', 'PolicySet', 'PolicyViolation']

T = TypeVar('T', bound='BasePolicy')


class PolicyViolation(Exception):
    def __init__(self, msg):
        super(PolicyViolation, self).__init__(msg)


@dataclass(frozen=True)
class BasePolicy:
    name: str
    version: str
    doc: str
    target: str
    namespace: str
    type: str

    @cached_property
    def id(self) -> str:
        content = asdict(self)
        content.pop('doc')
        content_str = str(sorted(content.items()))
        return str(uuid5(NAMESPACE_URL, '/'.join((self.target, self.namespace, self.name, self.version, content_str))))

    @staticmethod
    def param_map(data: dict) -> dict:
        return {'name': data['name'], 'version': data['version'], 'doc': data['doc'],
                'target': data['target'], 'namespace': data['namespace'], 'type': data['type']}

    def dump(self, file: Path) -> None:
        policy_data = {'id': self.id, **asdict(self)}
        with open(file, 'w') as out_file:
            dump(policy_data, out_file, indent=4)

    @classmethod
    def load(cls, file: Path, fix: bool = False) -> Optional[Union[BasePolicy, Policy, PolicyExemption, PolicySet]]:
        with open(file) as in_file:
            try:
                policy_data = load(in_file)
            except JSONDecodeError:
                return
        if fix and policy_data['namespace'] != file.parent.stem:
            policy_data['namespace'] = file.parent.stem
        policy_type = {c.__name__: c for c in BasePolicy.__subclasses__()}[policy_data['type']]
        obj = policy_type(**policy_type.param_map(policy_data))
        if fix and (policy_data.get('id') != obj.id or policy_data['namespace'] != file.parent.stem):
            obj.dump(file)
        return obj

    @staticmethod
    @lru_cache()
    def policy_map(path: Path = None, fix: bool = False, refresh_token: str = '') \
            -> Dict[str, Union[BasePolicy, Policy, PolicyExemption, PolicySet]]:
        def ls_dir(dir_path: Path) -> Generator[Path]:
            for file in dir_path.iterdir():
                if file.is_dir():
                    yield from ls_dir(file)
                else:
                    yield file

        if refresh_token:
            pass
        return {policy.id: policy for file in ls_dir(path or Path(__file__).parent.parent.joinpath('policies'))
                if (policy := BasePolicy.load(file=file, fix=fix))}


@dataclass(frozen=True)
class Policy(BasePolicy):
    allowed: FrozenDict[str, Tuple[str]]
    blocked: FrozenDict[str, Tuple[str]]
    enforced: FrozenDict[str, str]
    possible: Tuple[str]

    @staticmethod
    def param_map(data: dict) -> dict:
        return dict(BasePolicy.param_map(data), **{'allowed': FrozenDict(data.get('allowed', {})),
                                                   'blocked': FrozenDict(data.get('blocked', {})),
                                                   'enforced': FrozenDict(data.get('enforced', {})),
                                                   'possible': tuple(data.get('possible', [])), })

    @cached_property
    def all_params(self) -> Set[str]:
        return set(*(self.allowed.keys()), *(self.blocked.keys()), *(self.enforced.keys()))

    @cached_property
    def is_consistent(self) -> bool:
        if self.possible and any(param not in self.possible for param in self.all_params):
            return False
        if self.enforced and not self.validate(assigned=self.enforced):
            return False
        if self.blocked and any(value in self.allowed.get(param, tuple()) for param, value in self.blocked.items()):
            return False
        return True

    def __add__(self: Policy, other: Policy) -> Policy:
        policy_data = asdict(self)
        # addition logic here
        return Policy(**policy_data)

    def __sub__(self: Policy, other: PolicyExemption) -> Policy:
        policy_data = asdict(self)
        # exemption logic here
        return Policy(**policy_data)

    def apply_policy(self: Policy, policy: Policy) -> Policy:
        return self + policy

    def apply_exemption(self: Policy, exemption: PolicyExemption) -> Policy:
        return self - exemption

    def validate(self, assigned: FrozenDict[str, str]) -> bool:
        return not any((value not in self.allowed.get(param, (value,)) or value in self.blocked.get(param, tuple())
                        or value != self.enforced.get(param, value) or param not in (self.possible or (param,)))
                       for param, value in assigned.items())

    def violations(self, assigned: FrozenDict[str, str]) -> Tuple[str]:
        violations = tuple()
        for param, value in assigned.items():
            if value not in self.allowed.get(param, (value,)):
                violations += '"{}"="{}" not allowed, allowed values are: {}'.format(param, value, self.allowed[param])
            if value in self.blocked.get(param, tuple()):
                violations += '"{}"="{}" is blocked, blocked values are: {}'.format(param, value, self.blocked[param])
            if value != self.enforced.get(param, value):
                violations += '"{}"="{}" is enforced to be "{}"'.format(param, value, self.enforced[param])
            if param not in (self.possible or (param,)):
                violations += 'param "{}" is not possible, possible params are: {}'.format(param, self.possible)
        return violations


@dataclass(frozen=True)
class PolicyExemption(BasePolicy):
    exempted: FrozenDict[str, Tuple[str]]

    @staticmethod
    def param_map(data: dict) -> dict:
        return dict(BasePolicy.param_map(data), **{'exempted': FrozenDict(data.get('exempted', {})), })

    def apply_exemption(self: PolicyExemption, policy: Policy) -> Policy:
        return policy - self


@dataclass(frozen=True)
class PolicySet(BasePolicy):
    policies: Tuple[str]
    exemptions: Tuple[str]

    @staticmethod
    def param_map(data: dict) -> dict:
        return dict(BasePolicy.param_map(data), **{'policies': tuple(data.get('policies', [])),
                                                   'exemptions': tuple(data.get('exemptions', [])), })

    @cached_property
    def policy(self) -> FrozenDict[str, Policy]:
        return FrozenDict({})


@dataclass(frozen=True)
class Config(BasePolicy):
    assigned: FrozenDict[str, str]
    applicable: Tuple[str]

    @staticmethod
    def param_map(data: dict) -> dict:
        return dict(BasePolicy.param_map(data), **{'assigned': tuple(data.get('assigned', [])),
                                                   'applicable': tuple(data.get('applicable', [])), })

    @cached_property
    def config(self) -> FrozenDict[str, str]:
        return FrozenDict({})


@dataclass(frozen=True)
class ConfigSet(BasePolicy):
    assigned: FrozenDict[str, FrozenDict[str, str]]
    applicable: FrozenDict[str, Tuple[str]]

    @staticmethod
    def param_map(data: dict) -> dict:
        return dict(BasePolicy.param_map(data), **{'assigned': FrozenDict(data.get('assigned', {})),
                                                   'applicable': FrozenDict(data.get('applicable', {})), })

    @cached_property
    def config(self) -> FrozenDict[str, FrozenDict[str, str]]:
        return FrozenDict({})


if __name__ == '__main__':
    for pid, p in BasePolicy.policy_map().items():
        print(pid, p)
        p.policy_map()
