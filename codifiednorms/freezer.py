#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Decorator for enforcing typing and Class FrozenDict
"""
import functools
import inspect
import types
import typing


def _find_type_origin(type_hint):
    if isinstance(type_hint, typing._SpecialForm):
        return
    actual_type = typing.get_origin(type_hint) or type_hint
    if isinstance(actual_type, typing._SpecialForm):
        for origins in map(_find_type_origin, typing.get_args(type_hint)):
            yield from origins
    else:
        yield actual_type


def _check_types(parameters, hints):
    for name, value in parameters.items():
        type_hint = hints.get(name, typing.Any)
        actual_types = tuple(_find_type_origin(type_hint))
        if actual_types and not isinstance(value, actual_types):
            raise TypeError(f"Expected type '{type_hint}' for argument '{name}'"
                            f" but received type '{type(value)}' instead")


def enforce_types(callable):
    def decorate(func):
        hints = typing.get_type_hints(func)
        func_signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            parameters = dict(zip(func_signature.parameters, args))
            parameters.update(kwargs)
            _check_types(parameters, hints)

            return func(*args, **kwargs)

        return wrapper

    if inspect.isclass(callable):
        callable.__init__ = decorate(callable.__init__)
        return callable

    return decorate(callable)


def enforce_strict_types(callable):
    def decorate(func):
        hints = typing.get_type_hints(func)
        func_signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound = func_signature.bind(*args, **kwargs)
            bound.apply_defaults()
            parameters = dict(zip(func_signature.parameters, bound.args))
            parameters.update(bound.kwargs)
            _check_types(parameters, hints)

            return func(*args, **kwargs)

        return wrapper

    if inspect.isclass(callable):
        callable.__init__ = decorate(callable.__init__)
        return callable

    return decorate(callable)


class FrozenDict(dict):
    def __init__(self, d: typing.Dict[str, typing.Union[str, typing.Iterable[str]]]):
        super(FrozenDict, self).__init__({
            k: tuple(v) if isinstance(v, list) else FrozenDict(v) if isinstance(v, dict) else v
            for k, v in (
                d if isinstance(d, types.GeneratorType) else d.items() if isinstance(d, dict) else dict(d).items())
        })

    def clear(self) -> None:
        return NotImplemented('FrozenDict Object is Immutable')

    def pop(self, key):
        return NotImplemented('FrozenDict Object is Immutable')

    def popitem(self, *args, **kwargs):
        return NotImplemented('FrozenDict Object is Immutable')

    def setdefault(self, *args, **kwargs):
        return NotImplemented('FrozenDict Object is Immutable')

    def update(self, E=None, **F):
        return NotImplemented('FrozenDict Object is Immutable')

    def __ior__(self, other):
        return NotImplemented('FrozenDict Object is Immutable')

    def __delattr__(self, item):
        return NotImplemented('FrozenDict Object is Immutable')

    def __delitem__(self, key):
        return NotImplemented('FrozenDict Object is Immutable')

    def __setattr__(self, key, value):
        return NotImplemented('FrozenDict Object is Immutable')

    def __setitem__(self, key, value):
        return NotImplemented('FrozenDict Object is Immutable')
