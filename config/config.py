""" 配置文件 

用于存储项目的配置信息，如 API 密钥、数据库连接信息等。

Typical usage example:

"""

from pathlib import Path


class Config:
    """ 配置类 """
    def __init__(self):
        self.porject_path = Path.cwd()


    def get_project_path(self):
        """ 获取项目根目录 """
        return self.porject_path