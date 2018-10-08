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


def get_session(name=None):
    return DayuDatabase(name).session


class DayuDatabase(object):
    def __new__(cls, name=None):
        name = name or os.environ.get(DAYU_DB_NAME, None) or 'default'
        if name in _database_context:
            return _database_context[name]
        instance = super(DayuDatabase, cls).__new__(cls, name=name)
        _database_context[name] = instance
        return instance

    def __init__(self, name=None):
        name = name or os.environ.get(DAYU_DB_NAME, None) or 'default'
        db_url_file = os.sep.join((os.path.dirname(__file__), 'static', 'db_url', name + '.json'))

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

    aa = session.query(FOLDER).first()
    # print aa.test()
    print aa
