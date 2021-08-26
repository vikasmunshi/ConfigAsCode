#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Class for basic variable types
"""
from __future__ import annotations

import typing

import attr

try:
    from .repo import RepoCachedAttrs
except ImportError:
    from repo import RepoCachedAttrs

T = typing.TypeVar('T')

is_optional_str = attr.validators.optional(attr.validators.instance_of(str))


def is_tuple_of(t: typing.Type[T]):
    attr.validators.deep_iterable(attr.validators.instance_of(t), attr.validators.instance_of(tuple))


class AnyStr(str):
    def __eq__(self, other: str) -> bool:
        return True

    def __ne__(self, other: str) -> bool:
        return False


# @attr.s(frozen=True)
# class Value(RepoCachedAttrs):
#     value = attr.ib(type=typing.Optional[typing.Union[bool, int, str]],
#                     validator=attr.validators.optional(attr.validators.instance_of((bool, int, str))))
#
#     def __matmul__(self: Value, other: Policy) -> bool:
#         """ Value @ Policy """
#         return self.value in other.allowed and self.value not in other.denied

#
# @attr.s(frozen=True, cmp=False)
# class AnyValue(Value):
#     value = attr.ib(init=False, repr=False, cmp=False, default=AnyStr())
#
#     def __eq__(self, other: Value) -> bool:
#         return True
#
#     def __ne__(self, other: Value) -> bool:
#         return False

#
# @attr.s(frozen=True)
# class Values(RepoCachedAttrs):
#     values = attr.ib(type=typing.Tuple[Value, ...], converter=lambda v: tuple(v), factory=tuple,
#                      validator=is_tuple_of(Value))
#
#     def __iter__(self):
#         yield from self.values
#
#     def __contains__(self, item: Value) -> bool:
#         return item.value in self.values
#
#     def __add__(self: Values, other: Values) -> Values:
#         """ add values, return values that are in either i.e. union of sets"""
#         if isinstance(self.values, AllValues):
#             values = self.values
#         elif isinstance(other.values, AllValues):
#             values = other.values
#         else:
#             values = self.values + tuple(v for v in other.values if v not in self.values)
#         return attr.evolve(self, id=None, doc=f'{self.id}(+){other.id}', values=values)
#
#     def __sub__(self: Values, other: Values) -> Values:
#         """ remove values from self that are also in other"""
#         if isinstance(self.values, AllValues):
#             values = self.values
#         elif isinstance(other.values, AllValues):
#             values = tuple()
#         else:
#             values = tuple(v for v in self.values if v not in other.values)
#         return attr.evolve(self, id=None, doc=f'{self.id}(-){other.id}', values=values)
#
#     def __mod__(self: Values, other: Values) -> Values:
#         """ return values that are in both i.e. intersection of sets"""
#         if isinstance(self.values, AllValues):
#             values = other.values
#         elif isinstance(other.values, AllValues):
#             values = self.values
#         else:
#             values = tuple(v for v in self.values if v in other.values)
#         return attr.evolve(self, id=None, doc=f'{self.id}(%){other.id}', values=values)
#
#
# @attr.s(frozen=True, cmp=False)
# class AllValues(Values):
#     values = attr.ib(init=False, repr=False, cmp=False, default=(AnyValue(),))
#
#     def __contains__(self, item: Value) -> bool:
#         return True
#
#     def __eq__(self, other: Values) -> bool:
#         return True
#
#     def __ne__(self, other: Values) -> bool:
#         return False


@attr.s(frozen=True, kw_only=True)
class Target(RepoCachedAttrs):
    target = attr.ib(type=str, validator=attr.validators.instance_of(str))
    uri = attr.ib(type=str, cmp=False, default=None, validator=is_optional_str)


@attr.s(frozen=True, kw_only=True)
class Param(Target):
    param = attr.ib(type=str, validator=attr.validators.instance_of(str))


@attr.s(frozen=True, kw_only=True)
class Params(Target):
    params = attr.ib(type=typing.Tuple[str, ...], converter=lambda v: tuple(v), validator=is_tuple_of(str))


@attr.s(frozen=True)
class Config(Target):
    config = attr.ib(type=dict[str, Value],
                     converter=lambda d: {k: v if isinstance(v, Value) else Value(v) for k, v in d.items()})


@attr.s(frozen=True)
class Policy(RepoCachedAttrs):
    applies_to = attr.ib(type=Param, validator=attr.validators.instance_of(Param))
    allowed = attr.ib(type=Values, validator=attr.validators.instance_of(Values))
    denied = attr.ib(type=Values, validator=attr.validators.instance_of(Values))

    def __add__(self: Policy, other: Policy) -> Policy:
        if self.applies_to == other.applies_to:
            denied = self.denied + other.denied
            allowed = (self.allowed % other.allowed) - denied
            return attr.evolve(self, id=None, doc=f'{self.id}(+){other.id}', allowed=allowed, denied=denied)
        return self

    def __sub__(self: Policy, other: Policy) -> Policy:
        if self.applies_to == other.applies_to:
            allowed = self.allowed + other.allowed
            denied = self.denied - other.allowed
            return attr.evolve(self, id=None, doc=f'{self.id}(-){other.id}', allowed=allowed, denied=denied)
        return self


@attr.s(frozen=True)
class Policies(RepoCachedAttrs):
    policies = attr.ib(type=typing.Tuple[Policy, ...], converter=lambda v: tuple(v), factory=tuple,
                       validator=is_tuple_of(Policy))

    def __add__(self: Policies, other: Policies) -> Policies:
        policies = self.policies + tuple(p for p in other.policies if p not in self.policies)
        return attr.evolve(self, id=None, doc=f'{self.id}(-){other.id}', policies=policies)


@attr.s(frozen=True)
class AllAllowedPolicy(Policy):
    allowed = attr.ib(init=False, factory=AllValues)
    denied = attr.ib(init=False, factory=Values)


@attr.s(frozen=True)
class AllDeniedPolicy(Policy):
    allowed = attr.ib(init=False, factory=Values)
    denied = attr.ib(init=False, factory=AllValues)
