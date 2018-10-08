#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'
__doc__ = \
    '''
    这个文件中的函数都是helper function。
    方便数据库中的使用    
    '''

import time
import os

TIME_EPOCH = time.mktime(time.strptime('2010-01-01 00:00:00',
                                       '%Y-%m-%d %H:%M:%S'))

uuidChars = ("a", "b", "c", "d", "e", "f",
             "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s",
             "t", "u", "v", "w", "x", "y", "z", "0", "1", "2", "3", "4", "5",
             "6", "7", "8", "9", "A", "B", "C", "D", "E", "F", "G", "H", "I",
             "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V",
             "W", "X", "Y", "Z")

def load_config(config_name):
    pass

def short_uuid():
    import uuid

    _uuid = uuid.uuid1().get_hex()
    result = ''.join((uuidChars[int(_uuid[x * 4: x * 4 + 4], 16) % 0x3E] for x in range(0, 8)))
    return result


def delete_tree(orm):
    import net_log
    net_log.get_logger().warn('delete data orm tree: {}'.format(orm))
    orm.active = False
    for x in orm.walk():
        x.active = False


def snowflake():
    '''
    类似twitter 的snowflake 生成函数。
    生成的64 bit 整数，具备全局唯一、自增、分布式的特点。可以保证从2010年开始的79年内 不会生成相同的ID
    :return: 64 bit 整数
    '''
    import uuid
    import random

    user_bit = uuid.getnode() % 16
    pid_bit = os.getpid() % 16
    time_bit = int((time.time() - TIME_EPOCH) * 1000.0)
    guid = ((time_bit << 22) |
            (user_bit << 18) |
            (pid_bit << 14) |
            (random.randint(0, 8191)))
    return guid


def get_root_folder():
    '''
    获得整个数据库的Root ORM，可以理解为根路径
    :return: FOLDER orm
    '''
    import db
    import table
    import config.const
    session = db.get_session()
    try:
        return session.query(table.FOLDER).filter(
                table.FOLDER.name == config.const.DB_ROOT_FOLDER_NAME).one()
    except:
        root = table.FOLDER(name=config.const.DB_ROOT_FOLDER_NAME)
        session.add(root)
        session.commit()
        return root


def current_user_name():
    '''
    返回当前用户的用户名
    :return: string
    '''
    import getpass
    import config
    return os.getenv(config.DAYU_DB_NAME) or getpass.getuser()


def get_current_user():
    '''
    返回当前用户的orm
    :return: USER orm
    '''
    import dayu_database
    import table
    session = dayu_database.get_session()
    return session.query(table.USER).filter(table.USER.name == current_user_name()).one()


def get_db_config(db_config_name):
    '''
    获得对应的DB_CONFIG orm
    :param db_config_name: 用户输入的config 名称。例如 db.movie
    :return: DB_CONFIG orm
    '''
    import db
    import table
    session = db.get_session()
    return session.query(table.DB_CONFIG).filter(table.DB_CONFIG.name == db_config_name).one()


def get_storage_config(storage_config_name):
    '''
    获得对应的STORAGE orm
    :param storage_config_name: 用户输入的config 名称。例如 storage.movie
    :return: STORAGE orm
    '''
    import db
    import table
    session = db.get_session()
    return session.query(table.STORAGE).filter(table.STORAGE.name == storage_config_name).one()


def get_class(orm_tablename):
    '''
    通过给定的table 名，返回可以使用的ORM class
    :param orm_tablename: stirng。
    :return: 对应tablename 的ORM class
    '''
    import table
    return getattr(table, orm_tablename.upper(), None)


def get_cascading_info(orm, info_name, debug=False):
    '''
    获得某个FOLDER、FILE 对象的继承info
    处理过程如下：
    1. 获取orm 拥有的所有info 对象
    2. 判断是否存在有info_name 的对象
    3. 读取extra_data 还是debug_data
    4. 进行继承关系分析
    5. 循环执行1~4，直到ROOT_FOLDER。

    返回的字典数据形式：
    {'all_info':     {u'\u6307\u5bfc': u'\u9a6c\u4e01', u'FPS': u'23.98'},
     'inherit_info': {u'\u6307\u5bfc': u'\u9a6c\u4e01'},
     'private_info': {u'FPS': u'23.98'}}

     分别表示全部的信息，继承的信息，自己的私有信息。


    :param orm: FOLDER、FILE 类型的orm
    :param info_name: string，对应的是info.name
    :param debug: bool。默认情况读取extra_data，如果True，那么读取debug_data
    :return: dict

    '''
    result = {'all_info': {}, 'private_info': {}, 'inherit_info': {}}
    for x in orm.hierarchy[:-1]:
        cascading_info = x.infos.filter(get_class('info').name == info_name).first()
        if debug:
            result['inherit_info'].update(dict(cascading_info.debug_data) if cascading_info else {})
        else:
            result['inherit_info'].update(dict(cascading_info.extra_data) if cascading_info else {})

    private_info = orm.infos.filter(get_class('info').name == info_name).first()
    if debug:
        result['private_info'] = dict(private_info.debug_data) if private_info else {}
    else:
        result['private_info'] = dict(private_info.extra_data) if private_info else {}

    for k in result['private_info']:
        try:
            result['inherit_info'].pop(k)
        except:
            pass

    result['all_info'].update(result['inherit_info'])
    result['all_info'].update(result['private_info'])
    return result


