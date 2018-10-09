#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'
__doc__ = \
    '''
    这里将数据API 改为反射式。
    利用sqlalchemy 的automap 来实现。
    
    但是由于数据库内部采用无外键的设计，因此不能够正常的生成所有的relationship（除了 many to many）
    因此需要使用事先明确定义基础信息的方式。基础的信息包括：
    
    * 各种table 对应的mapper class
    * 如果某些column 需要有default 默认行为 或者 一些unique、index 约束的话，需要明确声明
    * orm relationship 
    
    其他数据库自行添加的column 会自动反射成为mapper class 的属性。
    
    
    '''

from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.event import listens_for
from util import snowflake, current_user_name


@as_declarative()
class DECALARE_BASE(object):

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    def to_string(self):
        from pprint import pformat
        return str('<{0}> '.format(self.__tablename__) + \
                   pformat({c.name: getattr(self, c.name, None) for c in self.__table__.columns}) + '\n')

    def __repr__(self):
        '''
        重载orm 的打印内容
        :return: string
        '''
        return u'<{class_name}>({orm_id}, {orm_name})'.format(class_name=self.__class__.__name__,
                                                              orm_id=self.id,
                                                              orm_name=self.name)


# 创建Automap 的反射基类
BASE = automap_base(DECALARE_BASE)


@listens_for(BASE, 'init', propagate=True)
def base_init_guid(target, args, kwargs):
    '''
    自动生成id，可以保证在flush 之前就让orm 得到全局唯一的id。
    （具体算法，可以参考twitter 的snowflake 算法）

    :param target: orm 对象
    :param args:
    :param kwargs:
    :return:
    '''
    if hasattr(target, 'id') and target.id is None:
        target.id = snowflake()


@listens_for(BASE, 'before_update', propagate=True)
def base_updated_user_name(mapper, connection, target):
    '''
    sqlalchemy 的事件监听。
    在任何orm 将要更新数据库的时候，将修改用户的用户名同时写入数据库。
    :param mapper:
    :param connection:
    :param target: 监听获得的orm 对象
    :return: None
    '''
    if hasattr(target, 'updated_by_name'):
        target.updated_by_name = current_user_name()


# 在真正调用prerpare() 函数进行反射之前，先导入所有预先明确定义的table mapper class。
# 这样才能实现反射的同时，还带有自定义的各种属性（例如hook property）
from table import *
