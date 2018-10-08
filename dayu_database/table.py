#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'
__doc__ = \
    '''
    在反射数据库之前，预先明确的定义需要的mapper class 以及相应的column、orm relationship。
    
    在init_db.table 中，定义的table 都仅仅是说明了column。而 reflection.table 中，大多数情况都不需要声明column 的属性，
    更多的是生命orm relationship 和 一些需要有默认行为、数据库约束条件的column
    
    '''

import itertools
import re
import uuid

from sqlalchemy import inspect, and_, Boolean, Column, FLOAT
from sqlalchemy.event import listens_for
from sqlalchemy.orm import relationship, backref, foreign, remote, ColumnProperty, RelationshipProperty, object_session

import config
import mixin
from base import BASE
from dayu_database.event_center import emit

version_regex = re.compile(r'.*[vV](\d+).*')


class THUMBNAIL(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):

    @property
    def hook(self):
        '''
        获得THUMBNAIL 所挂靠的orm 对象
        :return: orm
        '''
        return getattr(self, 'hook_{}'.format(self.hook_table), None)

    @hook.setter
    def hook(self, value):
        '''
        hook 属性的setter 函数
        :param value: 继承 InfoMixin 的orm 对象
        :return: None
        '''
        self.hook_table = value.__tablename__
        self.hook_id = value.id


@listens_for(mixin.ThumbnailMixin, 'mapper_configured', propagate=True)
def setup_thumbnail_listener(mapper, _class):
    '''
    利用sqlalchemy 的监听机制，实现对 继承InfoMixin 的class 动态添加.infos 属性
    :param mapper:
    :param _class: 继承InfoMixin 的class
    :return:
    '''
    hook_type = _class.__name__.lower()
    _class.thumbnail = relationship('THUMBNAIL',
                                    primaryjoin=and_(_class.id == foreign(remote(THUMBNAIL.hook_id)),
                                                     THUMBNAIL.hook_table == hook_type),
                                    uselist=False,
                                    backref=backref('hook_{0}'.format(hook_type),
                                                    primaryjoin=remote(_class.id) == foreign(
                                                            THUMBNAIL.hook_id))
                                    )

    @listens_for(_class.thumbnail, 'set')
    def set_thumbnail(target, value, old_value, initiator):
        value.hook_table = hook_type


@listens_for(THUMBNAIL, 'init', propagate=False)
def thumbnail_init_name(target, args, kwargs):
    if hasattr(target, 'name') and target.name is None:
        target.name = uuid.uuid1().hex


