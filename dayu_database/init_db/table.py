#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'
__doc__ = '''
这个文件记录了数据库的ORM table 对应关系。

数据库的设计思路这次和之前的有所区别。传统的VFX pipeline 设计往往会依据naming convention 的方式来定义pipeline 的结构：
例如： /project/asset/prp/chair/mod/abc/v0001.abc

这样的设计，是人为的定义了数据库table 的结构、关系。如果出现关系不同的项目，那么数据库就需要改动table、column。
显然修改数据库会对整个系统造成比较大的影响。更不要说，如果两个项目同时进行，但是需要采用不同的层级结构。
（例如制作movie 的同时制作 animation、电视剧集，二者的制作逻辑可能存在不同 ）

所以这次的设计，希望数据库可以对自己的层级结构进行自我的解释。这个做有几个好处：
* 可以同时存在不同制作关系（不同的层级结构）
* 只通过修改配置，就能够创建新的关系，而不需要修改数据库结构
* 简化DB api，用户可以像浏览文件系统一样，浏览数据库。


============= FOLDER、FILE、SYMBOL ===============

仿照文件系统的方式，构造一个树状的结构，最重要的是FOLDER、FILE、SYMBOL。
FOLDER 表示"文件夹"，里面可以继续存放其他的结构；
FILE 表示"文件"，是系统中认为的最小单位；（大多数情况下可以对应制作环节中的version、dailies）
SYMBOL 表示"链接"，相当于linux 中symbol link。

FOLDER 和FILE 都会自己记录所在的层级深度（depth），然后根据不同的数据库结构配置，进行自我解释。
解释后的结果存放到自身的meaning 属性中。用这种方式就可以实现：在不改动数据库结构、api 的前提实现多种pipline 结构并存。


=========== VIEW、VIEW_PERMISSION ============

另外一个重要的特性，就是VIEW、VIEW_PERMISSION。
这两个是用来解决视图共享的问题。比方说，对于某个制片，可能会很关心某些制作内容，但是这些内容又不是在一个规范的层级下：
（需要查看某些asset 以及某几个sequence）。对于树状结构，这就需要来回的查找。
VIEW 提供了一个类似"收藏夹" 的功能，可以超出树状结构，将不同位置的FOLDER、FILE 放在一起，实现快速的使用。
VIEW_PERMISSION 提供了对VIEW 共享的控制。适用于下面使用场景：
* 初级制片，创建需要的VIEW，然后共享给制片主管，这样主管就可以快速的得知所有需要注意的内容。
    如果制片修改的VIEW 的内容，那么主管也会看到实时更新的结果。实现了协同工作。
* 制作组长，可以把某些重要的素材放到一个view 中，然后共享给所有组员。这样组员就可以快速的看到相应的内容。
    如果组长修改VIEW，那么组员也会卡看实时更新的结果。
    

============ SEARCH、SEARCH_PERMISSION ==============    

还有一个类似的特性，就是SEARCH、SEARCH_PERMISSION。
这两个table 和VIEW、VIEW_PERMISSION 类似。SEARCH 是可以让用户自定义各种查询规则，实时动态的刷新想要看到的内容。例如：
* 列出今天cmp 所有的dailies
* 某个用户在本周内提交的所有element
* 某个sequnce 中所有的跟踪相机版本

而SEARCH_PERMISSION 和VIEW_PERMISSION 的功能类似。提供了将某个SEARCH 共享给他人的能力。这里就不再赘述。


============ TAG ===============
还提供基于标签的搜索功能。用户给需要的FOLDER、FILE 打上不同的标签，然后就可以通过TAG 快速的得到所有的内容。

总之，我们提供了对于数据的四种不同层面的检索能力：
* FOLDER、FILE、SYMBOL 提供了传统的树状检索能力（方便实现naming convention）
* VIEW 提供了用户跨层级、自己挑选的检索能力 （类似收藏夹）
* SEARCH 提供了通过规则进行全局检索的能力 （基于规则筛选）
* TAG 提供了标签检索的能力


============== 一些设计原则 ===============

数据库以及数据库API 有一些设计原则，了解这些，会更好的帮助理解：
* 数据库除了many-to-many 的3NF 之外，都采用无外键 （no foreign key）设计。所有的连接关系通过API 实现。
    这样可以防止在更改删除是，由于constrain 导致无法实际删除row
* 大部分ORM class 的行为都通过mixin 方式进行扩展
* 大部分的column 都是延迟读取。也就是只有当真正访问到orm 的这个属性时，才会向数据库发起读取请求
* many-to-one 会直接返回orm 对象
* one-to-many 都是惰性读取（lazy），用户必须自己list() 或者使用for loop 来获得每一个orm 对象



'''

