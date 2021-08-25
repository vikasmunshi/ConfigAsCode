#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
CLI for package codified
"""
try:
    from .variables import *
except ImportError:
    from variables import *

if __name__ == '__main__':
    base = RepoCachedAttrs.read('some')
    print(base, base.id)
    base.write()
    print(RepoCachedAttrs.__instances__)
    print(RepoCachedAttrs.__types__)
    print(AllValues().as_dict)
    print(AnyValue().as_dict)
