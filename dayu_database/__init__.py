#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

import os

from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker

from config import DAYU_DB_NAME
from deco import lazy

_database_context = {}


def get_session(db=None):
    return DayuDatabase(db).session


class DayuDatabase(object):
    def __new__(cls, db=None):
        import threading
        db = db or os.environ.get(DAYU_DB_NAME, None) or 'default'
        current_threading_id = id(threading.current_thread())
        uid = '{}_{}'.format(db, current_threading_id)
        if uid in _database_context:
            return _database_context[uid]
        instance = super(DayuDatabase, cls).__new__(cls, name=db)
        _database_context[uid] = instance
        return instance

    def __init__(self, db=None):
        db = db or os.environ.get(DAYU_DB_NAME, None) or 'default'
        db_url_file = os.sep.join((os.path.dirname(__file__), 'static', 'db_url', db + '.json'))

        if not os.path.exists(db_url_file):
            from error import DayuDatabaseConfigNotExistError
            raise DayuDatabaseConfigNotExistError('no database config file: {}'.format(db_url_file))

        import json
        with open(db_url_file, 'r') as jf:
            self.url = URL(**json.load(jf))

        self.engine = create_engine(self.url, echo=False, isolation_level='READ COMMITTED')

    @lazy
    def session(self):
        import base
        import auto_naming
        import sqlalchemy.event
        self.session_maker = sessionmaker(bind=self.engine, autoflush=False)
        base.BASE.prepare(self.engine,
                          reflect=True,
                          classname_for_table=auto_naming._classname_for_table,
                          name_for_collection_relationship=auto_naming._name_for_collection_relationship,
                          name_for_scalar_relationship=auto_naming._name_for_scalar_relationship,
                          generate_relationship=auto_naming._generate_relationship)

        _session = self.session_maker()

        @sqlalchemy.event.listens_for(_session, 'after_commit')
        def event_after_commit(session):
            print 'db commit completed'
            # net_log.get_logger().info('db commit completed')

        return _session


if __name__ == '__main__':
    session = get_session()
    from table import *

    aa = session.query(FILE).get(1148725585083440309)
    # print aa.test()
    print aa.disk_path()
    print type(aa.sub_level)
    # print aa.path_data
    for x in aa.sub_level.walk():
        print x
