#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

DAYU_DB_ROOT_FOLDER_NAME = '.!0x5f3759df_this_is_a_magic_number_used_for_telling_which_atom_is_the_root'

DAYU_DB_NAME = 'DAYU_DB_NAME'
DAYU_APP_NAME = 'DAYU_APP_NAME'
DAYU_CONFIG_STATIC_PATH = 'DAYU_CONFIG_STATIC_PATH'

# 所有可能的分支条件，用于批量创建json config 的成绩结构。用户也可以通过手动创建文件的方式进行添加。
DECISION_TREE = [['maya', 'nuke', 'houdini', 'hiero'],
                 ['default'],
                 ['element', 'workfile', 'cache', 'dailies'],
                 ['plt', 'mod', 'cam', 'ani', 'pcmp', 'tmw'],
                 ['create', 'export']]


class DayuDatabaseStatusNotConnect(object):
    pass


class DayuDatabaseStatusConnected(object):
    pass


class DayuDatabaseConfig(dict):
    def __setitem__(self, key, value):
        if self['parent'].status is DayuDatabaseStatusNotConnect:
            super(DayuDatabaseConfig, self).__setitem__(key, value)
        else:
            from error import DayuDatabaseConfigChangedAfterConnect
            raise DayuDatabaseConfigChangedAfterConnect('cannot change config after database connected!')

    def update(self, **kwargs):
        if self['parent'].status is DayuDatabaseStatusNotConnect:
            super(DayuDatabaseConfig, self).update(**kwargs)
        else:
            from error import DayuDatabaseConfigChangedAfterConnect
            raise DayuDatabaseConfigChangedAfterConnect('cannot change config after database connected!')

    def pop(self, k):
        if self['parent'].status is DayuDatabaseStatusNotConnect:
            return super(DayuDatabaseConfig, self).pop(k)
        else:
            from error import DayuDatabaseConfigChangedAfterConnect
            raise DayuDatabaseConfigChangedAfterConnect('cannot change config after database connected!')

    def popitem(self):
        if self['parent'].status is DayuDatabaseStatusNotConnect:
            return super(DayuDatabaseConfig, self).popitem()
        else:
            from error import DayuDatabaseConfigChangedAfterConnect
            raise DayuDatabaseConfigChangedAfterConnect('cannot change config after database connected!')

    def setdefault(self, k, default=None):
        if self['parent'].status is DayuDatabaseStatusNotConnect:
            return super(DayuDatabaseConfig, self).setdefault(k, default)
        else:
            from error import DayuDatabaseConfigChangedAfterConnect
            raise DayuDatabaseConfigChangedAfterConnect('cannot change config after database connected!')

    def __init__(self, **kwargs):
        import os
        super(DayuDatabaseConfig, self).__init__(**kwargs)
        self[DAYU_DB_NAME] = kwargs.get(DAYU_DB_NAME, None) or \
                             os.environ.get(DAYU_DB_NAME, None) or \
                             'default'
        self[DAYU_CONFIG_STATIC_PATH] = kwargs.get(DAYU_CONFIG_STATIC_PATH, None) or \
                                        os.environ.get(DAYU_CONFIG_STATIC_PATH, None) or \
                                        os.sep.join([os.path.dirname(__file__), 'static'])

    def from_json(self, path):
        import json
        with open(path, 'r') as jf:
            self.update(json.load(jf))

    def from_env(self):
        import os
        for k in self:
            self[k] = os.environ.get(k, self[k])

    def from_mapping(self, **kwargs):
        self.update(kwargs)


if __name__ == '__main__':
    config = DayuDatabaseConfig()
    print config
