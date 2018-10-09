#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

import collections
import re
import sys

from sqlalchemy import Column, BigInteger, Boolean, DateTime, String, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, backref, deferred, validates

import deco


class BasicMixin(object):
    # 数据库主键，会使用snowflake 算法生成64 bit 的int
    @declared_attr
    def id(cls):
        return Column(BigInteger, primary_key=True, index=True)

    # orm 的名字用于后台的处理
    @declared_attr
    def name(cls):
        return Column(String)

    # orm 的显示名，主要用于GUI 显示
    @declared_attr
    def label(cls):
        return Column(String)

    # api 不负责真正的删除，只会将对应的row 标记为False，用来区别是否存在
    @declared_attr
    def active(cls):
        return Column(Boolean, default=True)

    # 各种flag 标识，目前没有使用
    @declared_attr
    def flag(cls):
        return Column(Integer, default=0)


class TimestampMixin(object):
    '''
    让class 具备created_time 和 updated_time 这两个属性
    '''

    @declared_attr
    def created_time(cls):
        return deferred(Column(DateTime(timezone=False), server_default=func.now()))

    @declared_attr
    def updated_time(cls):
        return deferred(Column(DateTime(timezone=False), onupdate=func.now()))


class UserMixin(object):
    '''
    让class 具备 created_by 和 updated_by 这两个属性。分别用来记录由谁创建、由谁更新的
    '''

    @declared_attr
    def created_by_name(cls):
        from util import current_user_name
        return deferred(Column(String, default=current_user_name()))

    @declared_attr
    def updated_by_name(cls):
        return deferred(Column(String))

    @declared_attr
    def created_by(cls):
        return relationship('USER',
                            primaryjoin='foreign({}.created_by_name) == remote(USER.name)'.format(
                                    cls.__name__))

    @declared_attr
    def updated_by(cls):
        return relationship('USER',
                            primaryjoin='foreign({}.updated_by_name) == remote(USER.name)'.format(
                                    cls.__name__))


class ExtraDataMixin(object):
    '''
    让class 具备 extra_data 和 debug_data 这两个jsonb 格式的属性。
    通常推荐常用的信息，放入extra_data （例如，sub_level 的文件路径信息就存放在extra_data）
    调试信息、代码信息、错误信息这些只有开发人员需要的信息，推荐放入 debug_data 中。
    （如果信息量很大，并且不需要进场读取，推荐创建INFO，然后hook 到orm 上）
    '''

    @declared_attr
    def extra_data(cls):
        return deferred(Column(JSONB, default=lambda: {}))

    @declared_attr
    def debug_data(cls):
        return deferred(Column(JSONB, default=lambda: {}))


class TypeMixin(object):
    '''
    让class 具备 type_group 和type 的属性
    '''

    @declared_attr
    def type_group(cls):
        return relationship('TYPE_GROUP',
                            primaryjoin='foreign({}.type_group_name) == remote(TYPE_GROUP.name)'.format(
                                    cls.__name__),
                            backref=backref('{}s'.format(cls.__name__.lower()),
                                            lazy='dynamic'))

    @declared_attr
    def type(cls):
        return relationship('TYPE',
                            primaryjoin='foreign({}.type_name) == remote(TYPE.name)'.format(
                                    cls.__name__),
                            backref=backref('{}s'.format(cls.__name__.lower()),
                                            lazy='dynamic'))

    @validates('type_group_name')
    def validate_type_group_name(self, key, value):
        if value is None:
            return value

        import dayu_database
        from util import get_class
        session = dayu_database.get_session()
        try:
            type_group_table = get_class('type_group')
            type_group_orm = session.query(type_group_table).filter(type_group_table.name == value).one()
        except:
            # session.rollback()
            raise Exception('no TYPE_GROUP named: {}'.format(value))

        return value

    @validates('type_name')
    def validate_type_name(self, key, value):
        if value is None:
            return value

        import dayu_database
        from util import get_class
        session = dayu_database.get_session()
        try:
            type_table = get_class('type')
            type_orm = session.query(type_table).filter(type_table.name == value).one()
        except:
            # session.rollback()
            raise Exception('no TYPE named: {}'.format(value))

        return value


