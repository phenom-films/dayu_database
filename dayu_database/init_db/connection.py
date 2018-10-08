# !/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.engine.url import URL
import os
import json
import base
import table


class Connection(object):
    '''
    实际与数据库连接的class。
    绝大多数情况下，用户不应该自己实例化对象。而是应该使用 db.get_session() 直接获得session 即可。
    '''

    def __init__(self,
                 echo=False,
                 isolation_level='READ COMMITTED'):
        # 读取连接配置json文件
        with open(current_path.ancestor(1).child('url_info', 'db_server_ip.json'), 'r') as jf:
            self.connection = URL(**json.load(jf, encoding='utf-8'))
        self.engine = create_engine(self.connection, echo=echo, isolation_level=isolation_level)
        self.scope_session_maker = scoped_session(sessionmaker(bind=self.engine, autoflush=False))
        self.session_maker = sessionmaker(bind=self.engine, autoflush=False)

        # 总是会自动创建table，如果已经存在同名的table 则跳过。
        base.BASE.metadata.create_all(self.engine)


if __name__ == '__main__':
    tt = Connection()
