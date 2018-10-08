#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'
__doc__ = \
    '''
    这里是重载orm relationship 的命名规范，然后自动反射到对应的mapper orm class 上。
    
    由于数据库采用了无外键的设计，所以反射的时候并不会存在自动生成的orm relationship。
    只有many to many 的链接才使用了外键，因此，这套数据库中所有的relationship 都会是collection 形式的1 to N 
    
    如果希望更深的了解，可以阅读：
    http://docs.sqlalchemy.org/en/latest/orm/extensions/automap.html
    
    '''

from sqlalchemy.ext.automap import name_for_scalar_relationship, name_for_collection_relationship, generate_relationship
from sqlalchemy.orm.interfaces import MANYTOMANY

# 利用常量字典，进行relationship 的重命名
RELATION_OVERRIDE = {'tag.id<tag_folder_association.tag_id'                   : 'folders',
                     'folder.id<tag_folder_association.folder_id'             : 'tags',
                     'note.id<note_user_to_association.note_id'               : 'to_users',
                     'user.id<note_user_to_association.user_id'               : 'received_notes',
                     'folder.id<folder_folder_association.left_folder_id'     : 'folder_backs',
                     'folder.id<folder_folder_association.right_folder_id'    : 'folder_fronts',
                     'tag.id<tag_file_association.tag_id'                     : 'files',
                     'file.id<tag_file_association.file_id'                   : 'tags',
                     'file.id<file_file_association.left_file_id'             : 'file_ups',
                     'file.id<file_file_association.right_file_id'            : 'file_downs',
                     'view.id<file_view_association.right_view_id'            : 'files',
                     'file.id<file_view_association.left_file_id'             : 'views',
                     'package.id<file_package_association.right_package_id'   : 'files',
                     'file.id<file_package_association.left_file_id'          : 'packages',
                     'folder.id<folder_file_association.left_folder_id'       : 'file_backs',
                     'file.id<folder_file_association.right_file_id'          : 'folder_fronts',
                     'view.id<folder_view_association.right_view_id'          : 'folders',
                     'folder.id<folder_view_association.left_folder_id'       : 'views',
                     'user.id<task_user_association.user_id'                  : 'tasks',
                     'task.id<task_user_association.task_id'                  : 'users',
                     'file.id<file_folder_association.left_file_id'           : 'folder_backs',
                     'folder.id<file_folder_association.right_folder_id'      : 'file_fronts',
                     'package.id<folder_package_association.right_package_id' : 'folders',
                     'folder.id<folder_package_association.left_folder_id'    : 'packages',
                     'note.id<note_user_cc_association.note_id'               : 'cc_users',
                     'user.id<note_user_cc_association.user_id'               : 'cced_notes',
                     'type.id<type_type_group_association.type_id'            : 'type_groups',
                     'type_group.id<type_type_group_association.type_group_id': 'types',
                     'user.id<user_department_association.user_id'            : 'departments',
                     'department.id<user_department_association.department_id': 'users'
                     }


def _name_for_scalar_relationship(base, local_cls, referred_cls, constraint):
    '''
    多对一 的relationship，重命名的函数
    :param base:
    :param local_cls:
    :param referred_cls:
    :param constraint:
    :return:
    '''
    key = '{}>{}'.format(constraint.columns.values()[0], constraint.elements[0].target_fullname)
    # print key
    if key in RELATION_OVERRIDE:
        return RELATION_OVERRIDE[key]

    return name_for_scalar_relationship(base, local_cls, referred_cls, constraint)


def _name_for_collection_relationship(base, local_cls, referred_cls, constraint):
    '''
    一对多的 relationship 重命名函数
    :param base:
    :param local_cls:
    :param referred_cls:
    :param constraint:
    :return:
    '''
    key = '{}<{}'.format(constraint.elements[0].target_fullname, constraint.columns.values()[0])
    # print key
    if key in RELATION_OVERRIDE:
        return RELATION_OVERRIDE[key]

    return name_for_collection_relationship(base, local_cls, referred_cls, constraint)


def _classname_for_table(base, tablename, table):
    '''
    mapper class 对应table 的重命名函数
    :param base:
    :param tablename:
    :param table:
    :return:
    '''
    return str(tablename.upper())


def _generate_relationship(base, direction, return_fn, attrname, local_cls, referred_cls, **kw):
    '''
    用于生成 relationship、backref 的函数。
    目前因为全部采用dynamic 的方式惰性求值，所以需要重载many to many 的连接，增加lazy=dynamic 的属性
    #todo: 考虑之后添加更多的order_by 属性

    :param base:
    :param direction:
    :param return_fn:
    :param attrname:
    :param local_cls:
    :param referred_cls:
    :param kw:
    :return:
    '''
    if direction is MANYTOMANY:
        kw.update(lazy='dynamic')
    return generate_relationship(base, direction, return_fn, attrname, local_cls, referred_cls, **kw)