class DBPathMixin(object):
    '''
    让class 具备从orm 转换到DBPath 对象的能力
    '''

    _cache_db_path = None

    def db_path(self, refresh=False):
        if getattr(self, '_cache_db_path', None) and refresh is False:
            return self._cache_db_path

        import db_path
        self._cache_db_path = db_path.DBPath('/' + '/'.join(x.name for x in self.hierarchy[1:]))
        self._cache_db_path._cache_orm = self
        return self._cache_db_path


class DiskPathMixin(object):
    '''
    让class 具备从orm 转换到DiskPath 的能力
    '''

    _cache_publish_disk_path = None
    _cache_work_disk_path = None
    _cache_cache_disk_path = None

    _eval_regex = re.compile(r'<(\w+)>')

    @declared_attr
    def path_data(cls):
        return deferred(Column(JSONB, default=lambda: {}))

    def disk_path(self, disk_type='publish', refresh=False):
        '''
        从orm 转换到DiskPath 的对象
        :param disk_type: string，通常可以选择 'publish', 'work', 'cache'。（需要和storage_config 的内容保持一致）
        :return: DiskPath 对象（实际在硬盘上的存放路径）
        '''

        if getattr(self, '_cache_{}_disk_path'.format(disk_type), None) and refresh is False:
            return getattr(self, '_cache_{}_disk_path'.format(disk_type), None)

        from dayu_path import DayuPath
        import util

        storage = util.get_storage_config(self.storage_config_name)
        db_config = util.get_db_config(self.db_config_name)
        parents = self.hierarchy
        result = storage.config[disk_type][sys.platform]
        for index, x in enumerate(parents[1:]):
            depth_config = db_config.config[str(index + 1)]
            param_list = []
            for param in depth_config['to_disk_param'][x.meaning][disk_type]:
                match = DiskPathMixin._eval_regex.match(param)
                if match:
                    func = getattr(util, match.groups()[0])
                    if func:
                        param_list.append(func())

                else:
                    param_list.append(getattr(x, param))

            result += depth_config['to_disk'][x.meaning][disk_type].format(*param_list)

        setattr(self, '_cache_{}_disk_path'.format(disk_type), DayuPath(result))
        getattr(self, '_cache_{}_disk_path'.format(disk_type), None)._cache_orm = self
        return getattr(self, '_cache_{}_disk_path'.format(disk_type), None)


