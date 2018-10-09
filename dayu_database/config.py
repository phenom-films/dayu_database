#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

DAYU_DB_ROOT_FOLDER_NAME = '.!0x5f3759df_this_is_a_magic_number_used_for_telling_which_atom_is_the_root'

DAYU_DB_NAME = 'DAYU_DB_NAME'
DAYU_APP_NAME = 'DAYU_APP_NAME'

# 所有可能的分支条件，用于批量创建json config 的成绩结构。用户也可以通过手动创建文件的方式进行添加。
DECISION_TREE = [['maya', 'nuke', 'houdini', 'hiero'],
                 ['default'],
                 ['element', 'workfile', 'cache', 'dailies'],
                 ['plt', 'mod', 'cam', 'ani', 'pcmp', 'tmw'],
                 ['create', 'export']]
