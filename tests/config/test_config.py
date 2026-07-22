from pathlib import Path
import config


def test_get_project_path():
    """ 测试获取项目根目录 """
    assert config.Config().get_project_path() == Path.cwd()