class SubLevelMixin(object):
    '''
    让class 获得从orm 转换到SubLevel 的能力
    （通常情况下，只有FILE 类型的对象才拥有这个能力）
    '''

    @property
    def sub_level(self):
        '''
        生成SubLevel 对象。用户可以使用这个对象进行路径操作，而不需要实际扫描硬盘。
        :return: SubLevel 对象
        '''
        from sub_level import SubLevel
        result = SubLevel(str(self.disk_path(disk_type='publish')))
        result._structure = dict(self.path_data.get('vfx_full_path', {}))
        return result

    def flatten(self, relative=False):
        '''
        基于当前FILE，将所有的sub_level 进行扁平化。
        返回的list，结构如下：
        [{'orm': <FILE>(1131598333513092212, sd_0010_plt_bga_v0004, VERSION),
          'sub_level': u'fullres/exr',
          'file': SequentialFiles(filename=DiskPath(u'/Volumes/filedata/tech/publish/dayu/sequence/sd/sd_0010/element/plt/sd_0010_plt_bga/sd_0010_plt_bga_v0004/fullres/exr/sd_0010_plt_bga_v0004.%04d.exr'), frames=[1001, 1002, 1003, 1004, 1005, 1006], missing=[])}]
          {...}
        ]

        :param relative: bool，表示文件的filename，是否需要只是相对路径
        :return: list
        '''
        import util

        file_table = util.get_class('file')
        if not isinstance(self, file_table):
            return []

        all_versions = self.parent.sub_files.filter(file_table.name <= self.name).all()
        older_files = [x for x in all_versions if x.name <= self.name]
        temp_flatten_dict = dict()
        for v in older_files:
            current_version_path = v.disk_path('publish')
            for s in v.sub_level.walk(collapse=True, relative=relative):
                sub_level_key = '/'.join(s.filename.replace(current_version_path, '').split('/')[:-1]).strip('/')
                temp_flatten_dict.update({sub_level_key: {'file': s, 'orm': v, 'sub_level': sub_level_key}})
        return temp_flatten_dict.values()

    def rescan(self, confirm=True, recursive=True):
        '''
        自动扫描orm 所对应的硬盘路径下有什么文件，并将这些文件的路径信息保存到orm 中。
        之后可以从过sub_level() 进行访问。
        :param confirm: 是否需要真的更新orm？默认false，防止误操作
        :param recursive: 是否递归遍历？默认True
        :return: True 表示更新orm 成功；否则False
        '''

        def folder_to_structure(folders):
            result = {}
            for path in (x.replace('\\', '/').strip('/') for x in folders):
                temp = result
                for item in path.split('/'):
                    temp = temp.setdefault(item, {})
            return result

        if confirm is not True:
            return False

        disk = self.disk_path(disk_type='publish')
        if not disk.exists():
            return False

        black_list_begin = ('.', '..', 'Thumb')
        black_list_end = ('.csv', '.db', '.tmp')

        if recursive:
            import os
            file_list = []
            for root, dirs, files in os.walk(disk):
                dirs[:] = [x for x in dirs if (not x.startswith(black_list_begin)) and
                           (not x.endswith(black_list_end))]
                file_list.extend(('/'.join((root, x)).replace(disk, '') for x in files
                                  if (not x.startswith(black_list_begin)) and
                                  (not x.endswith(black_list_end))))

        else:
            import os
            file_list = (x.replace(disk, '') for x in disk.listdir(filter=os.path.isfile)
                         if (not x.name.startswithwhite_list_begin) and
                         (not x.name.endswith(black_list_end)))

        old_extra = dict(self.path_data)
        old_extra.update({'vfx_full_path': folder_to_structure(file_list)})
        self.path_data = old_extra
        return True


class WorkflowMixin(object):
    # @declared_attr
    # def workflow_config(cls):
    #     return relationship('WORKFLOW_CONFIG',
    #                         primaryjoin='foreign({}.workflow_config_name) == remote(WORKFLOW_CONFIG.name)'.format(
    #                                 cls.__name__),
    #                         order_by='WORKFLOW_CONFIG.name')

    @declared_attr
    def pipeline_config(cls):
        return relationship('PIPELINE_CONFIG',
                            primaryjoin='foreign({}.pipeline_config_name) == remote(PIPELINE_CONFIG.name)'.format(
                                    cls.__name__),
                            order_by='PIPELINE_CONFIG.name')