def get_next_depth(db_config_name, current_depth):
    '''
    让用户得到下一个depth 可以创建什么meaning 的orm。
    由于数据库的层级是根据config 自我解释的，因此没有固定的层级结构。
    用户在获得一个orm 之后，可能不知道下一个深度层级可以创建什么类型的orm，是FOLDER？还是FILE？
    使用这个函数，就可以让用户知道下一个深度层级应该创建的orm 是什么meaning、以及是FOLDER，还是FILE。

    返回的字典：
    {u'DAILIES': <class 'db.table.FILE'>, u'VERSION': <class 'db.table.FILE'>}

    :param db_config_name: string。db_config_name 必须在DB_CONFIG 里存在
    :param current_depth: int。传入当前的深度层级
    :return: dict
    '''
    import table
    import re

    db_config = get_db_config(db_config_name=db_config_name)

    if isinstance(current_depth, int):
        depth_config = db_config.config.get(str(current_depth + 1), None)
        if depth_config:
            return {v: (table.FILE if depth_config['is_end'][v] else table.FOLDER)
                    for k, v in depth_config['db_pattern'].items()}
    else:
        depth_config = db_config.config.get(str(current_depth.depth + 1), None)
        if depth_config:
            current_db_path_pattern = next(
                    (k for k, v in db_config.config.get(str(current_depth.depth))['db_pattern'].items()
                     if re.match(k, current_depth.db_path())), None)
            return {v: (table.FILE if depth_config['is_end'][v] else table.FOLDER)
                    for k, v in depth_config['db_pattern'].items()
                    if '/'.join(k.split('/')[:-1]) == current_db_path_pattern}

    return {}


def get_vfx_onset(orm):
    '''
    快速获得可能和某个orm 相关的onset metadata。
    匹配的依据是如果orm.name(或者orm.name 的一部分) 出现在metadata FILE.vfx_clue 中，那么就认为是相关的。
    :param orm: FOLDER 或者FILE orm
    :return: generator
    '''
    import db
    import table
    session = db.get_session()
    for meta_file in session.query(table.FILE) \
            .filter(table.FILE.meaning == 'METADATA') \
            .filter(table.FILE.top == orm.top):
        found = False
        for vfx_match_name in meta_file.vfx_clue:
            if vfx_match_name == 'ALL':
                found = True
                yield meta_file
                break

            if vfx_match_name in orm.name:
                found = True
                yield meta_file
                break

        if found is True:
            continue

        for vfx_match_name in meta_file.cam_clue:
            if vfx_match_name == 'ALL':
                found = True
                yield meta_file
                break

            if vfx_match_name in orm.name:
                found = True
                yield meta_file
                break


def get_name_pattern(project_name, meaning):
    meaning = meaning.upper()
    project_orm = get_root_folder()[project_name]
    db_config_orm = project_orm.db_config
    config_data = dict(db_config_orm.config)

    # 在 config 中寻找包含meaning 的level
    found_level = [int(x) for x in config_data if meaning in config_data[x]['content'] and int(x) > 0]
    if not found_level:
        return []

    # 对 level 进行向上遍历，并且在分支的时候根据用户提供的type_group, sequence_group 来进行选择
    # 同时，如果meaning 存在多个level 中，那么势必可以找到一跳符合规范的层级，其他就会跳出
    parents = []
    for l in found_level:
        parents = [meaning]
        temp = meaning
        for i in range(l, 0, -1):
            level_data = config_data[str(i)]
            # print i, temp
            temp = level_data['parent'].get(temp)
            # print level_data['parent']
            if len(temp) > 1:

                temp = next(([x] for x in temp if set(x.split('_')).intersection(set(parents[0].split('_')))), [])
                if not temp:
                    break

            temp = temp[0]
            parents.append(temp)
        else:
            if parents[-1] == 'ROOT':
                # print '--------- found ---------'
                found_level = l
                break

    parents = parents[::-1]
    # print parents

    import re
    string_format_regex = re.compile(r'\{(\d+)\}')
    start = [config_data[str(found_level)], found_level, meaning]

    def traverse_level(value, result_meaning=None, result_gap=None):
        '''
        核心，利用正则表达式，对{\d+} 形式的进行替换，得到最终的可以让用户匹配file name 的regex

        value的数据结构：
        [dict， # db config 中每个level 对应的dict 数据
         int,   # dict 对应的level 所在的深度
         str    # 需要在当前level dict 中寻找的meaning
         ]

        :param value: list
        :param result_meaning: None 或者 list，用来存在正则匹配的每个捕获组的含义
        :param result_gap: list，对嵌套的拼接name 进行过进行解析的结构（必须使用list，来保证共享内存的数据）
        :return: list，结构是[re.compile()，[str, str...]]
        '''

        # 如果不传入，初始化为list
        if result_meaning is None:
            result_meaning = []

        # unpack 数据，方便后面的使用
        current_level_data, current_level_index, current_meaning = value
        # 得到当前的name 的格式化string，例如 {0}_{1}
        current_name_pattern = current_level_data['to_name'][current_meaning]

        if result_gap:
            # 如果不是第一次调用，将字符中的 <CATCH> 关键字 替换为新的current_name_pattern
            # 例如：把 <CATCH>_{1} 替换为 {0}_{1}_{2}_{1}
            result_gap[-1] = result_gap[-1].replace('<CATCH>', current_name_pattern)
        else:
            result_gap = []
            result_gap.append(current_name_pattern)

        # 对 {0}_{1} 的string 进行正则查找，从左到右，每次只替换一个{\d+} 成为 <CATCH>
        for m in string_format_regex.finditer(current_name_pattern):
            parent_name_index = current_level_data['to_name_param'][current_meaning][int(m.group(1))]
            result_gap[-1] = string_format_regex.sub('<CATCH>', result_gap[-1], 1)
            # print  current_level_index, parent_name_index, current_meaning, result_gap[-1]

            # 如果找到name pattern 中的level 就是自身当前的level，那么就仅仅执行替换
            if parent_name_index == current_level_index:
                result_meaning.append(current_meaning)
                result_gap[-1] = string_format_regex.sub('<CATCH>', result_gap[-1], 1)
                return result_gap, result_meaning

            # 如果name pattern 格式化string 中的level 不是自身level，需要递归调用，进行深度有限解析
            traverse_level([config_data[str(parent_name_index)], parent_name_index, parents[parent_name_index]],
                           result_meaning, result_gap)
        return result_gap, result_meaning

    # 调用，并且返回结果
    name_regex, regex_meaning = traverse_level(start)
    regex_string = name_regex[-1].replace('<CATCH>', r'([^_]+)').join(['^', '$'])
    return re.compile(regex_string), regex_meaning


