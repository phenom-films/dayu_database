#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

import os


def init_db(db=None, preset=None):
    import dayu_database
    import base
    import table
    db_obj = dayu_database.get_db(db=db)
    db_obj.connect()
    base.BASE.metadata.create_all(db_obj.engine)

    preset = preset if preset else 'default'
    init_preset_file = os.sep.join([os.path.dirname(os.path.dirname(__file__)),
                                    'static', 'init_db_presets', '{}.json'.format(preset)])

    if not os.path.exists(init_preset_file):
        from dayu_database.error import DayuDatabaseConfigNotExistError
        raise DayuDatabaseConfigNotExistError('no presets when init db: {}'.format(init_preset_file))

    import json
    session = db_obj.session
    with open(init_preset_file, 'r') as jf:
        init_info = json.load(jf)
        for x in init_info:
            print x
            orm_table = getattr(table, x['table'])
            orm = orm_table(**x['data'])
            session.add(orm)
            session.flush()

        session.commit()


if __name__ == '__main__':
    init_db('test')