class DepthMixin(object):
    '''
    用于实现数据库树状层级结构的重要mixin class！
    '''

    @declared_attr
    def depth(cls):
        return Column(Integer, default=0, index=True)

    @declared_attr
    def db_config(cls):
        return relationship('DB_CONFIG',
                            primaryjoin='foreign({}.db_config_name) == remote(DB_CONFIG.name)'.format(
                                    cls.__name__),
                            order_by='DB_CONFIG.name')

    @declared_attr
    def storage(cls):
        return relationship('STORAGE',
                            primaryjoin='foreign({}.storage_config_name) == remote(STORAGE.name)'.format(
                                    cls.__name__),
                            order_by='STORAGE.name')

    @declared_attr
    def parent(cls):
        '''
        获取parent orm，永远都是FOLDER 类型
        :return: FOLDER orm
        '''
        return relationship('FOLDER',
                            primaryjoin='foreign({}.parent_id) == remote(FOLDER.id)'.format(
                                    cls.__name__),
                            backref=backref('sub_{}s'.format(cls.__name__.lower()),
                                            order_by='{}.name'.format(cls.__name__),
                                            lazy='dynamic'))

    @declared_attr
    def top(cls):
        '''
        获得最顶层的FOLDER orm。（通常情况下可以理解为获得当前项目的project）
        :return: FOLDER orm
        '''
        return relationship('FOLDER',
                            primaryjoin='foreign({}.top_id) == remote(FOLDER.id)'.format(cls.__name__))

    def walk(self):
        '''
        递归遍历整个树状结构。类似于文件系统中的递归扫描文件
        :return: generator
        '''
        queue = collections.deque()
        queue.append(self)

        while queue:
            current = queue.popleft()
            for x in current.children:
                yield x
                queue.append(x)

    def find_meaning(self, meaning):
        '''
        快速获得上层层级结构中，某种meaning 的orm。
        如果传入的是string，那么只查找一次。如果是可迭代对象，那么就会按照用户传来的顺序进行查找，返回第一个查找到的orm。

        :param meaning: list of string, 用于表示meaning 的标识（SHOT、RESOURCE、VERSION 等等）
        :return: 如果找到了，就返回orm，否则返回None
        '''
        if isinstance(meaning, basestring):
            return next((x for x in self.hierarchy if x.meaning == meaning.upper()), None)
        else:
            meaning = map(str.upper, meaning)
            MAX_NUMBER = 99999
            result = [meaning.index(x.meaning) if x.meaning in meaning else MAX_NUMBER for x in self.hierarchy]
            min_value = min(result)
            if min_value < MAX_NUMBER:
                return self.hierarchy[result.index(min_value)]
            else:
                return None

    @property
    def cascading_info(self):
        '''
        获得当前orm 的所有cascading info。
        效果和db.util.get_cascading_info(orm, 'cascading_info', debug=False)['all_info'] 一样。
        可以算是语法糖。

        :return: dict
        '''
        from util import get_class
        result = {}
        for x in self.hierarchy:
            cascading_info = x.infos.filter(get_class('info').name == 'cascading_info').first()
            if cascading_info:
                result.update(cascading_info.extra_data)
        return result

    @deco.lazy
    def hierarchy(self):
        '''
        获得当前orm 的所有父级orm。
        返回的对象如：[root_orm, project, sequence_group, sequence... self]。注意返回的list 中包括self
        :return: list of orm
        '''

        # 经过测试，在层级深度 > 4 之后，deque 开始比list 有速度优势。
        # 考虑到大部分使用场景都是SHOT、ASSET 之后的深度，所以还是选择了deque
        result = collections.deque()
        current_orm = self
        while getattr(current_orm, 'parent', None):
            current_orm = getattr(current_orm, 'parent', None)
            result.appendleft(current_orm)

        result.append(self)
        return list(result)

    # todo: 如果连续创建orm，并且不session.flush()，那么由于无法出发validate_path() 函数
    # 因此，导致depth、meaning 等无法被自动继承。（即使使用@validate(parent)，也不行，会报错）
    # 暂时只能够要求编写的人员，每次创建之后，记得flush()
    # @validates('parent')
    # def validate_parent(self, key, value):
    #     self.depth = value.depth + 1

    @validates('depth')
    def validate_depth(self, key, value):
        '''
        利用sqlalchemy 的验证机制，实现自动判断深度、以及自动解析meaning。
        函数中其实并没有修改depth，只是利用这个验证机制，实现meaning 的解析。
        用户永远不应该手动设置depth、meaning 这两个属性！
        :param key:
        :param value: 传入的depth （int）
        :return: depth 数值 （int）
        '''
        if self.meaning is not None:
            return value

        import dayu_database
        import table

        # 这个code block 完成了读取db_config，然后根据里面的配置，解析depth 应该对应什么meaning
        session = dayu_database.get_session()
        assert session is not None

        config_orm = None
        try:
            config_orm = session.query(table.DB_CONFIG).filter(table.DB_CONFIG.name == self.db_config_name).one()
        except Exception as e:
            raise e

        mean = config_orm.config.get(str(value))
        if len(mean['content']) > 1:
            branch_depth = mean['db_pattern']
            parents = getattr(self, 'hierarchy', None)
            db_path_string = '/' + '/'.join(str(x.name) for x in parents[1:])

            for _key, _value in branch_depth.items():
                if re.match('^{0}$'.format(_key), db_path_string):
                    self.meaning = _value
                    break
            else:
                raise Exception('no match meaning with depth!')

            assert mean['is_end'][self.meaning] is (self.__tablename__ == 'file')

        else:
            self.meaning = mean['content'][0]

        # 小技巧，如果当前的meaning 是TYPE，那么正好把type_name 赋值为name。
        if self.meaning == 'TYPE':
            self.type_name = self.name
        if self.meaning == 'TYPE_GROUP':
            self.type_group_name = self.name

        return value


