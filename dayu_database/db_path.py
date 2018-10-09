#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'
__doc__ = \
    '''
    DBPath 是通过路径的形式，表现数据库FOLDER、FILE 层级结构的一个class。
    由于数据库的核心设计参照的树状结构，而树状结构正好可以通过文件路径的方式进行表示。
    
    设计这个DBPath 的原因是：
    * 前期只使用orm 的方式进行数据库创建，代码会比较多
    * 由于VFX 制作的逻辑本身就带有很强的树状结果关系（project/sequence/shot/type/resource/version...）
        因此，使用类似路径的方式来表现结构就是很好的选择
    * 更贴近文件系统的逻辑
    * 提供多一种的数据库访问API 风格
    
    虽然用起来代码写的很少，但是DBPath 也有一些弊端：
    由于查询逻辑类似文件系统，因此对于比较深的层级结构进行查询时，SQL 的访问次数是很多的。
    因此在非常在意性能的场景中，推荐使用数据库 session 直接查询。
    
    =========== 完整name 和 创建的short name 关系 =============
    为了保证和使用orm 创建数据库对象的逻辑一致。在使用DBPath 查询orm 的时候，必须提供完整的name（例如pl_0010，而不能只提供短名）
    但是在使用 .create() 函数是，创建数据库的时候，都是只让用户输入短名，完整的名字会在写入数据库的时候自动拼接生成。
    
    ============ commit ============
    这里依旧保持统一的逻辑。即 如果对数据库进行了写入、更新 之类的操作，
    所有的API 不负责最终的commit！
    这个commit 的责任是交给用户的，因此用户需要自己执行 db.get_session().commit()
    
    '''

import collections
import re


