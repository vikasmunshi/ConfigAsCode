#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Definition and management of policies as codified norms used for generating target configuration.
"""
from __future__ import annotations
from __future__ import print_function

from dataclasses import asdict, dataclass
from functools import cached_property, lru_cache, reduce
from json import JSONDecodeError, dump, load
from pathlib import Path
from typing import Dict, Generator, Optional, Set, Tuple, Type, TypeVar
from uuid import NAMESPACE_URL, uuid5

from frozen import FrozenDict

__all__ = ['Config', 'Policy', 'PolicyExemption', 'PolicySet', 'PolicyViolation']

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
    def from_dict(cls: Type[T], data: dict) -> T:
        policy_type = {c.__name__: c for c in BasePolicy.__subclasses__()}[data['type']]
        return policy_type(**policy_type.param_map(data))

    @classmethod
    def load(cls: Type[T], file: Path, fix: bool = False) -> Optional[T]:
        with open(file) as in_file:
            try:
                policy_data = load(in_file)
            except JSONDecodeError:
                return
        if fix and policy_data['namespace'] != file.parent.stem:
            policy_data['namespace'] = file.parent.stem
        try:
            obj = cls.from_dict(policy_data)
        except AttributeError:
            return
        if fix and (policy_data.get('id') != obj.id or policy_data['namespace'] != file.parent.stem):
            obj.dump(file)
        return obj

    @staticmethod
    @lru_cache()
    def policy_map(path: Path = None, fix: bool = False) -> Dict[str, T]:
        def ls_dir(dir_path: Path) -> Generator[Path]:
            for file in dir_path.iterdir():
                if file.is_dir():
                    yield from ls_dir(file)
                else:
                    yield file

        return {policy.id: policy for file in ls_dir(path or Path(__file__).parent.parent.joinpath('repository'))
                if (policy := BasePolicy.load(file=file, fix=fix))}

    @classmethod
    def reload_policy_map(cls) -> None:
        cls.policy_map.cache_clear()
        cls.policy_map()

    @classmethod
    def reset_repository(cls) -> None:
        cls.policy_map.cache_clear()
        cls.policy_map(fix=True)

    @classmethod
    def get_policy_by_id(cls: Type[T], policy_id: str) -> Optional[T]:
        return cls.policy_map().get(policy_id, None)


@dataclass(frozen=True)
class Policy(BasePolicy):
    allowed: FrozenDict[str, Tuple[str]]
    blocked: FrozenDict[str, Tuple[str]]
    enforced: FrozenDict[str, str]
    required: Tuple[str]
    possible: Tuple[str]

    @staticmethod
    def param_map(data: dict) -> dict:
        return dict(BasePolicy.param_map(data), **{'allowed': FrozenDict(data.get('allowed', {})),
                                                   'blocked': FrozenDict(data.get('blocked', {})),
                                                   'enforced': FrozenDict(data.get('enforced', {})),
                                                   'required': tuple(data.get('required', [])),
                                                   'possible': tuple(data.get('possible', [])), })

    @cached_property
    def all_params(self) -> Set[str]:
        return set(tuple(self.allowed.keys()) + tuple(self.blocked.keys()) + tuple(self.enforced.keys()))

    @cached_property
    def is_consistent(self) -> bool:
        if self.possible and any(param not in self.possible for param in self.all_params):
            return False
        if self.enforced and not self.validate(assigned=self.enforced):
            return False
        if self.blocked and any(any(value in self.allowed.get(param, tuple()) for value in values)
                                for param, values in self.blocked.items()):
            return False
        return True

    def __post_init__(self):
        if not self.is_consistent:
            c = '; '.join('{}: {}'.format(a, getattr(self, a)) for a in ('allowed', 'blocked', 'enforced', 'possible'))
            raise PolicyViolation('Policy {} ({}) is inconsistent; {}'.format(self.id, self.name, c))

    def __add__(self: Policy, other: Policy) -> Policy:
        if isinstance(self, Policy) and isinstance(other, PolicyExemption):
            return self - other
        if not (isinstance(self, Policy) and isinstance(other, Policy)):
            raise PolicyViolation('Cannot combine type {} with {}'.format(type(self).name, type(other).name))
        if self.target != other.target:
            raise PolicyViolation('Cannot combine target {} with {}'.format(self.target, other.target))
        if ev := [param for param, value in self.enforced.items() if value != other.enforced.get(param, value)]:
            raise PolicyViolation('inconsistent values for enforced Parameters: {}'.format(', '.join(ev)))

        return Policy.from_dict(
            dict(name='{}:{} combined with {}:{}'.format(self.id, self.name, other.id, other.name),
                 version='{}:{} {}:{}'.format(self.id, self.version, other.id, other.version),
                 doc='{}:{} {}:{}'.format(self.id, self.doc, other.id, other.doc), target=self.target,
                 namespace='{}:{} {}:{}'.format(self.id, self.namespace, other.id, other.namespace), type=self.type,
                 allowed={param: (lambda l1, l2: list(set(l1 or l2).intersection(set(l2 or l1))))(
                     self.allowed.get(param), other.allowed.get(param))
                     for param in set(list(self.allowed.keys()) + list(other.allowed.keys()))},
                 blocked={param: list(set(self.blocked.get(param, []) + other.blocked.get(param, [])))
                          for param in set(list(self.blocked.keys()) + list(other.blocked.keys()))},
                 enforced=dict(other.enforced, **self.enforced), required=list(set(self.required + other.required)),
                 possible=[] if not (self.possible and other.possible) else list(set(self.possible + other.possible))))

    def __sub__(self: Policy, other: PolicyExemption) -> Policy:
        if (not isinstance(self, Policy)) or (not isinstance(other, PolicyExemption)):
            raise PolicyViolation('Cannot exempt type {} by {}'.format(type(self).name, type(other).name))
        if self.target != other.target:
            raise PolicyViolation('Cannot exempt target {} with {}'.format(self.target, other.target))

        return Policy.from_dict(
            dict(name='{}:{} with exemptions {}:{}'.format(self.id, self.name, other.id, other.name),
                 version='{}:{} {}:{}'.format(self.id, self.version, other.id, other.version),
                 doc='{}:{} {}:{}'.format(self.id, self.doc, other.id, other.doc), target=self.target,
                 namespace='{}:{} {}:{}'.format(self.id, self.namespace, other.id, other.namespace), type=self.type,
                 allowed={param: list(set(self.allowed.get(param, []) + other.exempted.get(param, [])))
                          for param in set(list(self.allowed.keys()) + list(other.exempted.keys()))},
                 blocked={param: list(value for value in values if value not in other.exempted.get(param, []))
                          for param, values in self.blocked.items()},
                 enforced={param: value for param, value in self.enforced.items() if
                           value != other.exempted.get(param)},
                 required=list(set(self.required) - set(other.exempted.keys())),
                 possible=list(set(list(self.possible) + list(other.exempted.keys()))) if self.possible else []))

    def apply_policy(self: Policy, policy: Policy) -> Policy:
        return self + policy

    def apply_exemption(self: Policy, exemption: PolicyExemption) -> Policy:
        return self - exemption

    def validate(self, assigned: FrozenDict[str, str]) -> bool:
        return not any((value not in self.allowed.get(param, (value,)) or value in self.blocked.get(param, tuple())
                        or value != self.enforced.get(param, value) or param not in (self.possible or (param,)))
                       for param, value in assigned.items())

    def violations(self, assigned: FrozenDict[str, str]) -> Tuple[str]:
        v = tuple()
        for param, value in assigned.items():
            if value not in self.allowed.get(param, (value,)):
                v += '"{}"="{}" not allowed, allowed values are: {}'.format(param, value, self.allowed[param]),
            if value in self.blocked.get(param, tuple()):
                v += '"{}"="{}" is blocked, blocked values are: {}'.format(param, value, self.blocked[param]),
            if value != self.enforced.get(param, value):
                v += '"{}"="{}" is enforced to be "{}"'.format(param, value, self.enforced[param]),
            if param not in (self.possible or (param,)):
                v += 'param "{}" is not possible, possible params are: {}'.format(param, self.possible),
        return v


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
    def policy(self) -> Policy:
        policies = [Policy.get_policy_by_id(policy_id) for policy_id in self.policies]
        exemptions = [Policy.get_policy_by_id(policy_id) for policy_id in self.exemptions]
        return reduce(lambda x, y: x - y, exemptions, reduce(lambda x, y: x + y, policies))


@dataclass(frozen=True)
class Config(BasePolicy):
    assigned: FrozenDict[str, FrozenDict[str, str]]
    applicable: Tuple[str]

    @staticmethod
    def param_map(data: dict) -> dict:
        return dict(BasePolicy.param_map(data), **{'assigned': FrozenDict(data.get('assigned', {})),
                                                   'applicable': tuple(data.get('applicable', tuple())), })

    @cached_property
    def policy(self) -> FrozenDict[str, Policy]:
        policies, exemptions = {}, {}
        for policy in (BasePolicy.get_policy_by_id(policy_id) for policy_id in self.applicable):
            if isinstance(policy, Policy):
                policies.setdefault(policy.target, [])
                policies[policy.target] += [policy]
            elif isinstance(policy, PolicySet):
                policies.setdefault(policy.policy.target, [])
                policies[policy.target] += [policy.policy]
            elif isinstance(policy, PolicyExemption):
                exemptions.setdefault(policy.target, [])
                exemptions[policy.target] += [policy]
            else:
                print('unknown type'.format(type(policy).name))

        return FrozenDict({target: PolicySet.from_dict(dict(
            name=self.name,
            version=self.version,
            doc=self.doc,
            target=target,
            namespace=self.namespace,
            type='PolicySet',
            policies=policies[target],
            exemptions=exemptions.get(target, tuple()),
        )).policy for target in policies.keys()})

    @cached_property
    def config(self) -> FrozenDict[str, FrozenDict[str, str]]:
        return FrozenDict({})

    @cached_property
    def is_consistent(self) -> bool:
        return not any((target not in self.policy or not self.policy[target].is_consistent)
                       for target in self.config.keys())

    @cached_property
    def validate(self) -> bool:
        return (not self.is_consistent) and \
               (not any(not self.policy[target].validate(assigned) for target, assigned in self.config.items()))

    @cached_property
    def violations(self) -> Tuple[str]:
        if self.validate:
            return tuple()
        v = tuple()
        for target, assigned in self.config.items():
            if target not in self.policy:
                v += 'policy not defined for target {}'.format(target),
            else:
                v += self.policy[target].violations(assigned)
        return v


if __name__ == '__main__':
    BasePolicy.reload_policy_map()
    for pid, p in BasePolicy.policy_map().items():
        print(pid, p)
        p.policy_map()