class ClueMixin(object):
    '''
    提供metadata 信息和其他环节信息匹配的mixin。
    这些线索对应了不同的环节。用户只需要录入信息，之后的匹配会动态的通过数据库查询得到。无需手动建立metadata 和shot 之间的关联。
    '''

    @property
    def metadatas(self):
        from util import get_vfx_onset
        return (x for x in get_vfx_onset(self))

    @declared_attr
    def cam_clue(cls):
        # cam_clue 用来记录onset 摄影机的reel name
        return deferred(Column(JSONB, default=[]))

    @declared_attr
    def scene_clue(cls):
        # scene_clue, shot_clue, take_clue 是记录现场拍摄、剪辑师习惯的场、镜、次号
        return deferred(Column(JSONB, default=[]))

    @declared_attr
    def shot_clue(cls):
        # scene_clue, shot_clue, take_clue 是记录现场拍摄、剪辑师习惯的场、镜、次号
        return deferred(Column(JSONB, default=[]))

    @declared_attr
    def take_clue(cls):
        # scene_clue, shot_clue, take_clue 是记录现场拍摄、剪辑师习惯的场、镜、次号
        return deferred(Column(JSONB, default=[]))

    @declared_attr
    def vfx_clue(cls):
        # vfx_clue 记录VFX 对应的shot、asset、sequence 之类的编号
        return deferred(Column(JSONB, default=[]))

    @declared_attr
    def di_clue(cls):
        # di_clue 记录DI 需要的信息（暂时没有）
        return deferred(Column(JSONB, default=[]))


class InfoMixin(object):
    '''
    让class 可以被INFO 挂靠
    '''
    pass


class NoteMixin(object):
    '''
    让class 可以被NOTE 挂靠
    '''
    pass


class SymbolMixin(object):
    '''
    让class 可以拥有symbol 的属性
    '''
    pass


class JobMixin(object):
    '''
    让class 可以提交job 到任务中心。通常情况下是VERSION、DAILIES 这样meaning 的FOLDER 可以继承这个mixin class。
    '''
    pass


class ThumbnailMixin(object):
    @property
    def thumbnail_path(self):
        if self.thumbnail:
            hook_orm = self.top or self
            result = hook_orm.disk_path(disk_type='publish').child('.thumbnail', '{}.png'.format(self.thumbnail.name))
            try:
                result.parent.mkdir(parents=True)
                return result
            except Exception as e:
                # net_log.get_logger().warn('thumbnail path invalid: {}'.format(result))
                return None

        return None
