#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'
__doc__ = \
    '''
    这个文件只需要TD 或者数据库管理员运行。
    DbConfigManager 是根据写好的json 配置文件，更新数据库中的db_config 以及 storage_config
    原则上只需要在下列场合手动运行：
    * 数据库初始化后，需要首先初始化DB_CONFIG 和STORAGE 才能够添加项目
    * 在添加新的配置json 之后，需要将具体的设置添加到数据库中
    
    ========== 添加json 文件的层级关系 ===========
    json 文件所处的层级 以及文件名都会影响最终同步到数据库的配置name。
    所有的配置都放在db_config_presets 或者storage_config_presets 的文件夹中：
    如果有下面层级的文件：./movie/default.json ，那么数据库中DB_CONFIG 的对应name 为db.movie
    如果有 ./movie/my_project/previs.json，那么数据库中DB_CONFIG 的对应name 为db.movie.my_project.previz
    
    每个project 在创建的时候，都会包含有很多辅助的信息。最终要的就是：
    1. DB config：用来说明项目的层级结构、硬盘路径的规范、文件明明拼接规范
    2. Storage：用来说明在win/mac/linux 下，publish、work、cache 的保存区域分别是什么位置
    3. pipeline config：用来说明，对应环节可以导入、导出的类型都是什么，并且使用哪套api 进行操作。
    
    这三个配置会比较繁复，用户自行确定会很麻烦，因此，这里需要TD 进行编写基础的类型，然后用户在创建project 的时候只需要选择对应
    的模板即可。在创建完成之后，每个project 都会对应三个配置。例如，创建的porject 名字叫做dayu，那么三个配置就叫做：
    * db.dayu
    * storage.dayu
    * pipeline.dayu
    
    
    '''

import json

from dayu_path import DayuPath

import util


class ConfigManagerBase(object):
    all_configs = {}
    prefix = ''

    @property
    def configs(self):
        return self.__class__.all_configs.keys()

    def __getitem__(self, item):
        return self.__class__.all_configs.get(item, None)

    @classmethod
    def load_all_configs(cls):
        '''
        读取当前硬盘上所有DB_CONFIG 对应的json
        :return: None
        '''
        config_path = DayuPath(__file__).parent.child('static', cls.prefix + '_config_presets')

        assert config_path.exists() is True

        for json_preset in config_path.walk():
            if json_preset.ext == '.json':
                with open(json_preset, 'r') as jf:
                    preset_value = json.load(jf, encoding='utf-8')

                    preset_key = json_preset.replace(config_path, '').replace('\\', '/')
                    preset_key = preset_key.replace('.json', '').replace('default', '').strip('/')
                    preset_key = cls.prefix + '.' + '.'.join(preset_key.split('/'))

                    cls.all_configs.update({preset_key: preset_value})

        return cls()

    def push(self, overwrite=False):
        '''
        将所有读取到的json 预设，推到数据库
        :param overwrite: 如果未False，只会创建新的配置。如果未True，即使数据库中已经存在了，也会强制更新配置内容。
        :return:
        '''
        import dayu_database
        session = dayu_database.get_session()
        table_class = util.get_class('storage') if self.prefix == 'storage' else util.get_class(self.prefix + '_config')
        for key in self.__class__.all_configs:
            try:
                old_orm = session.query(table_class).filter(table_class.name == key).one()
                if overwrite:
                    old_orm.extra_data = self.__class__.all_configs[key]
            except:
                new_orm = table_class(name=key, extra_data=self.__class__.all_configs[key])
                session.add(new_orm)

        session.commit()
        session.close()


class DbConfigManager(ConfigManagerBase):
    '''
    用来于更新数据库中DB_CONFIG
    '''
    all_configs = {}
    prefix = 'db'

    def __init__(self):
        super(DbConfigManager, self).__init__()


class StorageConfigManager(ConfigManagerBase):
    '''
    用来读取Storage config ，并且同步到数据库 storage table 的class
    '''
    all_configs = {}
    prefix = 'storage'

    def __init__(self):
        super(StorageConfigManager, self).__init__()


class PipelineAPIConfigManager(ConfigManagerBase):
    '''
    用来读取pipeline config 的class，并且同步到pipeline table 的class
    '''
    all_configs = {}
    prefix = 'pipeline'


