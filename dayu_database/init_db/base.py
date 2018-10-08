#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

from sqlalchemy import Column, BigInteger, String, Boolean, Integer
from sqlalchemy.event import listens_for
from sqlalchemy.ext.declarative import as_declarative, declared_attr

from dayu_database.util import snowflake, current_user_name


@as_declarative()
class BASE(object):
    '''
    所有ORM 的基类
    '''

    @declared_attr
    def __tablename__(cls):
        '''
        满足 sqlalchemy 需要的__tablename__
        总是使用class.name 的小写
        :return: string
        '''
        return cls.__name__.lower()

    # 数据库主键，会使用snowflake 算法生成64 bit 的int
    id = Column(BigInteger, primary_key=True, index=True)
    # orm 的名字用于后台的处理
    name = Column(String)
    # orm 的显示名，主要用于GUI 显示
    label = Column(String)
    # api 不负责真正的删除，只会将对应的row 标记为False，用来区别是否存在
    active = Column(Boolean, default=True)
    # 各种flag 标识，目前没有使用
    flag = Column(Integer, default=0)


@listens_for(BASE, 'init', propagate=True)
def base_init_guid(target, args, kwargs):
    '''
    sqlalchemy 的事件监听。
    在实例化任何orm的时候，使用snowflake 的方式生成数据库64 bit int 的主键。
    （用户永远不应该自己输入id）
    :param target: 监听截获的orm 对象
    :param args:
    :param kwargs:
    :return: None
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