import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.event
import sqlalchemy.inspection
import sqlalchemy.orm.properties

import base
import mixin
import random
import re

version_regex = re.compile(r'.*[vV](\d+).*')


class THUMBNAIL(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.CloudMixin, mixin.UserMixin):
    hook_table = sqlalchemy.Column(sqlalchemy.String, index=True)
    hook_id = sqlalchemy.Column(sqlalchemy.BigInteger, index=True)


task_user_association_table = sqlalchemy.Table('task_user_association',
                                               base.BASE.metadata,
                                               sqlalchemy.Column('task_id', sqlalchemy.BigInteger,
                                                                 sqlalchemy.ForeignKey('task.id'),
                                                                 primary_key=True, index=True),
                                               sqlalchemy.Column('user_id', sqlalchemy.BigInteger,
                                                                 sqlalchemy.ForeignKey('user.id'),
                                                                 primary_key=True, index=True))


class STATUS(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.CloudMixin, mixin.UserMixin):
    name = sqlalchemy.Column(sqlalchemy.String, unique=True)


class TASK(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.CloudMixin, mixin.UserMixin):
    project_id = sqlalchemy.Column(sqlalchemy.BigInteger, index=True)
    entity_id = sqlalchemy.Column(sqlalchemy.BigInteger, index=True)
    bid = sqlalchemy.Column(sqlalchemy.FLOAT, default=0.0)
    start_date = sqlalchemy.Column(sqlalchemy.Date)
    end_date = sqlalchemy.Column(sqlalchemy.Date)
    status_name = sqlalchemy.Column(sqlalchemy.String, index=True)
    step_name = sqlalchemy.Column(sqlalchemy.String, index=True)


class TIMELOG(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.CloudMixin, mixin.UserMixin):
    duration = sqlalchemy.Column(sqlalchemy.FLOAT, default=0.0)
    work_date = sqlalchemy.Column(sqlalchemy.Date)
    task_id = sqlalchemy.orm.deferred(sqlalchemy.Column(sqlalchemy.BigInteger, index=True))
    user_name = sqlalchemy.Column(sqlalchemy.String, index=True)


note_user_to_association_table = sqlalchemy.Table('note_user_to_association',
                                                  base.BASE.metadata,
                                                  sqlalchemy.Column('note_id', sqlalchemy.BigInteger,
                                                                    sqlalchemy.ForeignKey('note.id'),
                                                                    primary_key=True, index=True),
                                                  sqlalchemy.Column('user_id', sqlalchemy.BigInteger,
                                                                    sqlalchemy.ForeignKey('user.id'),
                                                                    primary_key=True, index=True))

note_user_cc_association_table = sqlalchemy.Table('note_user_cc_association',
                                                  base.BASE.metadata,
                                                  sqlalchemy.Column('note_id', sqlalchemy.BigInteger,
                                                                    sqlalchemy.ForeignKey('note.id'),
                                                                    primary_key=True, index=True),
                                                  sqlalchemy.Column('user_id', sqlalchemy.BigInteger,
                                                                    sqlalchemy.ForeignKey('user.id'),
                                                                    primary_key=True, index=True))


class NOTE(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.CloudMixin, mixin.UserMixin):
    comment = sqlalchemy.Column(sqlalchemy.String)
    task_id = sqlalchemy.orm.deferred(sqlalchemy.Column(sqlalchemy.BigInteger, index=True))
    from_user_name = sqlalchemy.Column(sqlalchemy.String, index=True)

    hook_table = sqlalchemy.Column(sqlalchemy.String, index=True)
    hook_id = sqlalchemy.Column(sqlalchemy.BigInteger, index=True)