class ConfigTemplateManager(object):
    '''
    template 模板class。用来给create project 工具使用。
    可以认为是在DbConfigManager、StorageConfigManager、PipelineAPIConfigManager 这三个class 管理class。

    在create project 工具调用的时候，有两种方式可以创建工程：
    1. 使用已有的项目
    2. 使用最初定义的模板

    如果用户选择了第二种方式，就会使用到ConfigTemplateManager。
    ConfigTemplateManager 会读取DbConfigManager、StorageConfigManager、PipelineAPIConfigManager 三个class 中
    所有的config，并且进行配对，如果存在相同的名称，那么就会认为存在一个可以使用的template 模板设置：

    例如，DbConfigManager 存在 db.movie 这个配置，StorageConfigManager 存在 storage.movie，
    PipelineAPIConfigManager 存在 pipeline.movie。三个拥有movie 名称的配置就形成了完整来的 template.movie 这个模板。
    如果名称不同，或者三种配置有所确实，那么就不会出现可用的模板。
    '''
    db_config_loaded = False
    storage_config_loaded = False
    pipeline_config_loaded = False

    def __init__(self, reload=False):
        '''
        实例化对象，会自动创建三个manager class，并且进行读取。
        通常情况，只会读取一次。

        :param reload: bool，如果True，那么会强制重新从硬盘上读取所有的json 配置文件。
        '''
        if reload:
            self.db_config_manager = DbConfigManager.load_all_configs()
            self.storage_config_manager = StorageConfigManager.load_all_configs()
            self.pipeline_config_manager = PipelineAPIConfigManager.load_all_configs()

        else:
            self.db_config_manager = DbConfigManager() \
                if ConfigTemplateManager.db_config_loaded else DbConfigManager.load_all_configs()
            self.storage_config_manager = StorageConfigManager() \
                if ConfigTemplateManager.storage_config_loaded else StorageConfigManager.load_all_configs()
            self.pipeline_config_manager = PipelineAPIConfigManager() \
                if ConfigTemplateManager.pipeline_config_loaded else PipelineAPIConfigManager.load_all_configs()

        ConfigTemplateManager.db_config_loaded = True
        ConfigTemplateManager.storage_config_loaded = True
        ConfigTemplateManager.pipeline_config_loaded = True

        self._selected_template = None
        self._selected_db_config = None
        self._selected_storage_config = None
        self._selected_pipline_config = None

    def push(self, overwrite=False):
        '''
        写入数据库，应该已经不会使用了。因为create project 的UI 总是会复制，并且自行写入
        :param overwrite:
        :return:
        '''
        self.db_config_manager.push(overwrite=overwrite)
        self.storage_config_manager.push(overwrite=overwrite)
        self.pipeline_config_manager.push(overwrite=overwrite)

    @property
    def available_templates(self):
        '''
        返回所有可用的模板名称
        :return: list of string
        '''
        db_configs = {'.'.join(x.split('.')[1:]) for x in self.db_config_manager.configs}
        storage_configs = {'.'.join(x.split('.')[1:]) for x in self.storage_config_manager.configs}
        pipeline_configs = {'.'.join(x.split('.')[1:]) for x in self.pipeline_config_manager.configs}

        result = db_configs.intersection(storage_configs, pipeline_configs)
        return ['template.' + x for x in result]

    @property
    def template(self):
        return self._selected_template

    @template.setter
    def template(self, template_string):
        self._selected_template = template_string
        self.db_config = 'db.' + '.'.join(template_string.split('.')[1:])
        self.storage_config = 'storage.' + '.'.join(template_string.split('.')[1:])
        self.pipeline_config = 'pipeline.' + '.'.join(template_string.split('.')[1:])

    @property
    def db_config(self):
        return self._selected_db_config

    @db_config.setter
    def db_config(self, config_string):
        self._selected_db_config = config_string

    @property
    def storage_config(self):
        return self._selected_storage_config

    @storage_config.setter
    def storage_config(self, config_string):
        self._selected_storage_config = config_string

    @property
    def pipeline_config(self):
        return self._selected_pipline_config

    @pipeline_config.setter
    def pipeline_config(self, config_string):
        self._selected_pipline_config = config_string


if __name__ == '__main__':
    aa = ConfigTemplateManager()
    print aa.available_templates
