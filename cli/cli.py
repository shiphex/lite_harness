""" 命令行交互模块.

执行命令行交互，获取用户输入，执行系统输出。

Typical usage example:
    cli.inform_system_info("输入问题，回车发送。输入 q 退出。")
    user_input = cli.get_user_input()
    cli.put_agent_output(user_input)
"""

"""
交互色彩管理：
- 系统信息：灰色    \033[38m\033[0m
- 用户输入：蓝色    \033[34m\033[0m
- 智能体输出：原色    \033[0m\033[0m
- 错误信息：红色    \033[31m\033[0m
"""

import sys

# 确保输出流支持 UTF-8 编码
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# res means reset
color = {
    "res"           : "\033[0m",        # 重置颜色
    "black"         : "\033[30m",       # 黑色
    "blue"          : "\033[34m",       # 蓝色
    "bold"          : "\033[1m",        # 加粗
    "bold_res"      : "\033[22m",       # 重置加粗
    "cyan"          : "\033[36m",       # 青色
    "green"         : "\033[32m",       # 绿色
    "italics"       : "\033[3m",        # 斜体
    "italics_res"   : "\033[23m",       # 重置斜体
    "purple"        : "\033[35m",       # 紫色
    "red"           : "\033[31m",       # 红色
    "underline"     : "\033[4m",        # 下划线
    "underline_res" : "\033[24m",       # 重置下划线
    "white"         : "\033[37m",       # 白色
    "yellow"        : "\033[33m",       # 黄色
    "gray"          : "\033[90m",       # 灰色
}


def inform_system_info(messages: str):
    """ 告知用户系统信息.
    
    Args: 
        messages (str): 系统信息内容。

    Returns:
        None
        
    Raises:
        None
    """
    print(f"{color['yellow']}{messages}{color['res']}")


def inform_system_warning(messages: str):
    """ 告知用户警告信息。
    
    Args:
        messages (str): 警告信息内容。
        
    Returns:
        None
        
    Raises:
        None
    """
    print(f"{color['red']}{messages}{color['res']}")

def get_user_input(messages: str = ">> ") -> str:
    """ 获取用户输入.
    
    Args:
        None
        
    Returns:
        str: 用户输入内容。
        
    Raises:
        None
    """
    return input(f"{color['blue']}{messages}{color['res']}")


def put_agent_output(messages: str):
    """ 执行智能体输出.
    
    Args: 
        messages (str): 系统输出内容。

    Returns:
        None
    
    Raises:
        None
    """
    print(f"{color['res']}● {messages}{color['res']}\n")


def put_agent_other_info(messages: str):
    """ 执行智能体其他信息输出.
    
    Args: 
        messages (str): 其他信息输出内容。

    Returns:
        None
    
    Raises:
        None
    """
    print(f"{color['gray']}● {messages}{color['res']}")
