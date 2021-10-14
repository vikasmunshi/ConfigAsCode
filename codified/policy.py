#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Policy class for specifying configuration as a codified policy
"""
from __future__ import annotations

import typing

T = typing.TypeVar('T')
ValueType = typing.Union[bool, int, str, type(None)]
ValuesType = typing.Tuple[ValueType]
ValuesInputType = typing.Iterable[ValueType]

Any = type('Any', (object,), {'__contains__': lambda self, item: True, '__repr__': lambda self: 'Any'})()


class PolicyMeta(type):
    param = 'param'
    policy_id = 'policy_id'
    doc = 'doc'
    allowed = 'allowed'
    blocked = 'blocked'
    __classes__ = {}
    __instances__ = {}

    def __new__(mcs, name: str, bases: typing.Tuple, dct: dict):
        if name in mcs.__classes__:
            raise NotImplementedError('Class redefinition is not allowed!!!')
        mcs.__instances__[name], mcs.__classes__[name] = {}, super().__new__(mcs, name, bases, dct)
        return mcs.__classes__[name]

    def __call__(cls, *args, **kwargs):
        obj = super().__call__(*args, **kwargs)
        class_name, param, policy_id = cls.__name__, obj.param, obj.policy_id
        if param in cls.__instances__[class_name]:
            if policy_id in cls.__instances__[class_name][param]:
                if not (existing_obj := cls.__instances__[class_name][param][policy_id]) == obj:
                    raise NotImplementedError('Policy redefinition is not allowed!!!')
                return existing_obj
            cls.__instances__[class_name][param][policy_id] = obj
        else:
            cls.__instances__[class_name][param] = {policy_id: obj}
        return obj

    def from_dict(cls, dct: dict) -> T:
        dct = dct.copy()
        return cls.__classes__.get(dct.pop('namespace', cls.__name__))(**dct)

    @property
    def policies(cls) -> typing.Dict[str, typing.Dict[str, Policy]]:
        return cls.__instances__[cls.__name__]

    @classmethod
    def list(mcs, path: str = None) -> dict:
        result = mcs.__instances__
        for path_element in (path.split('.') if path else []):
            result = result.get(path_element, {})
        return result

    def check_policies(cls, param: str, value: ValueType) -> typing.Optional[bool]:
        if policies := cls.policies.get(param):
            return all(p.check_policy(value) for p in policies.values())

    def explain_policies(cls, param: str, value: ValueType) -> str:
        legend = {True: 'passed', False: 'failed'}
        return '\n'.join(f'{p}:{value}:{legend[p.check_policy(value)]}' for p in cls.policies.get(param, {}).values()) \
               or f'{cls.__name__}:{param}:no policy'

    def define(cls, *policy_definitions: typing.Dict) -> typing.Tuple[Policy, ...]:
        return tuple(cls.from_dict(policy_definition) for policy_definition in policy_definitions)


class Policy(metaclass=PolicyMeta):
    def __init__(self, *, param: str, policy_id: str = None, doc: str = None,
                 allowed: ValuesInputType = Any, blocked: ValuesInputType = None):
        self.policy_id = policy_id if policy_id is not None \
            else f'{self.__class__.__name__}_{len(self.__class__.policies.get(param, {}))}'
        self.namespace = self.__class__.__name__
        self.param = param
        self.allowed = Any if (allowed == 'Any' or allowed is Any) else tuple(set(allowed))
        self.blocked = tuple(set(blocked)) if blocked is not None else tuple()
        self.doc = doc if doc is not None else self.__class__.doc if hasattr(self.__class__, 'doc') else ''

    @property
    def as_dict(self):
        return dict({k: v for k, v in self.__class__.__dict__.items() if not k.startswith('__')}, **self.__dict__)

    def check_policy(self, value: ValueType) -> bool:
        return value in self.allowed and value not in self.blocked

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(f'{k}={v}' for k, v in self.as_dict.items())})"

    def __eq__(self, other: Policy) -> bool:
        return self is other or all(v == getattr(self, k) for k, v in other.as_dict.items())


class ASRPolicy(Policy):
    doc = 'some doc'


class AuthPolicy(Policy):
    pass


class SpecificAuthPolicy(AuthPolicy):
    pass


if __name__ == '__main__':
    print(asr := ASRPolicy(param='p1', doc='other doc'))
    print(p := asr.as_dict)
    print(ASRPolicy.from_dict(p))
    print('p', p)
    print(ASRPolicy.define({ASRPolicy.param: 'p3', ASRPolicy.allowed: Any},
                           {ASRPolicy.param: 'p4'},
                           {ASRPolicy.param: 'p5'}))
    print(ASRPolicy.check_policies('p1', 'some value'))
    print(ASRPolicy.explain_policies('p1', 'some value'))
    print(ASRPolicy.check_policies('p2', 'some value'))
    print(ASRPolicy.explain_policies('p2', 'some value'))
    print(Policy.policies)
    print(ASRPolicy.policies)
    print(Policy.list('ASRPolicy.p1'))
    print(Policy.list())