user_department_association_table = sqlalchemy.Table('user_department_association',
                                                     base.BASE.metadata,
                                                     sqlalchemy.Column('user_id', sqlalchemy.BigInteger,
                                                                       sqlalchemy.ForeignKey('user.id'),
                                                                       primary_key=True, index=True),
                                                     sqlalchemy.Column('department_id', sqlalchemy.BigInteger,
                                                                       sqlalchemy.ForeignKey('department.id'),
                                                                       primary_key=True, index=True))


class AUTHORIZATION(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.CloudMixin, mixin.UserMixin):
    '''
    用户存放用户信息的table
    '''
    name = sqlalchemy.Column(sqlalchemy.String, unique=True)


class DEPARTMENT(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.CloudMixin, mixin.UserMixin):
    '''
    用户存放用户信息的table
    '''
    name = sqlalchemy.Column(sqlalchemy.String, unique=True)


class USER(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.CloudMixin, mixin.UserMixin):
    '''
    用户存放用户信息的table
    '''
    name = sqlalchemy.Column(sqlalchemy.String, unique=True)
    full_name = sqlalchemy.Column(sqlalchemy.String)
    email = sqlalchemy.orm.deferred(sqlalchemy.Column(sqlalchemy.String))
    phone = sqlalchemy.orm.deferred(sqlalchemy.Column(sqlalchemy.String))
    avatar = sqlalchemy.orm.deferred(sqlalchemy.Column(sqlalchemy.String))
    authorization_name = sqlalchemy.orm.deferred(sqlalchemy.Column(sqlalchemy.String))