def create_project(name, template_or_project=None, custom_storage=None):
    import db
    import db.born
    import table

    session = db.get_session()

    project_orm = table.FOLDER(name=name, parent=get_root_folder())
    project_orm.db_config_name = 'db.{}'.format(name)
    project_orm.storage_config_name = 'storage.{}'.format(name)
    project_orm.pipeline_config_name = 'pipeline.{}'.format(name)

    if isinstance(template_or_project, basestring):
        template_manager = db.born.ConfigTemplateManager()

        sub_template_name = '.'.join(template_or_project.split('.')[1:])
        print sub_template_name
        db_orm = table.DB_CONFIG(name=project_orm.db_config_name,
                                 extra_data=template_manager.db_config_manager.all_configs.get(
                                         'db.' + sub_template_name))
        storage_orm = table.STORAGE(name=project_orm.storage_config_name,
                                    extra_data=template_manager.storage_config_manager.all_configs.get(
                                            'storage.' + sub_template_name))
        pipeline_orm = table.PIPELINE_CONFIG(name=project_orm.pipeline_config_name,
                                             extra_data=template_manager.pipeline_config_manager.all_configs.get(
                                                     'pipeline.' + sub_template_name))
    else:
        db_orm = table.DB_CONFIG(name=project_orm.db_config_name,
                                 extra_data=template_or_project.db_config.config)
        storage_orm = table.STORAGE(name=project_orm.storage_config_name,
                                    extra_data=template_or_project.storage.config)
        pipeline_orm = table.PIPELINE_CONFIG(name=project_orm.pipeline_config_name,
                                             extra_data=template_or_project.pipeline_config.config)

    if custom_storage:
        storage_orm.extra_data = custom_storage

    session.add_all([project_orm, db_orm, storage_orm, pipeline_orm])
    project_orm.db_config = db_orm
    project_orm.storage = storage_orm
    project_orm.pipeline_config = pipeline_orm

    asset_seq_grp = table.FOLDER(name='asset', label='Asset', parent=project_orm)
    seq_seq_grp = table.FOLDER(name='sequence', label='Sequence', parent=project_orm)
    metadata_seq_grp = table.FOLDER(name='metadata', label='Metadata', parent=project_orm)

    asset_seq_dict = {'chr': 'Character',
                      'efx': 'Effects',
                      'env': 'Environment',
                      'mpt': 'Matte Painting',
                      'prp': 'Prop',
                      'std': 'Standard'}

    metadata_seq_dict = {'lds'   : 'Lens Data',
                         'env'   : 'Environment',
                         'ref'   : 'Reference',
                         'report': 'Report',
                         'scan'  : 'Scanning',
                         'hdri'  : 'HDRI',
                         'misc'  : 'Misc',
                         'cpt'   : 'Concept',
                         'art'   : 'Art'}

    for k in asset_seq_dict:
        asset_seq = table.FOLDER(name=k, label=asset_seq_dict.get(k, k), parent=asset_seq_grp)

    for k in metadata_seq_dict:
        metadata_seq = table.FOLDER(name=k, label=asset_seq_dict.get(k, k), parent=metadata_seq_grp)

    return project_orm


if __name__ == '__main__':
    print short_uuid()
