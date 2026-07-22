""" PowerShell 工具。

该工具用于执行 PowerShell 命令。

Typical usage example:
    import tools
    result = tools.run_powershell("Get-Process")
"""

import os
import subprocess


def run_powershell(command: str) -> str:
    """ 执行 PowerShell 命令。

    该函数用于执行 PowerShell 命令。
    
    Args:
        command: 要执行的 PowerShell 命令。
        
    Returns:
        命令执行结果。
    """

    # 检查命令是否包含危险字符
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "危险命令，拒绝执行。"
    
    
    # 通过子进程执行命令
    try:
        r = subprocess.run([
                                "powershell",
                                "-NoProfile",
                                "-ExecutionPolicy", "Bypass",
                                "-Command",
                                command,
                            ], 
                            cwd=os.getcwd(),
                            capture_output = True, 
                            encoding='utf-8', errors='ignore',
                            text = True, timeout = 120)
        out = (r.stdout + r.stderr).strip()     # 返回一个已移除开头和结尾空格的字符串副本。
        return out[:5000] if out else "输出为空。"
    except subprocess.TimeoutExpired:
        return "命令执行超时（120s）。"
    except (FileNotFoundError, OSError) as e:
        return f"命令执行失败：{e}"