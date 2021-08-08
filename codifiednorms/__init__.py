#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Manage "Codified Norms" and "Config as Code"
"""
__package__ = 'codifiednorms'
__version__ = '0.2.20210809'

from .policy import *

__all__ = ['Config', 'Policy', 'PolicySet']
