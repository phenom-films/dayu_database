#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'
__doc__ = \
    '''
    这里主要是为了和 Finder 上的Search 配合使用。
    
    本质上就是完成了下面的基本步骤：
    1. 用户在UI 上通过控件，选择需要的过滤条件
    2. 用户保存search 的时候，前端将过滤条件保存成为json 形式的描述
    3. 生成一个 SEARCH orm，写入数据库
    
    同时，通过sqlalchemy 的inspect 动态的解析orm 的属性，判断是否是relationship，方便前端进行选择。
    
    '''

import re
import datetime
import collections

from sqlalchemy import and_, or_, not_, inspect
from sqlalchemy.orm.properties import RelationshipProperty, ColumnProperty
import util

# 关键字函数定义
LOGIC_SWITCH = {'and': and_,
                'or' : or_,
                'not': not_}

# 给前端的对应关系，每个tuple 中，第一个是前端显示使用，后一个是后台的函数定义名称
OPERATION_SWITCH = {'VARCHAR' : collections.OrderedDict((('is', 'eq'), ('like', 'like'), ('is not', 'ne'),
                                                         ('contain', 'in'), ('not contain', 'not_in'))),
                    'INTEGER' : collections.OrderedDict((('is', 'eq'), ('like', 'like'), ('is not', 'ne'),
                                                         ('less than', 'lt'), ('greater than', 'gt'),
                                                         ('less equal', 'le'), ('greater than', 'ge'),
                                                         ('contain', 'in'), ('not contain', 'not_in'))),
                    'BIGINT'  : collections.OrderedDict((('is', 'eq'), ('like', 'like'), ('is not', 'ne'),
                                                         ('less than', 'lt'), ('greater than', 'gt'),
                                                         ('less equal', 'le'), ('greater than', 'ge'),
                                                         ('contain', 'in'), ('not contain', 'not_in'))),
                    'DATETIME': collections.OrderedDict((('is', 'eq'), ('like', 'like'), ('is not', 'ne'),
                                                         ('less than', 'lt'), ('greater than', 'gt'),
                                                         ('less equal', 'le'), ('greater than', 'ge'),
                                                         ('contain', 'in'), ('not contain', 'not_in'))),
                    'JSONB'   : collections.OrderedDict((('is', 'eq'), ('like', 'like'), ('is not', 'ne'),
                                                         ('less than', 'lt'), ('greater than', 'gt'),
                                                         ('less equal', 'le'), ('greater than', 'ge'),
                                                         ('contain', 'in'), ('not contain', 'not_in'))),
                    'BOOLEAN' : collections.OrderedDict((('is', 'eq'), ('like', 'like'), ('is not', 'ne'))),
                    }

DATETIME_FORMATTER = '%Y-%m-%d %H:%M:%S'

# 类型转换的定义
CAST_RULE = {'VARCHAR' : str,
             'INTEGER' : int,
             'BIGINT'  : long,
             'DATETIME': lambda v: datetime.datetime.strptime(v, DATETIME_FORMATTER),
             'JSONB'   : None,
             'BOOLEAN' : bool,
             }


def _resolve_token_today(*args, **kwargs):
    offset = datetime.timedelta(**kwargs)
    today = datetime.datetime.today()
    today = datetime.datetime(today.year, today.month, today.day) + \
            datetime.timedelta(days=1) - \
            datetime.timedelta(seconds=1)
    return (today + offset).strftime(DATETIME_FORMATTER)


def _resolve_token_current_user(*args, **kwargs):
    import db.util
    return db.util.current_user_name()


def _resolve_token_now(*args, **kwargs):
    offset = datetime.timedelta(**kwargs)
    return (datetime.datetime.now() + offset).strftime(DATETIME_FORMATTER)


def _resolve_token_this_week_start(*args, **kwargs):
    offset = datetime.timedelta(**kwargs)
    today = datetime.datetime.today()
    today = datetime.datetime(today.year, today.month, today.day)
    offset += datetime.timedelta(days=-(today.isoweekday() - 1))
    return (today + offset).strftime(DATETIME_FORMATTER)


def _resolve_token_this_week_end(*args, **kwargs):
    offset = datetime.timedelta(**kwargs)
    today = datetime.datetime.today()
    today = datetime.datetime(today.year, today.month, today.day, 23, 59, 59)
    offset += datetime.timedelta(days=(7 - today.isoweekday()))
    return (today + offset).strftime(DATETIME_FORMATTER)


def _offset_month(months):
    today = datetime.datetime.today()
    result = datetime.datetime(today.year, today.month, 1)
    if months == 0:
        return result

    month_direction = int(months / abs(months))
    month_gap = 32 if month_direction > 0 else 27

    for _ in range(abs(int(months))):
        result += datetime.timedelta(days=month_direction * month_gap)
        result += datetime.timedelta(days=-(result.day - 1))

    return result


