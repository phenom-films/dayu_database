#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'
__doc__ = \
    '''
     SubLevel 是用来表示数据库FILE orm 内部的实际硬盘文件。
    在数据库中，逻辑的最小单位事FILE；对应制作的环节的最小单位事VERSION。
    但是实际制作中，往往还要关心更小的实际文件路径层级关系。这时候就需要Sublevel。
    
    =========== SubLevel 的优势 ===========
    * SubLevel 支持任意层级的表示
    * SUbLevel 只需要扫描硬盘一次，就会将文件路径信息保存到数据库。之后在搜索时，就不需要扫描硬盘。
        在大量序列帧对比时，会有明显的速度提高
    * 可以根据不同环节的json 配置，直接判断出文件对应的不同操作
    
    ========== SubLevel config 的示例 （json）==========
    最难处理的就是一个FILE 内部包含了"复合型" 文件。需要在软件内使用不同方式进行处理：
    * 有可能是需要多选
    * 有可能需要按照预先给定的优先级，只找到最高优先级的一个
    * 对于文件是按照单一的文件处理，还是按照序列帧的方式处理
    
    {
      "levels": [                # Level 是表示SubLevel 的key，value 是一个list，里面按照顺序表示了文件层级深度
        {                        # 每一个层级是一个dict
          "pattern": [           # pattern 是需要匹配的key，value 是一个list
            ".*/cam$",           # 按照希望的优先级顺序，添加可以匹配层级的正则string。（这里表示的是匹配第一个层级是cam 的路径）
            ".*/plate$",
            ".*/stmap$"
          ],
          "op": {                # op 表示找到对应的pattern 之后，应该采取什么操作
            ".*/cam$": null,     # key 必须和上面 pattern 中的正则string 完全一致，value 表示需要执行操作的名字。
            ".*/plate$": null,   # 如果是null，表示没有操作，需要进入下一个文件层级继续判断。
            ".*/stmap$": null
          },
          "flag": "multiple"     # flag，表示当前层级的行为flag。multiple 返回所有匹配的对象，first 只返回第一个找到的匹配对象
        },                       # sequence 表示当做文件序列帧进行处理，而不是单一文件。三种标识可以使用 | 进行连接，表示多个flag。
        {
          "pattern": [
            ".*/.*/mcam$",       # 第二层级，匹配任何叫做cam 的路径
            ".*/.*/abc$",
            ".*/.*/fbx$",
            ".*/.*/exr$",
            ".*/.*/tif$",
            ".*/.*/tiff$",
            ".*/.*/jpg$"
          ],
          "op": {
            ".*/.*/mcam$": null,    # 对应的操作是null，表示需要进入下一层级继续判断
            ".*/.*/abc$": null,
            ".*/.*/fbx$": null,
            ".*/.*/exr$": null,
            ".*/.*/tif$": null,
            ".*/.*/tiff$": null,
            ".*/.*/jpg$": null
          },
          "flag": "first"          # 表示只返回第一个匹配的对象（也就是找到优先级最高的路径）
        },
        {
          "pattern": [
            ".*/.*/mcam/.*\\.mcam$",    # 匹配文件扩展名为 .mcam 的文件
            ".*/.*/abc/.*\\.abc$",
            ".*/.*/fbx/.*\\.fbx$",
            ".*/.*/exr/.*\\.exr$",
            ".*/.*/tif/.*\\.tif$",
            ".*/.*/tiff/.*\\.tiff$",
            ".*/.*/jpg/.*\\.jpg$"
          ],
          "op": {
            ".*/.*/mcam/.*\\.mcam$": "read_geo",   # 对应的操作是read_geo
            ".*/.*/abc/.*\\.abc$": "read_geo",
            ".*/.*/fbx/.*\\.fbx$": "read_geo",
            ".*/.*/exr/.*\\.exr$": "read",
            ".*/.*/tif/.*\\.tif$": "read",
            ".*/.*/tiff/.*\\.tiff$": "read",
            ".*/.*/jpg/.*\\.jpg$": "read"
          },
          "flag": "multiple|sequence"      # 这个层级返回所有匹配的文件，并且把文件作为序列帧进行操作。（本身就是单一文件的不受影响）
        }
      ]
    }
    
    
    ============ create 的自动行为 ==============
    目前判断一个FILE 导入软件的行为，需要有6个分支条件：
    * 当前软件 （通过GUI 端的whatsapp 函数进行获得）
    * 当前task 的类型 （shotgun 上分配的任务）
    * 导入FILE 的type_group （默认的有 element、workfile、cache、dailies）
    * 导入FILE 的type
    * 行为是什么 （导入软件是create、导出是export）
    * 可能调用的API 代码版本是什么 （例如老的工程会使用a0001 版本的代码，其他可能会使用a0002 版本的代码）
    
    通过上面7个分支条件，我们就可以确定某个FILE 导入软件的行为模式了。而行为模式本身就是通过上面的SubLevel config 来控制。
    为了方便扩展，我们把所有的json 按照分支顺序保存在sub_level_config_presets 文件夹内。
    
    '''

