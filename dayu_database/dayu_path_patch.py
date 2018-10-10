#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

import collections

from dayu_path.plugin import DayuPathPlugin, DayuPath


def get_configs(self, disk_type='publish'):
    '''
    内部的解析分析方法。
    返回初步分析的大致结果：
    * db_config_orm = 对应的数据库结构orm
    * storage_orm  = 对应的STORAGE orm
    * project_orm = 对应的项目orm （FOLDER orm，并且层级深度是1）
    * root = 根路径
    * compoent = 从项目开始的所有层级结构的列表

    :param disk_type: 路径存储的类型，可以是publish, work, cache 中的一种
    :return: tuple
    '''
    import dayu_database
    from table import STORAGE
    import util
    session = dayu_database.get_session()
    component = self.split('/')
    if component and ':' in component[0]:
        component[0] = component[0].lower()

    mark = component.index(disk_type) if disk_type in component else None
    if mark:
        root = '/'.join(component[:mark + 1])
        storage_orm = None
        for x in session.query(STORAGE):
            if root in x.config[disk_type].values():
                storage_orm = x
                break
        else:
            # raise Exception('no root matched in storage_config')
            return None, None, None, None, None

        project_name = component[mark + 1]
        project_orm = util.get_root_folder()[project_name]
        db_config_orm = None
        if project_orm:
            db_config_orm = project_orm.db_config
        else:
            # raise Exception('no matching project')
            return None, None, None, None, None

        return db_config_orm, storage_orm, project_orm, root, component[mark + 1:]


    else:
        return None, None, None, None, None


def area(self):
    component = self.strip('/').split('/')

    if 'publish' in component:
        area = 'publish'
        mark = self.ancestor(len(component) - component.index('publish') - 1)
    elif 'work' in component:
        area = 'work'
        mark = self.ancestor(len(component) - component.index('work') - 1)
    elif 'cache' in component:
        area = 'cache'
        mark = self.ancestor(len(component) - component.index('cache') - 1)
    else:
        area = None
        mark = None

    return mark


def platform(self, platform=None):
    '''
    进行路径平台转换的便捷方法。
    如果用户给定一个路径，这个路径是合法的流程内文件，那么可以将其转换到不同的操作系统对应的文件路径。
    如果路径不是流程内文件，直接返回原路径
    :param platform: string，可以是win32, darwin, linux2 中的一种，分别对应windows、苹果、linux
    :return: DiskPath 对象
    '''
    if platform is None:
        import sys
        platform = sys.platform

    import dayu_database
    from dayu_database.table import STORAGE
    session = dayu_database.get_session()
    component = self.split('/')

    mark = None
    area = None
    if 'publish' in component:
        area = 'publish'
        mark = component.index('publish')
    elif 'work' in component:
        area = 'work'
        mark = component.index('work')
    elif 'cache' in component:
        area = 'cache'
        mark = component.index('cache')

    if mark is None:
        return self
    else:
        root_path = '/'.join(component[:mark + 1])
        for storage in session.query(STORAGE):
            for k, v in storage.config[area].items():
                if v == root_path:
                    target = storage.config[area].get(platform, None)
                    result = DayuPath(target + '/' + '/'.join(component[mark + 1:])) if target else self
                    return result

        return self


def orm(self, disk_type='publish', refresh=False):
    '''
    把路径转换为ORM 的函数。
    路径中的每一个层级，支持使用正则表达式进行通配符选择。
    :param disk_type: string。可以是publish、work、cache 的三者之一
    :return: 如果只有唯一对应的ORM，返回ORM；否则返回deque()
    '''
    if getattr(self, '_cache_orm', None) and refresh is False:
        return self._cache_orm

    import base
    import re

    db_config, storage, project, root_path, component = self.get_configs(disk_type)
    if db_config is None:
        return collections.deque()

    queue = collections.deque()
    queue.append(project)
    disk_depth = None

    while queue \
            and queue[0].__tablename__ == 'folder' \
            and db_config.config[str(queue[0].depth)]['from_disk'][queue[0].meaning][disk_type] < len(
            component) - 1:
        current_orm = queue.popleft()
        depth_config = db_config.config.get(str(current_orm.depth + 1), None)
        if depth_config is None:
            queue.appendleft(current_orm)
            break

        for x in current_orm.children:
            disk_depth = depth_config['from_disk'][x.meaning][disk_type]
            if re.match(r'^{}$'.format(x.name), component[disk_depth].split('.')[0]):
                queue.append(x)

    self._cache_orm = queue[0] if len(queue) == 1 else queue
    if isinstance(self._cache_orm, base.BASE):
        setattr(self._cache_orm, '_cache_{}_disk_path'.format(disk_type),
                DayuPath(root_path + '/' + '/'.join(component[:disk_depth + 1])))
    return self._cache_orm


def db_path(self, disk_type='publish', refresh=False):
    '''
    将DiskPath 转换为DBPath 的方法。
    :param disk_type: string。可以是publish、work、cache 的三者之一
    :return: 如果只有唯一对应的DiskPath，返回DiskPath；否则返回deque()
    '''
    if getattr(self, '_cache_db_path', None) and refresh is False:
        return self._cache_db_path

    import base
    self._cache_db_path = self.orm(disk_type=disk_type)
    if isinstance(self._cache_db_path, base.BASE):
        self._cache_db_path = self._cache_db_path.db_path()
        setattr(self._cache_db_path, '_cache_{}_disk_path'.format(disk_type), self)
    else:
        temp = collections.deque()
        temp.extend((x.db_path() for x in self._cache_db_path))
        self._cache_db_path = temp

    return self._cache_db_path


def str_frame(self):
    '''
    返回解析出的帧数
    :return: string 类型。如果没有解析成功，返回 空字符
    '''
    from dayu_path.config import FRAME_REGEX
    match = FRAME_REGEX.match(self.name)
    return match.group(1) if match else ''


DayuPathPlugin.register_func(get_configs)
DayuPathPlugin.register_func(platform)
DayuPathPlugin.register_func(orm)
DayuPathPlugin.register_func(db_path)
DayuPathPlugin.register_attribute('area', property(area))
DayuPathPlugin.register_attribute('str_frame', property(str_frame))
