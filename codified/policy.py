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
            dct['namespace'], mcs.repo[name] = name, tuple()
        return super().__new__(mcs, name, bases, dct)

    def from_dict(cls, dct: dict) -> T:
        obj_class = globals().get(dct.get('namespace', cls.__name__))
        return obj_class(param=dct['param'], allowed=dct['allowed'], blocked=dct['blocked'])

    @property
    def policies(cls) -> typing.Tuple[Policy]:
        return cls.repo[cls.namespace]

    def check(cls, param: str, value: ValueType) -> typing.Optional[bool]:
        if policies := [p for p in cls.policies if p.param == param]:
            return all(value in p.allowed and value not in p.blocked for p in policies)

    def explain(cls, param: str, value: ValueType) -> typing.Optional[str]:
        legend = {True: 'passed', False: 'failed'}
        return '\n'.join(f'{p}: {legend[value in p.allowed and value not in p.blocked]}'
                         for p in cls.policies if p.param == param) or None


class Policy(metaclass=PolicyMeta):
    def __init__(self, param: str, allowed: ValuesInputType = Any, blocked: ValuesInputType = None, id: str = None):
        if self.__class__ is Policy:
            raise NotImplementedError('Must be subclassed!')
        self.id = id if id is not None else f'{self.__class__.__name__}_{len(self.__class__.policies) + 1}'
        self.param = param
        self.allowed = Any if (allowed == 'Any' or allowed is Any) else set(allowed)
        self.blocked = set(blocked) if blocked is not None else set()
        self.__class__.repo[self.__class__.namespace] += (self,)

    def as_dict(self) -> dict:
        # noinspection PyUnboundLocalVariable
        return {a: v for a in dir(self) if (not a.startswith('__') and not callable(v := getattr(self, a)))}

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(f'{k}={v}' for k, v in self.__dict__.items())})"