class STATUS(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    pass


class TASK(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    bid = Column(FLOAT, default=0.0)
    project = relationship('FOLDER',
                           primaryjoin='foreign(TASK.project_id) == remote(FOLDER.id)')
    entity = relationship('FOLDER',
                          primaryjoin='foreign(TASK.entity_id) == remote(FOLDER.id)',
                          backref=backref('tasks',
                                          order_by='TASK.created_time',
                                          lazy='dynamic'))
    status = relationship('STATUS',
                          primaryjoin='foreign(TASK.status_name) == remote(STATUS.name)',
                          backref=backref('tasks',
                                          order_by='TASK.created_time',
                                          lazy='dynamic'))
    step = relationship('TYPE',
                        primaryjoin='foreign(TASK.step_name) == remote(TYPE.name)',
                        backref=backref('tasks',
                                        order_by='TASK.created_time',
                                        lazy='dynamic'))


class TIMELOG(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    task = relationship('TASK',
                        primaryjoin='foreign(TIMELOG.task_id) == remote(TASK.id)',
                        backref=backref('timelogs',
                                        order_by='TIMELOG.work_date',
                                        lazy='dynamic'))
    user = relationship('USER',
                        primaryjoin='foreign(TIMELOG.user_name) == remote(USER.name)',
                        backref=backref('timelogs',
                                        order_by='TIMELOG.work_date',
                                        lazy='dynamic'))


class NOTE(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    task = relationship('TASK',
                        primaryjoin='foreign(NOTE.task_id) == remote(TASK.id)',
                        backref=backref('notes',
                                        order_by='NOTE.created_time',
                                        lazy='dynamic'))
    from_user = relationship('USER',
                             primaryjoin='foreign(NOTE.from_user_name) == remote(USER.name)',
                             backref=backref('sent_notes',
                                             order_by='NOTE.created_time',
                                             lazy='dynamic'))

    @property
    def hook(self):
        '''
        获得NOTE 所挂靠的orm 对象
        :return: orm
        '''
        return getattr(self, 'hook_{}'.format(self.hook_table), None)

    @hook.setter
    def hook(self, value):
        '''
        hook 属性的setter 函数
        :param value: 继承 NoteMixin 的orm 对象
        :return: None
        '''
        self.hook_table = value.__tablename__
        self.hook_id = value.id


@listens_for(mixin.NoteMixin, 'mapper_configured', propagate=True)
def setup_info_listener(mapper, _class):
    '''
    利用sqlalchemy 的监听机制，实现对 继承NoteMixin 的class 动态添加.notes 属性
    :param mapper:
    :param _class: 继承NoteMixin 的class
    :return:
    '''
    hook_type = _class.__name__.lower()
    _class.notes = relationship('NOTE',
                                primaryjoin=and_(_class.id == foreign(remote(NOTE.hook_id)),
                                                 NOTE.hook_table == hook_type),
                                order_by='NOTE.created_time',
                                lazy='dynamic',
                                backref=backref('hook_{0}'.format(hook_type),
                                                primaryjoin=remote(_class.id) == foreign(NOTE.hook_id))
                                )

    @listens_for(_class.notes, 'append')
    def append_notes(target, value, initiator):
        value.hook_table = hook_type


class USER(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    用户存放用户信息的table
    '''

    authorization = relationship('AUTHORIZATION',
                                 primaryjoin='foreign(USER.authorization_name) == remote(AUTHORIZATION.name)',
                                 backref=backref('users',
                                                 order_by='USER.name',
                                                 lazy='dynamic'))

    @property
    def shared_views(self):
        '''
        得到被其他用户分享的VIEW
        :return: generator
        '''
        return (x.view for x in self.view_permissions)

    @property
    def shared_searchs(self):
        '''
        得到被其他用户分享的SEARCH
        :return: generator
        '''
        return (x.search for x in self.search_permissions)


@listens_for(USER, 'before_insert')
def insert_folder(mapper, connection, target):
    # 由于shotgun 的监听事件需要修改cloud_id 和cloud_table, 所以必须在这里强行发射信号
    import message
    message.pub(('event', 'db', 'user', 'commit', 'before'), mapper, connection, target)


class AUTHORIZATION(BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    用户存放用户信息的table
    '''
    pass


class DEPARTMENT(BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    用户存放用户信息的table
    '''
    pass


class STORAGE(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    用于存放 storage_config 的table。
    每一行对应一个storage 的配置，具体的配置存放在extra_data 中。
    （参考 db.born.StorageConfigManager）
    '''

    @property
    def config(self):
        '''
        返回实际的storage config 内容。
        :return: dict
        '''
        return dict(self.extra_data)


#
#
class DB_CONFIG(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    用于存放 db_config 的table
    这个table 的内容非常重要，如何对FOLDER、FILE 的层级结构进行自我解释，都需要这个。
    （参考：db.born.DbConfigManager）
    '''

    @property
    def config(self):
        '''
        返回实际的 db_config 内容。
        :return:
        '''
        return dict(self.extra_data)


# class WORKFLOW_CONFIG(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
#     '''
#     用于存放 workflow_config 的table
#     这个table 的内容非常重要，如何对FOLDER、FILE 的层级结构进行自我解释，都需要这个。
#     （参考：db.born.WorkflowConfigManger）
#     '''
#
#     @property
#     def config(self):
#         '''
#         返回实际的 workflow_config 内容。
#         :return:
#         '''
#         return dict(self.extra_data)


class PIPELINE_CONFIG(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    用于存放 workflow_config 的table
    这个table 的内容非常重要，如何对FOLDER、FILE 的层级结构进行自我解释，都需要这个。
    （参考：db.born.WorkflowConfigManger）
    '''

    @property
    def config(self):
        '''
        返回实际的 workflow_config 内容。
        :return:
        '''
        return dict(self.extra_data)


#
#
class JOB(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    JOB 的定义是完成某个操作所需要的最小工单位。例如：用户想publish dailies 给总监review，那么job 可以分为：
    * copy job：将提交的序列帧拷贝到指定的路径
    * transcode job: 转码一份mov，输出到指定的路径
    * thumbnail job: 生成一张缩略图
    * sync job: 在shotgun 上创建一个dailies，并且把序列帧、mov、截图同步上去

    （参考 job center）
    '''

    @property
    def hook(self):
        '''
        实现了通用外键（GFK），得到JOB 所挂靠的ORM
        :return: orm
        '''
        return getattr(self, 'hook_{0}'.format(self.hook_table), None)

    @hook.setter
    def hook(self, value):
        '''
        通用外键 hook 的setter 函数。
        :param value: orm
        :return: None
        '''
        self.hook_table = value.__tablename__
        self.hook_id = value.id


@listens_for(mixin.JobMixin, 'mapper_configured', propagate=True)
def setup_job_listener(mapper, _class):
    '''
    利用sqlalchemy 的监听机制，实现动态的在class 上添加 .jobs 属性
    :param mapper:
    :param _class: 其他继承 JobMixin 的class
    :return:
    '''
    hook_type = _class.__name__.lower()
    _class.jobs = relationship('JOB',
                               primaryjoin=and_(_class.id == foreign(remote(JOB.id)), JOB.hook_table == hook_type),
                               order_by='JOB.priority, JOB.id',
                               lazy='dynamic',
                               backref=backref('hook_{0}'.format(hook_type),
                                               primaryjoin=remote(_class.id) == foreign(JOB.hook_id)))

    @listens_for(_class.jobs, 'append')
    def append_jobs(target, value, initiator):
        value.hook_table = hook_type


#
#
class SEARCH_PERMISSION(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    用于控制分享的SEARCH。
    如果用户想要把一个SEARCH 分享给其他用户，代码级别是创建一个SEARCH_PERMISSION。并把需要分享的用户 赋值到 shared_user 属性上。
    '''

    shared_user = relationship('USER',
                               primaryjoin='foreign(SEARCH_PERMISSION.shared_user_name) == remote(USER.name)',
                               backref=backref('search_permissions',
                                               lazy='dynamic',
                                               order_by='SEARCH_PERMISSION.name'))
    can_view = Column(Boolean, default=True)
    can_edit = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    can_share = Column(Boolean, default=False)


#
#
class SEARCH(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    SEARCH 的规则table
    '''
    # __table_args__ = {'autoload': True}
    # __tablename__ = 'search'

    # __table__ = Table('search', METADATA, autoload=True)

    permissions = relationship('SEARCH_PERMISSION',
                               primaryjoin='remote(foreign(SEARCH_PERMISSION.search_id)) == SEARCH.id',
                               lazy='dynamic',
                               backref=backref('search'))

    @property
    def shared_to_users(self):
        '''
        获得当前SEARCH 分享给了哪些用户
        :return: generator of orm
        '''
        return (x.shared_user for x in self.permissions)

    @property
    def items(self):
        '''
        根据search 的内容 查找数据库。
        search 的选项会保存在extra_data 中，例如：
        {'target_table': 'folder',
         'filters'     : {'and': [{'col': 'name', 'op': 'like', 'value': '%0010%', 'do': True},
                                  {'or': [{'col': 'top.name', 'op': 'eq', 'value': 'ss',  'do': True},
                                          {'col'  : 'created_by.name', 'op': 'in',
                                           'value': 'yangzhuo,andyguo',  'do': True}]}]}}

        其中 target_table 表示需要查找的table，而filters 表示搜索的条件。filter 的条件可以分为两大类：
        * 逻辑类，例如 and、or、not。
        * filter类

        逻辑类是个dict，key是逻辑的类型，value 永远是list。
        filter 类，每个dict 表示一个搜索条件，包含有三个key:
        * col：表示搜索的名称，如果需要连续查询，可以用 . 将属性隔开，例如"top.name"
        * op：表示进行的操作，例如 in、eq、not_in
        * value：表示用户输入的内容，也是操作的数据。如果value 需要包含有多个值，可以用 , 隔开。例如："a,b,c,d"

        :return: sql 查询对象，如果想要得到实际的内容，需要用户自行list()
        '''
        import dayu_database as db
        import util
        import filter_parse

        # 获得查询的基本类
        model_class = util.get_class(self.extra_data.get('target_table', 'folder'))
        # 建立最基本的查询对象
        sql_expr = db.get_session().query(model_class)

        def _build_filter(model_class, col_name_list):
            '''
            根据一条filter 条件，创建出查询的主体对象
            （用户永远不应该自己调用）
            :param model_class: ORM class
            :param col_name_list: string，查询条件中的 col
            :return: list
            '''
            current_table = model_class
            relationship_filters = []

            # 如果col 的查询名含有. 分割，那么可以认为需要多次连接查询
            for col_name in col_name_list:
                # 得到对应orm class 的所有sqlalchemy 属性，只有这些属性才能够参与sql 的生成。排除纯Python属性
                sql_attr = inspect(current_table).attrs.get(col_name, None)
                # 得到 qlalchemy.orm.attributes.InstrumentedAttribute 的对象。本质上就是类似 FOLDER.xxx 这样的形式
                col_attr = getattr(current_table, col_name, None)

                # 如果是column，那么就是orm 表内属性，不需要子查询
                if sql_attr.__class__ == ColumnProperty:
                    relationship_filters.append(col_attr)
                # 如果是relationship，那么久需要子查询
                elif sql_attr.__class__ == RelationshipProperty:
                    # 判断是 one-to-many，还是many-to-one，来选择has、any 函数
                    if sql_attr.uselist:
                        col_attr = getattr(col_attr, 'any', None)
                    else:
                        col_attr = getattr(col_attr, 'has', None)
                    # 由于子查询可能跨表查询，所以后续的orm class 就会变为新的table
                    current_table = sql_attr.mapper.class_
                    relationship_filters.append(col_attr)

                else:
                    raise Exception('no such a name in ORM')

            return relationship_filters

        def traverse_filter(raw_filter):
            '''
            遍历整个search dict
            :param raw_filter: dict，必须是一个逻辑类的的。例如：{and: [...]}
            :return: 可以用在.filter() 函数内
            '''
            for key, value in raw_filter.items():
                # 得到逻辑函数
                logic = filter_parse.LOGIC_SWITCH[key]
                # 用于存放当前逻辑函数内的查询条件
                param = []
                for sub in value:
                    # 如果查询条件没有col， 那么认为是一个嵌套的逻辑函数，递归调用traverse_filter
                    if sub.get('col', None) is None:
                        param.append(traverse_filter(sub))
                    else:
                        # 这部分是正常的一个搜索条件
                        do = sub.get('do')
                        # 跳过用户没有check 的条件
                        if not do:
                            continue

                        col_name = sub.get('col')
                        op = sub.get('op')
                        data_type = sub.get('type')
                        # 对value 中的关键字进行解析。如果是string 那么直接返回，如果是dict，那么寻找dict 对应的key 处理函数
                        exp_value = filter_parse.resolve_expression(sub.get('value'))
                        # 根据sqlalchemy 定义的data type 对string 进行转换，这样才能够得到正确的比较结果（例如DATETIME）
                        exp_value = filter_parse.resolve_type(data_type, exp_value)

                        # 调用_build_filter 得到查询的函数列表，列表的顺序是按照查询顺序排布
                        attr_list = _build_filter(model_class, col_name.split('.'))

                        # 小技巧，因为sqlalchemy 没有not_in 之类的操作，只能讲其拆解为两部分，先判断in，然后对结果再not
                        if 'not' in op:
                            op = op.replace('not', '').strip('_')

                        # 如果op 是in 的操作，那么value 需要是list
                        if op == 'in':
                            attr_list[-1] = attr_list[-1].in_(exp_value.split(','))

                        # 其他正常的操作，通过逐一判断可能存在的函数
                        else:
                            attr = next((x.format(op) for x in ['{}', '{}_', '__{}__']
                                         if hasattr(attr_list[-1], x.format(op))), None)
                            if attr is None:
                                raise Exception('not a legal op')

                            if exp_value == 'null':
                                exp_value = None

                            attr_list[-1] = getattr(attr_list[-1], attr)(exp_value)

                        # 反向reduce，总是用 list[n](list[n+1])，直到全部完成
                        # 得到类似 FOLDER.top.has(FOLDER.created.has(USER.name.in_([...])))
                        single_sql = attr_list.pop()
                        while attr_list:
                            single_sql = attr_list.pop()(single_sql)

                        # 如果存在not，此时将所有的查询语句取反，例如 not_(...)
                        if 'not' in sub.get('op'):
                            single_sql = filter_parse.LOGIC_SWITCH['not'](single_sql)

                        # 加入逻辑列表
                        param.append(single_sql)

                # 返回逻辑函数
                return logic(*param)

        # 真正的调用，并且返回sql 查询对象，可以使用for loop 来遍历。否则需要用户自己 list()
        if self.extra_data.get('filters', None):
            filter_func = traverse_filter(self.extra_data['filters'])
            return (x for x in sql_expr.filter(filter_func).filter(model_class.active == True))
        else:
            return []


class VIEW_PERMISSION(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    用于控制分享的VIEW。
    如果用户想要把一个VIEW 分享给其他用户，代码级别是创建一个VIEW_PERMISSION。并把需要分享的用户 赋值到 shared_user 属性上。
    '''

    shared_user = relationship('USER',
                               primaryjoin='foreign(VIEW_PERMISSION.shared_user_name) == remote(USER.name)',
                               backref=backref('view_permissions',
                                               lazy='dynamic',
                                               order_by='VIEW_PERMISSION.name'))
    can_view = Column(Boolean, default=True)
    can_edit = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    can_share = Column(Boolean, default=False)


class VIEW(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    VIEW 相当于用户自己定义的"收藏夹"。可以将需要的FOLDER、FILE 集中在一起。
    创建的VIEW，创建者可以随时添加修改删除，这并不会真正影响到FOLDER 和FILE 的数据。
    '''

    permissions = relationship('VIEW_PERMISSION',
                               primaryjoin='remote(foreign(VIEW_PERMISSION.view_id)) == VIEW.id',
                               lazy='dynamic',
                               backref=backref('view'))

    @property
    def shared_to_users(self):
        '''
        获得当前VIEW 被分享给了哪些用户
        :return: generator of orm
        '''
        return (x.shared_user for x in self.permissions)

    @property
    def items(self):
        '''
        获得当前VIEW 所包含的内容(用户拖拽进来的FOLDER、FILES)
        :return: generator of orm
        '''
        return itertools.chain(self.folders, self.files)


class SYMBOL(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    相当于文件系统中的 symbol link。一定程度上可以理解为"快捷方式"。
    可以对FOLDER、FILE 进行软连接。
    '''

    @property
    def origin(self):
        '''
        返回连接的对象 （FOLDER、FILE）
        :return: orm
        '''
        return getattr(self, 'origin_{0}'.format(self.origin_table))

    @origin.setter
    def origin(self, value):
        '''
        origin 的setter 函数
        :param value: FOLDER、FILE 类型的orm
        :return: None
        '''
        self.origin_table = value.__tablename__
        self.origin_id = value.id

    @property
    def children(self):
        '''
        返回symbol link 对应的内容。
        （这里使用children 函数，是为了和FOLDER、FILE 统一api，方便GUI 的调用）
        :return: generator
        '''
        return self.origin.children


@listens_for(SYMBOL, 'before_insert')
def insert_symbol(mapper, connection, target):
    '''
    在 insert 之前，对SYMBOL 的数据进行验证
    :param mapper:
    :param connection:
    :param target: SYMBOL orm
    :return: Non
    '''

    # 确保用户指定了parent
    assert target.parent_id is not None
    # 确保用户指定了origin
    assert target.origin_table and target.origin_id
    # 确保同一层级内没有同名的FOLDER、FILE、SYMBOL
    assert next((x for x in target.parent.children if x.name == target.name and x.id != target.id), None) is None

    if target.lable is None:
        target.label = target.name


@listens_for(mixin.SymbolMixin, 'mapper_configured', propagate=True)
def setup_symbol_listener(mapper, _class):
    '''
    利用sqlalchemy 的监听机制，实现为 继承SymbolMixin 的class 动态添加symbols 属性
    :param mapper:
    :param _class: 继承 SymbolMixin 的class
    :return:
    '''
    symbol_type = _class.__name__.lower()
    _class.symbols = \
        relationship('SYMBOL',
                     primaryjoin=and_(_class.id == foreign(remote(SYMBOL.origin_id)),
                                      SYMBOL.origin_table == symbol_type),
                     order_by=('SYMBOL.origin_table, SYMBOL.origin_id'),
                     lazy='dynamic',
                     backref=backref('origin_{0}'.format(symbol_type),
                                     primaryjoin=remote(_class.id) == foreign(SYMBOL.origin_id))
                     )

    @listens_for(_class.symbols, 'append')
    def append_symbols(target, value, initiator):
        value.origin_table = symbol_type


class INFO(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    INFO 用来记录内容很多，但是又不会被经常读取的信息。
    INFO 和json 的extra_data、debug_data 的区别在于：
    * extra_data 和 debug_data 中记录的信息，是只要得到orm，就很有可能读取的。
        这些数据需要是经常访问，存放在json column 中可以避免对数据库频繁查询
    * QC 这类的解释性信息，大部分情况下即使获得了orm，也可能不需要读取，只在某些特定的情况下需要。
        那么推荐保存为一个INFO 对象，然后hook 到相应的orm 上。这样可以加速一般访问时的数据库查询
    '''

    @property
    def hook(self):
        '''
        获得INFO 所挂靠的orm 对象
        :return: orm
        '''
        return getattr(self, 'hook_{}'.format(self.hook_table), None)

    @hook.setter
    def hook(self, value):
        '''
        hook 属性的setter 函数
        :param value: 继承 InfoMixin 的orm 对象
        :return: None
        '''
        self.hook_table = value.__tablename__
        self.hook_id = value.id


@listens_for(mixin.InfoMixin, 'mapper_configured', propagate=True)
def setup_info_listener(mapper, _class):
    '''
    利用sqlalchemy 的监听机制，实现对 继承InfoMixin 的class 动态添加.infos 属性
    :param mapper:
    :param _class: 继承InfoMixin 的class
    :return:
    '''
    hook_type = _class.__name__.lower()
    _class.infos = relationship('INFO',
                                primaryjoin=and_(_class.id == foreign(remote(INFO.hook_id)),
                                                 INFO.hook_table == hook_type),
                                order_by='INFO.name',
                                lazy='dynamic',
                                backref=backref('hook_{0}'.format(hook_type),
                                                primaryjoin=remote(_class.id) == foreign(INFO.hook_id))
                                )

    @listens_for(_class.infos, 'append')
    def append_infos(target, value, initiator):
        value.hook_table = hook_type


# # TAG 和 FOLDER 之间的链接表， 提供TAG.folders 和 FOLDER.tags
# tag_folder_association_table = Table('tag_folder_association',
#                                      METADATA,
#                                      autoload=True
#                                      )
#
# # TAG 和 FILE 之间的连接表，提供TAG.files 和 FILE.tags
# tag_file_association_table = Table('tag_file_association',
#                                    METADATA,
#                                    autoload=True
#                                    )


class TAG(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    标签。
    可以为用户提供基于TAG 搜索的能力。只要用户将某写FOLDER、FILES 打上标签，那么就可以通过TAG 进行快速搜索。
    （参考Mac OS X 的Finder，可以对文件进行标签）
    '''

    @property
    def items(self):
        '''
        返回所有被打上当前标签的FOLDER 和FILE
        :return: generator
        '''
        return itertools.chain(self.folders, self.files)


class PACKAGE(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    PACKAGE 可以通俗的理解为一个"包"。里面可以存放任何需要的东西。
    （目前PACKAGE 的概念，除了不能share 之外，和VIEW 有些类似， 不知道之后会不会使用？）
    '''

    # __table_args__ = {'autoload': True}
    # __tablename__ = 'package'

    # __table__ = Table('package', METADATA, autoload=True)

    @property
    def items(self):
        return itertools.chain(self.folders, self.files)


class TYPE(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    定义数据类型的TYPE
    通常情况下会根据VFX 制作的定义来区分，例如：plt, mod, cam, flip, pyro, ani, srf, tex...
    '''
    # __table_args__ = {'autoload': True}
    # __tablename__ = 'type'

    # __table__ = Table('type', METADATA, autoload=True)

    pass


class TYPE_GROUP(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin):
    '''
    定义数据类型的group
    主要用来区分大的用途：
    * element：所有跨部门的交接素材
    * workfile: 所有的制作工程文件
    * cache: 所有的本环节内部使用的素材
    * dailies: 需要提交review 的素材
    '''

    pass


class FOLDER(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.DepthMixin,
             mixin.WorkflowMixin, mixin.NoteMixin,
             mixin.TypeMixin, mixin.SymbolMixin, mixin.JobMixin, mixin.DBPathMixin, mixin.DiskPathMixin,
             mixin.ClueMixin, mixin.SubLevelMixin, mixin.InfoMixin, mixin.ThumbnailMixin):
    '''
    可以对应的理解为文件系统中的"文件夹"
    整个层级结构仿照单根文件系统设计。一个FOLDER 内可以继续存放FOLDER、FILE、SYMBOL。
    但是同一个层级内部，不允许出现相同的名字！
    '''

    def __repr__(self):
        '''
        重载orm 的打印内容
        :return: string
        '''
        return u'<{class_name}>({orm_id}, {orm_name}, {meaning})'.format(class_name=self.__class__.__name__,
                                                                         orm_id=self.id,
                                                                         orm_name=self.name,
                                                                         meaning=self.meaning)

    @property
    def shots(self):
        if self.meaning == 'ASSET':
            return self.folder_fronts.filter(FOLDER.meaning == 'SHOT')

        return []

    @shots.setter
    def shots(self, values):
        if self.meaning == 'ASSET':
            self.folder_fronts = values
        else:
            raise Exception('only ASSET.shots, {}'.format(self))

    @property
    def assets(self):
        if self.meaning in ('SHOT', 'ASSET'):
            return self.folder_backs.filter(FOLDER.meaning == 'ASSET')

        return []

    @assets.setter
    def assets(self, values):
        if self.meaning in ('SHOT', 'ASSET'):
            self.folder_backs = values
        else:
            raise Exception('only SHOT or ASSET .shots, {}'.format(self))

    @property
    def children(self):
        '''
        获得当前FOLDER 的所有内容。（可以理解为文件系统中的 listdir ）
        :return: generator
        '''
        return itertools.chain(self.sub_folders, self.sub_files, self.symbols)

    def __getitem__(self, item):
        '''
        方便用户快速的指定下一层级中某个orm
        root_orm['project']['sequence']['pl']['pl_0010']
        :param item: string
        :return: 如果存在，返回对应name 的orm；否则返回None
        '''
        return self.sub_folders.filter(FOLDER.name == item).first() or \
               self.sub_files.filter(FILE.name == item).first() or \
               self.symbols.filter(SYMBOL.name == item).first()



@listens_for(FOLDER, 'before_delete')
def delete_folder(mapper, connection, target):
    if target.meaning == 'PROJECT':
        local_session = object_session(target)
        try:
            local_session.delete(target.storage)
            local_session.delete(target.pipeline_config)
            local_session.delete(target.db_config)
        except Exception as e:
            import net_log
            net_log.get_logger().error('fail to delete project\'s config: {}'.format(target))


@listens_for(FOLDER, 'before_update')
def update_folder(mapper, connection, target):
    '''
    更新FOLDER 时，进行数据验证（通常是 移动了FOLDER 到新的位置）
    :param mapper:
    :param connection:
    :param target: FOLDER orm
    :return: none
    '''

    # 如果FOLDER 标识为"删除"，那么不校验
    if target.active is False:
        return

    # 如果当前FOLDER 不是root_orm 需要校验
    if target.name != config.const.DAYU_DB_ROOT_FOLDER_NAME:
        # 必须指定parent
        assert target.parent.id is not None
        # 如果是第一个层级（通常是project），那么必须指定 db_config_name 和 storage_config_name
        assert not (target.parent.name == config.const.DAYU_DB_ROOT_FOLDER_NAME and target.db_config_name is None)
        assert not (target.parent.name == config.const.DAYU_DB_ROOT_FOLDER_NAME and target.storage_config_name is None)
        assert not (target.parent.name == config.const.DAYU_DB_ROOT_FOLDER_NAME and target.pipeline_config_name is None)

    if target.parent_id is not None:
        # FOLDER 的深度 +1
        target.depth = target.parent.depth + 1

        # 如果是project 层级，那么top 就是自身，否则沿用parent 的top
        if target.depth == 2:
            target.top_id = target.parent_id
            target.top = target.parent
        else:
            target.top_id = target.parent.top_id
            target.top = target.parent.top


@listens_for(FOLDER, 'after_insert')
@emit('event.db.folder.commit.after')
def after_insert_folder(mapper, connection, target):
    pass


@listens_for(FOLDER, 'before_insert')
def insert_folder(mapper, connection, target):
    '''
    FOLDER 插入数据库之前，进行数据验证
    :param mapper:
    :param connection:
    :param target: FOLDER orm
    :return:
    '''
    import dayu_database as db
    import util

    # 如果标记为"删除"， 那么不验证
    if target.active is False:
        return

    # 如果是root，那么不验证
    if target.name == config.DAYU_DB_ROOT_FOLDER_NAME:
        return

    # 必须指定parent
    assert target.parent_id is not None
    # 如果是第一个层级（通常是project），那么必须指定 db_config_name 和 storage_config_name
    assert not (target.parent.name == config.DAYU_DB_ROOT_FOLDER_NAME and target.db_config_name is None)
    assert not (target.parent.name == config.DAYU_DB_ROOT_FOLDER_NAME and target.storage_config_name is None)
    assert not (target.parent.name == config.DAYU_DB_ROOT_FOLDER_NAME and target.pipeline_config_name is None)

    # 其他层级深度，沿用parent 的db_config_name
    if target.db_config_name is None:
        target.db_config_name = target.parent.db_config_name

    # 其他层级深度，沿用parent 的 storage_config_name
    if target.storage_config_name is None:
        target.storage_config_name = target.parent.storage_config_name

    # 其他层级深度，沿用parent 的 pipeline_config_name
    if target.pipeline_config_name is None:
        target.pipeline_config_name = target.parent.pipeline_config_name

    # 沿用parent 的type_name
    if target.type_name is None:
        target.type_name = target.parent.type_name

    # 沿用parent 的type_group_name
    if target.type_group_name is None:
        target.type_group_name = target.parent.type_group_name

    # 深度+1，这里会调用 db.mixin.DepthMixin 中的 @validate('depth') 函数
    target.depth = target.parent.depth + 1

    if target.depth == 2:
        target.top_id = target.parent_id
        target.top = target.parent
    else:
        target.top_id = target.parent.top_id
        target.top = target.parent.top

    # 通过读取对应的 db_config 内容，将用户输入的short name，替换成完整的name
    # 例如，对于shot 来说，用户输入name=0010，但是处理之后会得到 pl_0010 的完整name
    session = db.get_session()
    assert session is not None

    config_orm = util.get_db_config(target.db_config_name)

    parents = list(getattr(target, 'hierarchy', None))
    depth_config = config_orm.config[str(target.depth)]
    selected_names = (x.name for index, x in enumerate(parents) if
                      index in depth_config['to_name_param'][target.meaning])
    target.name = depth_config['to_name'][target.meaning].format(*selected_names)

    # 确保没有重名orm
    try:
        assert next((x for x in target.parent.children if x.name == target.name and x.id != target.id), None) is None
    except:
        raise Exception(target.name)

    # 如果没有输入label，那么用name 赋值给label，方便GUI 读取
    if target.label is None:
        target.label = target.name

    # 由于shotgun 的监听事件需要修改cloud_id 和cloud_table, 所以必须在这里强行发射信号
    import message
    message.pub(('event', 'db', 'folder', 'commit', 'before'), mapper, connection, target)


class FILE(BASE, mixin.BasicMixin, mixin.UserMixin, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.DepthMixin,
           mixin.WorkflowMixin, mixin.NoteMixin,
           mixin.TypeMixin, mixin.SymbolMixin, mixin.JobMixin, mixin.DBPathMixin, mixin.DiskPathMixin,
           mixin.ClueMixin, mixin.SubLevelMixin, mixin.InfoMixin, mixin.ThumbnailMixin):
    '''
    FILE 表示数据库中逻辑的最小单位。可以理解成文件系统中的"文件"。
    FILE 不能再包含其他ORM，同时FILE 也具备SubLevel 这个class，可以不扫描硬盘就得到所包含的实际硬盘文件。
    '''

    old_file = relationship('FILE',
                            primaryjoin='foreign(FILE.old_file_id) == remote(FILE.id)',
                            backref=backref('new_files',
                                            order_by='FILE.name',
                                            lazy='dynamic'))

    def __repr__(self):
        '''
        重载orm 的打印内容
        :return: string
        '''
        return u'<{class_name}>({orm_id}, {orm_name}, {meaning})'.format(class_name=self.__class__.__name__,
                                                                         orm_id=self.id,
                                                                         orm_name=self.name,
                                                                         meaning=self.meaning)

    @property
    def version_part(self):
        match = version_regex.match(self.name)
        if match:
            return 'v' + match.groups()[0]
        else:
            return None

    @property
    def children(self):
        '''
        FILE 不能包含更小的orm，所以永远返回一个空的tuple
        :return: empty tuple
        '''
        return tuple()


@listens_for(FILE, 'before_update')
def update_file(mapper, connection, target):
    '''
    利用sqlalchemy 的监听机制，在更新FILE 之前进行数据校验
    :param mapper:
    :param connection:
    :param target: FILE ORM
    :return:
    '''
    # 如果FILE 被删除，跳过检查
    if target.active is False:
        return

    # 必须指定parent
    assert target.parent_id is not None
    # 必须指定db_config_name
    assert not (target.parent.name == config.DAYU_DB_ROOT_FOLDER_NAME and target.db_config_name is None)
    # 当前depth 是parent 的深度+1，会触发 @validate('depth') 的函数，重新进行meaning 的解析。
    target.depth = target.parent.depth + 1


@listens_for(FILE, 'after_insert')
@emit('event.db.file.commit.after')
def after_insert_file(mapper, connection, target):
    pass


@listens_for(FILE, 'before_insert')
def insert_file(mapper, connection, target):
    '''
    利用sqlalchemy 的监听机制，在FILE 写入数据库之前，进行数据校验
    :param mapper:
    :param connection:
    :param target:
    :return:
    '''
    import dayu_database as db
    import util

    # 如果删除，那么跳过检查
    if target.active is False:
        return

    # 必须指定parent
    assert target.parent_id is not None

    # 继承parent 的db_config_name
    if target.db_config_name is None:
        target.db_config_name = target.parent.db_config_name

    # 继承parent 的 storage_config_name
    if target.storage_config_name is None:
        target.storage_config_name = target.parent.storage_config_name

    # 其他层级深度，沿用parent 的 pipeline_config_name
    if target.pipeline_config_name is None:
        target.pipeline_config_name = target.parent.pipeline_config_name

    # 继承parent 的type_name
    if target.type_name is None:
        target.type_name = target.parent.type_name

    # 继承parent 的type_group_name
    if target.type_group_name is None:
        target.type_group_name = target.parent.type_group_name
    # parent 的深度+1，会触发mixin.DepthMixin 的 @validate('depth') 函数
    target.depth = target.parent.depth + 1

    # 设置top 属性
    if target.depth == 2:
        target.top_id = target.parent_id
        target.top = target.parent
    else:
        target.top_id = target.parent.top_id
        target.top = target.parent.top

    # 如果FILE 不指定文件名，那么很可能是meaning 为VERSION、DAILIES
    # 那么需要根据parent 文件夹内的已有文件，进行版本名自增
    session = db.get_session()
    assert session is not None

    config_orm = util.get_db_config(target.db_config_name)

    if target.name is None:
        try:
            contents = target.parent.sub_files.filter(FILE.id != target.id)[-1]
            match = version_regex.match(str(contents.name))
            if match:
                version_num = match.groups()[0]
                target.name = 'v%0{}d'.format(len(version_num)) % (int(version_num) + 1)
                # if target.old_file_id is None:
                #     target.old_file_id = contents.id

        except:
            cas_info = db.util.get_cascading_info(target, 'cascading_info')['all_info']
            target.name = cas_info.get('init_{}_version'.format(target.type_group_name), 'v0001')

    # 继续根据db_config 来进行完整name 的组合
    parents = list(getattr(target, 'hierarchy', None))
    depth_config = config_orm.config[str(target.depth)]
    selected_names = (x.name for index, x in enumerate(parents) if
                      index in depth_config['to_name_param'][target.meaning])
    target.name = depth_config['to_name'][target.meaning].format(*selected_names)

    # 保证没有重名
    assert next((x for x in target.parent.children if x.name == target.name and x.id != target.id), None) is None

    # 如果没有label，那么把name 赋值给label，方便GUI 读取显示
    if target.label is None:
        target.label = target.name

    # 由于shotgun 的监听事件需要修改cloud_id 和cloud_table, 所以必须在这里强行发射信号
    import message
    message.pub(('event', 'db', 'file', 'commit', 'before'), mapper, connection, target)
