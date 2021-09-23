#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Policy class for specifying configuration as a codified policy
"""
from __future__ import annotations

import typing

T = typing.TypeVar('T')
ValueType = typing.Union[bool, int, str, type(None)]
ValuesType = typing.Set[ValueType]
ValuesInputType = typing.Iterable[ValueType]


class Any:
    def __contains__(self, item: typing.Any) -> bool:
        return True

    def __repr__(self):
        return 'Any'


Any = Any()


class PolicyMeta(type):
    repo = {}
    namespace: str

    def __new__(mcs, name: str, bases: typing.Tuple, dct: dict):
        if bases:
            dct['namespace'], mcs.repo[name] = name, {}
        return super().__new__(mcs, name, bases, dct)

    def __call__(cls, *args, **kwargs):
        policy = super().__call__(*args, **kwargs)
        if (param := policy.param) not in cls.repo[cls.namespace]:
            cls.repo[cls.namespace][param] = {}
        cls.repo[cls.namespace][param][policy.id] = policy
        return policy

    def from_dict(cls, dct: dict) -> T:
        obj_class = globals().get(dct.get('namespace', cls.__name__))
        return obj_class(param=dct['param'], allowed=dct.get('allowed', Any), blocked=dct.get('blocked', set()))

    @property
    def policies(cls) -> typing.Dict[str, typing.Dict[str, Policy]]:
        return cls.repo[cls.namespace]

    def check_policies(cls, param: str, value: ValueType) -> typing.Optional[bool]:
        if policies := cls.policies.get(param):
            return all(p.check_policy(value) for p in policies.values())

    def explain_policies(cls, param: str, value: ValueType) -> str:
        legend = {True: 'passed', False: 'failed'}
        return '\n'.join(f'{p}:{value}:{legend[p.check_policy(value)]}' for p in cls.policies.get(param, {}).values()) \
               or f'{cls.namespace}:{param}:no policy'


class Policy(metaclass=PolicyMeta):
    def __init__(self, param: str, allowed: ValuesInputType = Any, blocked: ValuesInputType = None, id: str = None):
        if self.__class__ is Policy:
            raise NotImplementedError('Must be subclassed!')
        self.id = id if id is not None else f'{self.__class__.__name__}_{len(self.__class__.policies.get(param, {}))}'
        self.param = param
        self.allowed = Any if (allowed == 'Any' or allowed is Any) else set(allowed)
        self.blocked = set(blocked) if blocked is not None else set()

    def check_policy(self, value: ValueType) -> bool:
        return value in self.allowed and value not in self.blocked

    def as_dict(self) -> dict:
        # noinspection PyUnboundLocalVariable
        return {a: v for a in dir(self) if (not a.startswith('__') and not callable(v := getattr(self, a)))}

    def __repr__(self):
        vals = ', '.join(f'{k}={v}' for k, v in self.as_dict().items())
        return f'{self.__class__.__name__}({vals})'