def _resolve_token_this_month_start(*args, **kwargs):
    months = kwargs.get('months', 0)
    result = _offset_month(months)

    try:
        kwargs.pop('months')
    except:
        pass

    offset = datetime.timedelta(**kwargs)
    result += offset
    return result.strftime(DATETIME_FORMATTER)


def _resolve_token_this_month_end(*args, **kwargs):
    months = kwargs.get('months', 0) + 1
    result = _offset_month(months) - datetime.timedelta(seconds=1)

    try:
        kwargs.pop('months')
    except:
        pass

    offset = datetime.timedelta(**kwargs)
    result += offset
    return result.strftime(DATETIME_FORMATTER)


# 自定义的变量关键字所对应的处理函数
TOKEN_LIST = {'today'           : {'func'      : _resolve_token_today,
                                   'compatible': {'DATETIME', },
                                   'kwargs'    : [['days', {'data_type': float, 'default': 0.0}]
                                                  ]},
              'current_user'    : {'func'      : _resolve_token_current_user,
                                   'compatible': {'VARCHAR', },
                                   'kwargs'    : []},
              'now'             : {'func'      : _resolve_token_now,
                                   'compatible': {'DATETIME', },
                                   'kwargs'    : [['days', {'data_type': float, 'default': 0.0}],
                                                  ['hours', {'data_type': float, 'default': 0.0}],
                                                  ['minutes', {'data_type': float, 'default': 0.0}],
                                                  ]},
              'this_week_start' : {'func'      : _resolve_token_this_week_start,
                                   'compatible': {'DATETIME', },
                                   'kwargs'    : [['weeks', {'data_type': float, 'default': 0.0}],
                                                  ['days', {'data_type': float, 'default': 0.0}],
                                                  ]},
              'this_week_end'   : {'func'      : _resolve_token_this_week_end,
                                   'compatible': {'DATETIME', },
                                   'kwargs'    : [['weeks', {'data_type': float, 'default': 0.0}],
                                                  ['days', {'data_type': float, 'default': 0.0}],
                                                  ]},
              'this_month_start': {'func'      : _resolve_token_this_month_start,
                                   'compatible': {'DATETIME', },
                                   'kwargs'    : [['months', {'data_type': int, 'default': 0.0}],
                                                  ['days', {'data_type': float, 'default': 0.0}],
                                                  ]},
              'this_month_end'  : {'func'      : _resolve_token_this_month_end,
                                   'compatible': {'DATETIME', },
                                   'kwargs'    : [['months', {'data_type': int, 'default': 0.0}],
                                                  ['days', {'data_type': float, 'default': 0.0}],
                                                  ]},
              }


def get_valid_token(data_type):
    return [{'token' : k,
             'func'  : v['func'],
             'kwargs': v['kwargs']}
            for k, v in TOKEN_LIST.items() if data_type in v['compatible']]


def resolve_type(data_type, value):
    cast_func = CAST_RULE.get(data_type, None)
    if cast_func:
        return cast_func(value)

    return value


def resolve_expression(expression):
    if isinstance(expression, basestring):
        return expression

    if isinstance(expression, dict):
        result = ''
        for k in expression:
            func = TOKEN_LIST.get(k, {}).get('func', None)
            if func:
                result += str(func(**expression[k]))

        return result

    return None


def get_sql_attributes(class_name_or_property):
    atts = class_name_or_property.split('.')
    db_class = util.get_class(atts[0])
    if len(atts) == 1:
        return {key: {
            'type' : str(value._orig_columns[0].type) \
                if type(value) == ColumnProperty \
                else 'relation',
            'join' : True if type(value) == RelationshipProperty else False,
            'table': None if type(
                    value) == ColumnProperty else value.mapper.class_.__tablename__}
            for key, value in inspect(db_class).attrs.items()}
    else:
        current_class = db_class
        for x in atts[1:]:
            orm_property = inspect(current_class).attrs.get(x, None)
            if type(orm_property) == ColumnProperty:
                return None
            if orm_property is None:
                raise Exception('no such attr')
            current_class = orm_property.mapper.class_

        return {key: {
            'type' : str(
                    value._orig_columns[0].type) if type(
                    value) == ColumnProperty else 'relation',
            'join' : True if type(value) == RelationshipProperty else False,
            'table': None if type(
                    value) == ColumnProperty else value.mapper.class_.__tablename__}
            for key, value in inspect(current_class).attrs.items()}


if __name__ == '__main__':
    print datetime.datetime.strptime('2018-03-18 00:00:00', DATETIME_FORMATTER)
