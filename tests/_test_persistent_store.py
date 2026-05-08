#!/usr/bin/env python
# coding=utf-8

"""
@author: zgw
@date: 2026/5/7 19:51
@source from: 
"""
from llm_base.persistent_store import PersistentStore

a = PersistentStore()
print('success!')

print(a.session_exists("bfdfc3a8-6028-47ba-9678-11cedc824528"))




