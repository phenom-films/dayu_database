#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

import os
import threading

from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker

import dayu_path_patch
from config.const import DAYU_DB_NAME, DAYU_CONFIG_STATIC_PATH
from config import DayuDatabaseConfig
from status import DayuDatabaseStatusNotConnect, DayuDatabaseStatusConnected
from deco import lazy

_database_context = {}


def get_session(db=None):
    db_instance = get_db(db)
    if db_instance.status is DayuDatabaseStatusNotConnect:
        from error import DayuDatabaseNotConnectError
        raise DayuDatabaseNotConnectError('database not connect! please run .connect() before get_session()')
    return db_instance.session


def get_db(db=None):
    current_threading_id = id(threading.current_thread())
    db = db or os.environ.get(DAYU_DB_NAME, None) or 'default'
    db_instance = _database_context.get(current_threading_id, {}).get(db, None)
    if db_instance is None:
        db_instance = DayuDatabase(db=db)
    return db_instance


class DayuDatabase(object):
    config = None
    status = DayuDatabaseStatusNotConnect

    def __new__(cls, db=None):
        db = db or os.environ.get(DAYU_DB_NAME, None) or 'default'
        current_threading_id = id(threading.current_thread())
        instance = _database_context.get(current_threading_id, {}).get(db, None)
        if instance:
            return instance

        instance = super(DayuDatabase, cls).__new__(cls, db=db)
        instance.status = DayuDatabaseStatusNotConnect
        instance.config = DayuDatabaseConfig(parent=instance)
        instance.config.update(DAYU_DB_NAME=db)
        current_threading_db = _database_context.setdefault(current_threading_id, {})
        current_threading_db[db] = instance
        return instance

    def __init__(self, db=None):
        pass

    def connect(self):
        if self.status is DayuDatabaseStatusConnected:
            return self

        db = self.config.get(DAYU_DB_NAME, 'default')
        db_url_file = os.sep.join((self.config.get(DAYU_CONFIG_STATIC_PATH, ''), 'db_url', db + '.json'))

        if not os.path.exists(db_url_file):
            from error import DayuDatabaseConfigNotExistError
            raise DayuDatabaseConfigNotExistError('no database config file: {}'.format(db_url_file))

        import json
        with open(db_url_file, 'r') as jf:
            self.url = URL(**json.load(jf))

        self.engine = create_engine(self.url, echo=False, isolation_level='READ COMMITTED')
        current_threading_db = _database_context.setdefault(id(threading.current_thread()), {})
        current_threading_db[db] = self
        self.status = DayuDatabaseStatusConnected
        return self

    @lazy
    def session(self):
        if self.status is DayuDatabaseStatusNotConnect:
            from error import DayuDatabaseNotConnectError
            raise DayuDatabaseNotConnectError('database not connect! please run .connect() before get_session()')

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
