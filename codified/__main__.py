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
    print(any_value)
    print(v := Value('val1'), v == any_value)
    t = Target(target='target_one')
    t.write()
    # p = Param('param1')
    # p.write()
    # p1 = Param.read('codified.param_param1')
    # p1.write()
    any_value.write()
    all_values.write()
    no_values.write()
    print('instances', RepoCachedAttrs.__instances__)
    print('types', RepoCachedAttrs.__types__)
    Target('some target', params=['param1', 'param2']).write()