import bisect
import collections
import itertools
import json
import re

from dayu_path import DayuPath
from dayu_path.data_structure import SequentialFiles

from config import DECISION_TREE, DAYU_APP_NAME, DAYU_CONFIG_STATIC_PATH

presets_root = 'sub_level_config_presets'

# 用来保存所有分支条件变量的
SUB_LEVEL_CONFIGS = {}


def get_sub_level_op(decision, orm):
    '''
    最重要的helper function。用来分析某个FILE orm 的SubLevel，在某个决定分支条件下，应该对文件分别进行什么操作
    返回的List 例如：
    [(SequentialFile(filename='xxx.abc', frames=[], missing=[]), 'read_geo'),
     (SequentialFile(filename='xxx.%04d.exr', frames=[1001, 1002, 1003], missing=[]), 'read')]
    :param decision: 分支条件的string，例如"movie.nuke.cmp.element.cam.create.a0001"
    :param orm: FILE orm
    :return: list of tuple，tuple 包含 SequentialFile() 和 对应的操作名称
    '''
    sub_config = SUB_LEVEL_CONFIGS.get(decision, None)
    if sub_config is None:
        raise Exception('no matching sub level config')

    queue = collections.deque()
    queue.append((orm.sub_level, 0))
    temp = []

    while queue:
        current_path, index = queue.popleft()
        level = sub_config['levels'][index]

        # 如果对应层级的flag 包含 sequence，需要对当前文件夹内的文件进行sequence 化。
        # 例如，把序列帧变成 SequentialFile(filename='xxx.%04d.exr', frames=[1001, 1002, 1003], missing=[])
        if 'sequence' in level['flag']:
            collapse = {}
            for x in current_path.listdir():
                filename_pattern = x.to_pattern(sub_config.get('frame_pattern', '%'))
                seq = collapse.setdefault(filename_pattern, [])
                if filename_pattern != x:
                    bisect.insort(seq, x.frame)
            seq_list = (SequentialFiles(k, v, (sorted(set(range(v[0], v[-1] + 1)) - set(v))) if v else [])
                        for k, v, in collapse.items())

            product_generator = itertools.product(level['pattern'], seq_list)

        else:
            seq_list = (SequentialFiles(k, [], []) for k in current_path.listdir())
            product_generator = itertools.product(level['pattern'], seq_list)

        # 使用json 预设中写好的当前层级的regex string，对文件路径进行匹配
        for regex, x in product_generator:
            if re.match(regex, x.filename):
                op_func = level['op'].get(regex, None)
                if op_func is None:
                    queue.append((x.filename, index + 1))
                else:
                    temp.append((x, op_func))

                # 如果是first，那么就会break，实现匹配第一优先级的文件。如果是multiple，就会继续查找，实现多文件匹配。
                if 'multiple' not in level['flag']:
                    break

    return temp


class SubLevelConfigManager(object):
    '''
    用于管理SubLevel json 预设的class
    '''

    @staticmethod
    def load_all_configs(software=None):
        '''
        读取所有设置好的json 预设。需要json 文件存放在 sub_level_config_presets 文件内
        必须在加载模块的时候运行一次！
        :return:
        '''

        import os
        if software is None:
            software = os.getenv(DAYU_APP_NAME, '')

        root_path = DayuPath(os.environ.get(DAYU_CONFIG_STATIC_PATH,
                                            DayuPath(__file__).parent.child('static', presets_root, software)))
        for x in root_path.walk(filter=os.path.isfile):
            if x.endswith('.json'):
                with open(x, 'r') as jf:
                    content = jf.read()
                    if content:
                        SUB_LEVEL_CONFIGS.update({'.'.join(x.stem.split('_')): json.loads(content)})

    @staticmethod
    def generate_configs():
        '''
        根据DECISION_TREE 全局变量生成json 文件结构的函数。
        如果不希望拥有文件夹层级也可以不运行，因为只要把对应的json config 文件都放到sub_level_config_presets 文件夹内就好。
        load_all_config() 函数只会读取json 的文件名作为选择条件，不会管文件夹层级。
        但是推荐使用文件夹层级进行管理。
        :return:
        '''
        import os

        root_path = DayuPath(os.environ.get(DAYU_CONFIG_STATIC_PATH,
                                            DayuPath(__file__).parent.child('static', presets_root)))
        for x in itertools.product(*DECISION_TREE):
            temp = root_path.child(*x)
            temp.mkdir(parents=True)
            filename = '_'.join(list(x) + ['a0001.json'])
            temp = temp.child(filename)
            if not temp.exists():
                with open(temp, 'w') as jf:
                    jf.write('')


