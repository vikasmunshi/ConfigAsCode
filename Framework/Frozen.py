#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Immutable dictionary
"""
from types import GeneratorType
from typing import Dict, List, Union


class PolicyViolation(Exception):
    def __init__(self):
        super(PolicyViolation, self).__init__('FrozenDict Object is Immutable')


class FrozenDict(dict):
    def __init__(self, d: Dict[str, Union[str, List[str]]]):
        super(FrozenDict, self).__init__({
            k: tuple(v) if isinstance(v, list) else FrozenDict(v) if isinstance(v, dict) else v
            for k, v in (d if isinstance(d, GeneratorType) else d.items() if isinstance(d, dict) else dict(d).items())})

    def clear(self) -> None:
        raise PolicyViolation()

    def pop(self, key):
        raise PolicyViolation()

    def popitem(self, *args, **kwargs):
        raise PolicyViolation()

    def setdefault(self, *args, **kwargs):
        raise PolicyViolation()

    def update(self, E=None, **F):
        raise PolicyViolation()

    def __ior__(self, other):
        raise PolicyViolation()

    def __delattr__(self, item):
        raise PolicyViolation()

    def __delitem__(self, key):
        raise PolicyViolation()

    def __setattr__(self, key, value):
        raise PolicyViolation()

    def __setitem__(self, key, value):
        raise PolicyViolation()
