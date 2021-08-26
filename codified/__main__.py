#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
CLI for package codified
"""
try:
    from .repo import *
except ImportError:
    from repo import *

if __name__ == '__main__':
    base = RepoCachedAttrs.read('some')
    print(base, base.id)
    base.write()
    print(RepoCachedAttrs.__instances__)
    print(RepoCachedAttrs.__types__)
    print(any_value)
    print(v := Value('val1'), v == any_value)
    any_value.write()
    all_values.write()
    print(t := Target(target='target_one'))
    t.write()
    p1 = Param.read('codified.param_param1')
    p1.write()
