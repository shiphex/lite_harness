""" 权限判断模块. （当前已经废弃）

该模块用于判断模型传进来的指令是否符合权限要求。
如果指令包含拒绝列表中的内容，会返回错误信息。
如果指令包含潜在破坏性指令，会返回警告信息。
如果指令符合权限要求，会返回 None。

Typical usage example:
    from builtin.permission import check_deny_list
    result = check_deny_list("rm -rf /")
"""

import config
import cli

# 获取项目根目录
WORKDIR = config.Config().get_project_path()

# ═══════════════════════════════════════════════════════════
# Permission 执行前权限判断
# ═══════════════════════════════════════════════════════════

# Gate 1: 检测命令是否在拒绝列表中
# 拒绝列表
DENY_LIST_LINUX = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if=", "> /dev/sda"]
DENY_LIST_POWERSHELL = [
    # 对应 rm -rf / 递归强制删系统盘
    "Remove-Item C:\\* -Recurse -Force",
    "Remove-Item C:\\Windows -Recurse -Force",
    # 对应 sudo 提权高危启动
    "Start-Process powershell -Verb RunAs",
    "Start-Process cmd -Verb RunAs",
    # 对应 shutdown 关机 / reboot 重启
    "Stop-Computer",
    "Restart-Computer",
    "shutdown /s",
    "shutdown /r",
    # 对应 mkfs 磁盘格式化
    "Format-Volume",
    "diskpart",
    "format fs=",
    "clean all",
    # 对应 dd if= 底层磁盘覆写整块硬盘
    "Open-Disk -Access Write",
    "Get-Disk",
    "\\.\PhysicalDrive",
    # 对应 > /dev/sda 直接覆写物理磁盘
    "> \\.\PhysicalDrive",
    # 高危删除简写、递归删除任意根盘
    "rd /s /q C:\\",
    "Remove-Item -Recurse -Force"
]


def check_deny_list(command: str) -> str | None:
    """ 检查命令是否在拒绝列表中.

    Gate 1: 该函数用于检查模型传进来的指令是否在拒绝列表中。
    
    Args:
        command (str): 要检查的指令字符串。
    
    Returns:
        str | None: 如果指令在拒绝列表中，返回错误信息；否则返回 None。
    
    """
    for pattern in DENY_LIST_LINUX + DENY_LIST_POWERSHELL:
        if pattern in command:
            return f"已屏蔽：'{pattern}' 已在拒绝列表中"
        return None
    

# Gate 2: 规则匹配，上下文相关内容的检测
# 潜在破坏性指令列表
DANG_LIST_LINUX = ["rm ", "> /etc/", "chmod 777"]
DANG_LIST_POWERSHELL = [
    # 对应 Linux rm 删除操作
    "Remove-Item",
    "rd /s /q",
    "del /f /s /q",
    # 对应 Linux > /etc/ 覆写系统关键文件
    "> C:\\Windows\\",
    ">> C:\\Windows\\",
    "\\.\\PhysicalDrive",
    "WriteAllText",
    "WriteAllBytes",
    # 对应 Linux chmod 777 放开全部权限
    "icacls",
    "/grant Everyone:F",
    "Set-Acl",
    "Get-Acl",
    "SetAccessRule"
]

# 权限规则
PERMISSION_RULES = [
    {"tools": ["read_file", "write_file"],
     "check": lambda args: not (WORKDIR / args.get("path", "")).resolve().is_relative_to(WORKDIR),
     "message": "尝试访问的文件路径超出工作目录范围。"},
    {"tools": ["powershell"],
     "check": lambda args: any(kw in args.get("command", "") for kw in DANG_LIST_LINUX + DANG_LIST_POWERSHELL),
     "message": "潜在破坏性指令"},
]


def check_rules(tool_name: str, args: dict) -> str | None:
    """ 检查工具调用是否符合权限要求.

    Gate 2: 该函数用于检查模型传进来的工具调用是否符合权限要求。
    
    Args:
        tool_name (str): 要检查的工具名称。
        args (dict): 要检查的工具参数。
    
    Returns:
        str | None: 如果工具调用符合权限要求，返回 None；否则返回警告信息。
    
    """
    for rule in PERMISSION_RULES:
        if tool_name in rule["tools"] and rule["check"](args):
            return rule["message"]
    return None


def ask_user(tool_name: str, args: dict, reason: str) -> str:
    """ 询问用户是否继续执行工具调用.

    Gate 3: 该函数用于询问用户是否继续执行工具调用。用户批准，规则匹配后等待确认。
    
       Args:
        tool_name (str): 要检查的工具名称。
        args (dict): 要检查的工具参数。
        reason (str): 触发用户批准的警告信息。
    
    Returns:
        str: "allow" 或 "deny"，分别表示用户是否同意执行工具调用。
    
    """
    cli.inform_system_info(f"\n⚠ {reason}")
    cli.inform_system_info(f"    Tool: {tool_name}({args})")
    choice = cli.get_user_input("\n    是否继续？(y/N): ").strip().lower()
    return "allow" if choice in ("y", "yes") else "deny"


def check_permission(block) -> bool:
    """ 检查工具调用是否符合权限要求.

    Pipeline: "检测拒绝列表 -> 规则匹配 -> 用户批准" 工具链调用。

    Args:
        block (Block): 包含工具调用信息的 Block 对象。
    
    Returns:
        bool: 如果工具调用符合权限要求，返回 True；否则返回 False。
    
    Raises:
        ValueError: 如果 Block 对象的工具名称不在工具列表中。
    
    """
    # 检测拒绝列表
    if block.name == "powershell":
        reason = check_deny_list(block.input.get("command", ""))
        if reason:
            cli.inform_system_warning(f"\n\033[31m⛔ {reason}\033[0m")
            return False
    
    # 规则匹配
    reason = check_rules(block.name, block.input)
    if reason:
        # 用户批准
        choice = ask_user(block.name, block.input, reason)
        if choice == "deny":
            return False
    return True