# 只要运行过一次，不需要每次都运行
# SubLevelConfigManager.generate_configs()

# 必须运行！才能够读取需要的全局SubLevel config信息！
if not SUB_LEVEL_CONFIGS:
    SubLevelConfigManager.load_all_configs()


class SubLevel(DayuPath):
    '''
    SubLevel 是用来描述FILE orm 内部更细致的文件路径层级。
    本质上SubLevel 继承自DiskPath， 因此拥有所有正常文件系统的功能。
    但是为了结合数据库，减少对于硬盘IO 的开销，重载了一些方法，用内存操作取代了硬盘读取。
    在大量序列帧的情况下，可以明显提高速度。
    '''

    def __init__(self, value):
        '''
        初始化。
        基本上，用户无法自行初始化合法的SubLevel 对象。只能够通过 orm.sub_level() 得到这样的对象！
        :param value:
        '''
        super(SubLevel, self).__init__(value)
        self._structure = {}

    def isdir(self):
        '''
        利用数据库信息判断，当前路径是否为文件夹。（不扫描硬盘）
        :return: True 如果是文件夹，否则返回False
        '''
        return True if self._structure else False

    def isfile(self):
        '''
        利用数据库判断当前路径是否为文件（不扫描硬盘）
        :return: 如果是文件，返回True；否则返回False
        '''
        return not self.isdir()

    def __getitem__(self, item):
        temp_struct = self._structure.get(item, None)
        if temp_struct is None:
            return None
        else:
            result = SubLevel(self + '/' + str(item))
            result._structure = temp_struct
            return result

    def listdir(self):
        '''
        不扫描硬盘，直接获取文件夹内部的 文件夹 和 文件。
        :return: SubLevel 类型的list
         '''
        if self._structure:
            result = []
            for item in sorted(self._structure.keys()):
                path_ = (self + item) if self.endswith('/') else (self + '/' + item)
                temp = SubLevel(path_)
                temp._structure = self._structure[item]
                result.append(temp)
            return result
        else:
            return []

    @property
    def sub_folders(self):
        '''
        不扫描硬盘，直接获取文件夹内部的所有子文件夹
        :return: SubLevel 类型的list
        '''
        if self._structure:
            result = []
            for item in sorted(self._structure.keys()):
                if self._structure[item]:
                    path_ = (self + item) if self.endswith('/') else (self + '/' + item)
                    temp = SubLevel(path_)
                    temp._structure = self._structure[item]
                    result.append(temp)
            return result
        else:
            return []

    @property
    def sub_files(self):
        '''
        不扫描硬盘，直接获取文件夹内部的所有的文件
        :return: SubLevel 类型的list
        '''
        if self._structure:
            result = []
            for item in sorted(self._structure.keys()):
                if self._structure[item] == {}:
                    path_ = (self + item) if self.endswith('/') else (self + '/' + item)
                    temp = SubLevel(path_)
                    temp._structure = self._structure[item]
                    result.append(temp)
            return result
        else:
            return []

    def walk(self, collapse=False, relative=False):
        '''
        递归的遍历当前文件夹下的所有文件（不扫描硬盘）
        :param collapse: 如果是True，返回的数据会被序列化（SequentialFile），否则全部按照单一文件路径进行返回
        :return: generator
        '''
        import bisect
        import collections

        queue = collections.deque()
        queue.append(self)

        while queue:
            current = queue.popleft()
            if collapse:
                seq_list = {}
                for x in current.sub_files:
                    filename_pattern = x.to_pattern()
                    frames_list = seq_list.setdefault(filename_pattern, [])
                    if filename_pattern != x:
                        bisect.insort(frames_list, x.frame)

                queue.extend(current.sub_folders)

                for k, v in seq_list.items():
                    yield SequentialFiles(k.replace(self, '').strip('/') if relative else k,
                                          v,
                                          (sorted(set(range(v[0], v[-1] + 1)) - set(v))) if v else [])
            else:
                for x in current.listdir():
                    if x.isdir():
                        queue.append(x)
                    else:
                        yield x.replace(self, '').strip('/') if relative else x

    def absolute(self):
        '''
        返回绝对路径
        :return: SubLevel 对象自身
        '''
        return self

    def disk_path(self):
        '''
        将SubLevel 对象转换为普通的DiskPath 对象。
        之后进行的所有操作，都必须对硬盘进行操作。而无法利用数据库的信息了。
        :return: DiskPath 对象
        '''
        return DayuPath(self)