class DBPath(str):
    def __init__(self, object):
        '''
        初始化方法
        支持类似以文件路径的方式初始化一个数据库的路径层级结构。
        初始化的时候，并不会校验对应的orm 真的存在。
        :param object: 反应数据库结构的路径string
        '''
        super(DBPath, self).__init__(object)
        self.components = self.strip('/').split('/')
        self._cache_orm = None
        self._cache_publish_disk_path = None
        self._cache_work_disk_path = None
        self._cache_cache_disk_path = None

    def __repr__(self):
        return '<DBPath>({})'.format(self)

    @classmethod
    def make_path(cls, db_config_name, **kwargs):
        '''
        让用户只通过meaning，就可以创建出正确层级结构的DBPath
        例如，我想要得到 PROJECT=test, SHOT=pl_0010 的DBPath。在不知道db_config 的时候，是无法得到层级结构的。
        所以通过调用 DBPath.make_path('db.movie', PROJECT='test', SHOT='pl_0010)
        就会返回 DBPath('/test/.*/.*/pl_0010').
        提供的信息越多，DBPath 中通配符的部分就会越少，使得查询速度变快。
        :param db_config_name: string, 类似db.movie、db.episode 这类的配置名
        :param kwargs: dict，key 是meaning，value 是对应的值
        :return: DBPath 对象
        '''
        import util

        config_orm = util.get_db_config(db_config_name)
        if not config_orm:
            return None

        component = {}
        config_order = [(int(key), value['content']) for key, value in config_orm.config.items()]
        for key in kwargs:
            for x in config_order:
                if key.upper() in x[1]:
                    component[x[0]] = kwargs[key]
                    break
        component = [component.get(x + 1, '.*') for x in range(max(component.keys()))]
        return cls('/' + '/'.join(component))

    def orm(self, refresh=False):
        '''
        将DBPath 转换为数据库中对应orm 对象。
        DBPath 中的问一个层级都支持使用正则表达式的形式进行模糊匹配。从一定程度上可以实现跨层级搜索。
        例如：
        DBPath('/project/sequence/pl/.*/dailies/cmp/.*').orm()
        相当于，获得了 pl 场次下，所有shot 的dailies，并且这些dailies 都是cmp 类型的。
        :return: 如果查找到多个，就返回orm 的deque。如果只找到一个orm，那么就返回这个orm；如果没有找到对应的orm，那么返回空deque
        '''
        if getattr(self, '_cache_orm', None) and refresh is None:
            return self._cache_orm

        import util
        import base

        root_orm = util.get_root_folder()
        queue = collections.deque()
        queue.append(root_orm)

        while queue and queue[0].depth < len(self.components):
            current = queue.popleft()
            queue.extend(x for x in current.children
                         if re.match('^{}$'.format(self.components[current.depth]), x.name))

        self._cache_orm = queue[0] if len(queue) == 1 else queue
        if isinstance(self._cache_orm, base.BASE):
            self._cache_orm._cache_db_path = self
        return self._cache_orm

    def disk_path(self, disk_type='publish', refresh=False):
        '''
        将DBPath 转换为DiskPath 对象。
        :param disk_type: 需要提供路径的类型，可以是publish、work、cache 中的一个
        :return: DiskPath 对象
        '''
        if getattr(self, '_cache_{}_disk_path'.format(disk_type), None) and refresh is False:
            return getattr(self, '_cache_{}_disk_path'.format(disk_type), None)

        import base
        setattr(self, '_cache_{}_disk_path'.format(disk_type), self.orm())
        if isinstance(getattr(self, '_cache_{}_disk_path'.format(disk_type), None), base.BASE):
            setattr(self, '_cache_{}_disk_path'.format(disk_type),
                    getattr(self, '_cache_{}_disk_path'.format(disk_type), None).disk_path(disk_type=disk_type))
            getattr(self, '_cache_{}_disk_path'.format(disk_type), None)._cache_db_path = self

        else:
            temp = collections.deque()
            temp.extend((x.disk_path(disk_type=disk_type)
                         for x in getattr(self, '_cache_{}_disk_path'.format(disk_type), None)))
            setattr(self, '_cache_{}_disk_path'.format(disk_type), temp)

        return getattr(self, '_cache_{}_disk_path'.format(disk_type), None)

    def child(self, *args):
        '''
        拼接子层级路径。此时仅仅做路径拼接，而不会验证数据库是否真的存在对应的orm
        :param args: string 参数
        :return: 拼接后的DBPath 路径
        '''
        return DBPath(self + '/' + '/'.join(args))

    def listdir(self):
        '''
        类似文件系统，返回当前DBPath 下包含的数据库路径
        :return: generator
        '''
        import table
        if isinstance(self.orm(), (table.FOLDER, table.SYMBOL)):
            return (self.child(x.name) for x in self.orm().children)
        else:
            raise Exception('no orm in DB!')

    def walk(self):
        '''
        类似文件系统，递归的遍历当前数据库路径下的所有内容
        :return:
        '''
        import table
        orm = self.orm()
        if isinstance(orm, table.FOLDER):
            queue = collections.deque()
            queue.append((orm, self))

            while queue:
                current_orm, current_path = queue.popleft()
                for x in current_orm.children:
                    next_path = DBPath(current_path + '/' + x.name)
                    queue.append((x, next_path))
                    yield next_path

        else:
            raise Exception('no orm in DB!')

    def create(self, *list_of_names):
        '''
        以数据库路径的方式，连续创建新的orm。
        有两个限制：
        * 不能通过这个方式创建project。因为project 层级需要用户提供db_config_name 和storage_config_name
        * 不能通过这个方式来实现创建自动增长版本号的VERSION

        :param list_of_names: list of string。这里需要注意，都是提供的"短名"
        :param parents:
        :return: 创建成功后的DBPath 对象
        '''
        import table
        import util
        import dayu_database
        session = dayu_database.get_session()

        current_orm = self.orm()
        new_path_list = []
        if isinstance(current_orm, collections.Iterable):
            raise Exception('DBPath not represent a ORM!')

        config_orm = util.get_db_config(current_orm.db_config_name)
        for index, component in enumerate(list_of_names):
            sub_orm = next((x for x in current_orm.children if x.name == component), None)
            if sub_orm is None:
                depth_config = config_orm.config.get(str(current_orm.depth + 1), None)
                if depth_config:
                    current_new_path = self + '/' + '/'.join(list_of_names[:index + 1])
                    for _key, _value in depth_config['db_pattern'].items():
                        if re.match('^{0}$'.format(_key), current_new_path):
                            meaning = _value
                            if depth_config['is_end'][meaning]:
                                new_orm = table.FILE(name=component, parent=current_orm)
                            else:
                                new_orm = table.FOLDER(name=component, parent=current_orm)

                            try:
                                session.add(new_orm)
                                session.flush()
                                sub_orm = new_orm
                                new_path_list.append(sub_orm.name)
                                break
                            except Exception as e:
                                session.rollback()
                                if isinstance(new_orm, table.FILE):
                                    raise
                                sub_orm = next((x for x in current_orm.children if x.name == e.message), None)
                                new_path_list.append(sub_orm.name)
                                break
                    else:
                        raise Exception('no match meaning with depth!, {}'.format(current_new_path))

                else:
                    raise Exception('no db_config found!')

            else:
                try:
                    config_orm = util.get_db_config(sub_orm.db_config_name)
                    new_path_list.append(component)
                except Exception as e:
                    raise e

            current_orm = sub_orm

        return self.child(*new_path_list)

    @property
    def parent(self):
        '''
        返回上一个层级（不校验数据库orm 是否存在）
        :return: DBPath 对象
        '''
        return DBPath('/' + '/'.join(self.components[:-1] if self.components else []))

    def ancestor(self, depth):
        '''
        连续向上n 个层级
        :param depth: 大于0 的证书
        :return: DBPath 对象
        '''
        assert depth > 0
        current = self
        for index in range(depth):
            current = current.parent
        return current


if __name__ == '__main__':
    import db

    aa = DBPath.make_path('db.movie', shot='pl_0010', ELEMENT_RESOURCE='.*', project='test')
    print aa
    print aa.orm()