class STORAGE(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    用于存放 storage_config 的table。
    每一行对应一个storage 的配置，具体的配置存放在extra_data 中。
    （参考 db.born.StorageConfigManager）
    '''
    name = sqlalchemy.Column(sqlalchemy.String, unique=True)
    pass


class DB_CONFIG(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    用于存放 db_config 的table
    这个table 的内容非常重要，如何对FOLDER、FILE 的层级结构进行自我解释，都需要这个。
    （参考：db.born.DbConfigManager）
    '''
    name = sqlalchemy.Column(sqlalchemy.String, unique=True)
    pass


class PIPELINE_CONFIG(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    用于存放 pipeline_config 的table
    这个table 的内容非常重要，如何对FOLDER、FILE 的层级结构进行自我解释，都需要这个。
    （参考：db.born.PipelineConfigManager）
    '''
    name = sqlalchemy.Column(sqlalchemy.String, unique=True)
    pass


# class WORKFLOW_CONFIG(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
#     '''
#     用于存放 workflow_config 的table
#     这个table 的内容非常重要，如何对FOLDER、FILE 的层级结构进行自我解释，都需要这个。
#     （参考：db.born.WorkflowConfigManger）
#     '''
#     name = sqlalchemy.Column(sqlalchemy.String, unique=True)
#     pass


class JOB(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    JOB 的定义是完成某个操作所需要的最小工单位。例如：用户想publish dailies 给总监review，那么job 可以分为：
    * copy job：将提交的序列帧拷贝到指定的路径
    * transcode job: 转码一份mov，输出到指定的路径
    * thumbnail job: 生成一张缩略图
    * sync job: 在shotgun 上创建一个dailies，并且把序列帧、mov、截图同步上去

    （参考 job center）
    '''
    priority = sqlalchemy.Column(sqlalchemy.Integer, default=50)
    hook_table = sqlalchemy.Column(sqlalchemy.String, index=True)
    hook_id = sqlalchemy.Column(sqlalchemy.BigInteger, index=True)


class SEARCH_PERMISSION(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    用于控制分享的SEARCH。
    如果用户想要把一个SEARCH 分享给其他用户，代码级别是创建一个SEARCH_PERMISSION。并把需要分享的用户 赋值到 shared_user 属性上。
    '''
    search_id = sqlalchemy.Column(sqlalchemy.BigInteger, index=True)
    shared_user_name = sqlalchemy.Column(sqlalchemy.String, index=True)
    can_view = sqlalchemy.Column(sqlalchemy.Boolean, default=True)
    can_edit = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    can_delete = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    can_share = sqlalchemy.Column(sqlalchemy.Boolean, default=False)


class SEARCH(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    SEARCH 的规则table
    '''
    pass


class VIEW_PERMISSION(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    用于控制分享的VIEW。
    如果用户想要把一个VIEW 分享给其他用户，代码级别是创建一个VIEW_PERMISSION。并把需要分享的用户 赋值到 shared_user 属性上。
    '''
    view_id = sqlalchemy.Column(sqlalchemy.BigInteger, index=True)
    shared_user_name = sqlalchemy.Column(sqlalchemy.String, index=True)
    # 用于表示被分享的user，是否可以 查看、修改、删除、二次分享
    can_view = sqlalchemy.Column(sqlalchemy.Boolean, default=True)
    can_edit = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    can_delete = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    can_share = sqlalchemy.Column(sqlalchemy.Boolean, default=False)


class VIEW(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    VIEW 相当于用户自己定义的"收藏夹"。可以将需要的FOLDER、FILE 集中在一起。
    创建的VIEW，创建者可以随时添加修改删除，这并不会真正影响到FOLDER 和FILE 的数据。
    '''
    pass


class SYMBOL(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    相当于文件系统中的 symbol link。一定程度上可以理解为"快捷方式"。
    可以对FOLDER、FILE 进行软连接。
    '''
    origin_table = sqlalchemy.Column(sqlalchemy.String, index=True)
    origin_id = sqlalchemy.Column(sqlalchemy.BigInteger, index=True)


class INFO(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    INFO 用来记录内容很多，但是又不会被经常读取的信息。
    INFO 和json 的extra_data、debug_data 的区别在于：
    * extra_data 和 debug_data 中记录的信息，是只要得到orm，就很有可能读取的。
        这些数据需要是经常访问，存放在json column 中可以避免对数据库频繁查询
    * QC 这类的解释性信息，大部分情况下即使获得了orm，也可能不需要读取，只在某些特定的情况下需要。
        那么推荐保存为一个INFO 对象，然后hook 到相应的orm 上。这样可以加速一般访问时的数据库查询
    '''
    hook_table = sqlalchemy.Column(sqlalchemy.String, index=True)
    hook_id = sqlalchemy.Column(sqlalchemy.BigInteger, index=True)

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


@sqlalchemy.event.listens_for(mixin.InfoMixin, 'mapper_configured', propagate=True)
def setup_info_listener(mapper, _class):
    '''
    利用sqlalchemy 的监听机制，实现对 继承InfoMixin 的class 动态添加.infos 属性
    :param mapper:
    :param _class: 继承InfoMixin 的class
    :return:
    '''
    hook_type = _class.__name__.lower()
    _class.infos = sqlalchemy.orm.relationship('INFO',
                                               primaryjoin=sqlalchemy.and_(_class.id == sqlalchemy.orm.foreign(
                                                       sqlalchemy.orm.remote(INFO.hook_id)),
                                                                           INFO.hook_table == hook_type),
                                               order_by='INFO.name',
                                               lazy='dynamic',
                                               backref=sqlalchemy.orm.backref('hook_{0}'.format(hook_type),
                                                                              primaryjoin=sqlalchemy.orm.remote(
                                                                                      _class.id) == sqlalchemy.orm.foreign(
                                                                                      INFO.hook_id))
                                               )

    @sqlalchemy.event.listens_for(_class.infos, 'append')
    def append_infos(target, value, initiator):
        value.hook_table = hook_type


# TAG 和 FOLDER 之间的链接表， 提供TAG.folders 和 FOLDER.tags
tag_folder_association_table = sqlalchemy.Table('tag_folder_association',
                                                base.BASE.metadata,
                                                sqlalchemy.Column('tag_id', sqlalchemy.BigInteger,
                                                                  sqlalchemy.ForeignKey('tag.id'),
                                                                  primary_key=True, index=True),
                                                sqlalchemy.Column('folder_id', sqlalchemy.BigInteger,
                                                                  sqlalchemy.ForeignKey('folder.id'),
                                                                  primary_key=True, index=True))

# TAG 和 FILE 之间的连接表，提供TAG.files 和 FILE.tags
tag_file_association_table = sqlalchemy.Table('tag_file_association',
                                              base.BASE.metadata,
                                              sqlalchemy.Column('tag_id', sqlalchemy.BigInteger,
                                                                sqlalchemy.ForeignKey('tag.id'),
                                                                primary_key=True, index=True),
                                              sqlalchemy.Column('file_id', sqlalchemy.BigInteger,
                                                                sqlalchemy.ForeignKey('file.id'),
                                                                primary_key=True, index=True))


class TAG(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    标签。
    可以为用户提供基于TAG 搜索的能力。只要用户将某写FOLDER、FILES 打上标签，那么就可以通过TAG 进行快速搜索。
    （参考Mac OS X 的Finder，可以对文件进行标签）
    '''
    name = sqlalchemy.Column(sqlalchemy.String, unique=True)
    color = sqlalchemy.Column(sqlalchemy.Integer, default=lambda: random.randint(0, 4294967295))


class PACKAGE(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    PACKAGE 可以通俗的理解为一个"包"。里面可以存放任何需要的东西。
    （目前PACKAGE 的概念，除了不能share 之外，和VIEW 有些类似， 不知道之后会不会使用？）
    '''
    pass


type_type_group_association_table = sqlalchemy.Table('type_type_group_association',
                                                     base.BASE.metadata,
                                                     sqlalchemy.Column('type_id', sqlalchemy.BigInteger,
                                                                       sqlalchemy.ForeignKey('type.id'),
                                                                       primary_key=True, index=True),
                                                     sqlalchemy.Column('type_group_id', sqlalchemy.BigInteger,
                                                                       sqlalchemy.ForeignKey('type_group.id'),
                                                                       primary_key=True, index=True))


class TYPE(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    定义数据类型的TYPE
    通常情况下会根据VFX 制作的定义来区分，例如：plt, mod, cam, flip, pyro, ani, srf, tex...
    '''
    pass


class TYPE_GROUP(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin):
    '''
    定义数据类型的group
    主要用来区分大的用途：
    * element：所有跨部门的交接素材
    * workfile: 所有的制作工程文件
    * cache: 所有的本环节内部使用的素材
    * dailies: 需要提交review 的素材
    '''
    pass


# folder 和 folder 自身的多对多链接表
folder_folder_association_table = sqlalchemy.Table('folder_folder_association',
                                                   base.BASE.metadata,
                                                   sqlalchemy.Column('left_folder_id', sqlalchemy.BigInteger,
                                                                     sqlalchemy.ForeignKey('folder.id'),
                                                                     primary_key=True, index=True),
                                                   sqlalchemy.Column('right_folder_id', sqlalchemy.BigInteger,
                                                                     sqlalchemy.ForeignKey('folder.id'),
                                                                     primary_key=True, index=True))
# folder 和file 的多对多链接表
folder_file_association_table = sqlalchemy.Table('folder_file_association',
                                                 base.BASE.metadata,
                                                 sqlalchemy.Column('left_folder_id', sqlalchemy.BigInteger,
                                                                   sqlalchemy.ForeignKey('folder.id'),
                                                                   primary_key=True, index=True),
                                                 sqlalchemy.Column('right_file_id', sqlalchemy.BigInteger,
                                                                   sqlalchemy.ForeignKey('file.id'),
                                                                   primary_key=True, index=True))
# folder 和package 之间的多对多链接表
folder_package_association_table = sqlalchemy.Table('folder_package_association',
                                                    base.BASE.metadata,
                                                    sqlalchemy.Column('left_folder_id', sqlalchemy.BigInteger,
                                                                      sqlalchemy.ForeignKey('folder.id'),
                                                                      primary_key=True, index=True),
                                                    sqlalchemy.Column('right_package_id', sqlalchemy.BigInteger,
                                                                      sqlalchemy.ForeignKey('package.id'),
                                                                      primary_key=True, index=True))
# folder 和view 之间的多对多链接表
folder_view_association_table = sqlalchemy.Table('folder_view_association',
                                                 base.BASE.metadata,
                                                 sqlalchemy.Column('left_folder_id', sqlalchemy.BigInteger,
                                                                   sqlalchemy.ForeignKey('folder.id'),
                                                                   primary_key=True, index=True),
                                                 sqlalchemy.Column('right_view_id', sqlalchemy.BigInteger,
                                                                   sqlalchemy.ForeignKey('view.id'),
                                                                   primary_key=True, index=True))


class FOLDER(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin, mixin.DepthMixin,
             mixin.WorkflowMixin, mixin.NoteMixin,
             mixin.TypeMixin, mixin.SymbolMixin, mixin.JobMixin, mixin.DiskPathMixin,
             mixin.ClueMixin, mixin.InfoMixin, mixin.CloudMixin):
    '''
    可以对应的理解为文件系统中的"文件夹"
    整个层级结构仿照单根文件系统设计。一个FOLDER 内可以继续存放FOLDER、FILE、SYMBOL。
    但是同一个层级内部，不允许出现相同的名字！
    '''
    comment = sqlalchemy.Column(sqlalchemy.String)


file_file_association_table = sqlalchemy.Table('file_file_association',
                                               base.BASE.metadata,
                                               sqlalchemy.Column('left_file_id', sqlalchemy.BigInteger,
                                                                 sqlalchemy.ForeignKey('file.id'),
                                                                 primary_key=True, index=True),
                                               sqlalchemy.Column('right_file_id', sqlalchemy.BigInteger,
                                                                 sqlalchemy.ForeignKey('file.id'),
                                                                 primary_key=True, index=True))

file_folder_association_table = sqlalchemy.Table('file_folder_association',
                                                 base.BASE.metadata,
                                                 sqlalchemy.Column('left_file_id', sqlalchemy.BigInteger,
                                                                   sqlalchemy.ForeignKey('file.id'),
                                                                   primary_key=True, index=True),
                                                 sqlalchemy.Column('right_folder_id', sqlalchemy.BigInteger,
                                                                   sqlalchemy.ForeignKey('folder.id'),
                                                                   primary_key=True, index=True))

file_package_association_table = sqlalchemy.Table('file_package_association',
                                                  base.BASE.metadata,
                                                  sqlalchemy.Column('left_file_id', sqlalchemy.BigInteger,
                                                                    sqlalchemy.ForeignKey('file.id'),
                                                                    primary_key=True, index=True),
                                                  sqlalchemy.Column('right_package_id', sqlalchemy.BigInteger,
                                                                    sqlalchemy.ForeignKey('package.id'),
                                                                    primary_key=True, index=True))

file_view_association_table = sqlalchemy.Table('file_view_association',
                                               base.BASE.metadata,
                                               sqlalchemy.Column('left_file_id', sqlalchemy.BigInteger,
                                                                 sqlalchemy.ForeignKey('file.id'),
                                                                 primary_key=True, index=True),
                                               sqlalchemy.Column('right_view_id', sqlalchemy.BigInteger,
                                                                 sqlalchemy.ForeignKey('view.id'),
                                                                 primary_key=True, index=True))


class FILE(base.BASE, mixin.ExtraDataMixin, mixin.TimestampMixin, mixin.UserMixin, mixin.DepthMixin,
           mixin.WorkflowMixin, mixin.NoteMixin,
           mixin.TypeMixin, mixin.SymbolMixin, mixin.JobMixin, mixin.DiskPathMixin,
           mixin.ClueMixin, mixin.InfoMixin, mixin.CloudMixin, ):
    '''
    FILE 表示数据库中逻辑的最小单位。可以理解成文件系统中的"文件"。
    FILE 不能再包含其他ORM，同时FILE 也具备SubLevel 这个class，可以不扫描硬盘就得到所包含的实际硬盘文件。
    '''
    comment = sqlalchemy.Column(sqlalchemy.String)

    # 用来表示版本分支的属性
    old_file_id = sqlalchemy.orm.deferred(sqlalchemy.Column(sqlalchemy.BigInteger, index=True))
