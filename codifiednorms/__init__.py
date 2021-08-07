#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
try:
    from .policy import *
except ImportError:
    from policy import *
__package__ = 'codifiednorms'
__version__ = '0.1.20210817'
__all__ = ['Config', 'Policy', 'PolicySet', 'list_repo', 'fix_repo']
