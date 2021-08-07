#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
from .policy import list_repo

for policy in list_repo():
    print(policy.type, policy.id)
