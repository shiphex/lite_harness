""" 权限审批 hook 。

    该 hook 用于判断模型传进来的指令是否符合权限要求。
    如果指令包含拒绝列表中的内容，会返回错误信息。
    如果指令包含潜在破坏性指令，会返回警告信息。
    如果指令符合权限要求，会返回 None。

    Typical usage example:
        import hook
        hook.trigger_hooks("PreToolUse", block, output)
"""

import config
import cli

# 获取项目根目录
WORKDIR = config.Config().get_project_path()

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


def permission_hook(block):
    """ 检查工具调用权限 hook 函数。

    PreToolUse：检查工具调用权限。
    
    Returns:
        str: 如果权限被拒绝，返回拒绝原因。
            "权限已被拒绝列表拒绝"：命令在拒绝列表中。
            "权限已被用户拒绝"：用户拒绝调用该工具。
        None: 如果权限被允许，返回 None。
    """

    # 禁止命令检测
    if block.name == "powershell":
        for pattern in DENY_LIST_LINUX + DENY_LIST_POWERSHELL:
            if pattern in block.input.get("command", ""):
                cli.inform_system_warning(f"⛔ 已屏蔽：'{pattern}' 已在拒绝列表中。")
                return "权限已被拒绝列表拒绝"

    # 规则匹配
    for rule in PERMISSION_RULES:
        if block.name in rule["tools"] and rule["check"](block.input):
            reason = rule["message"]

            # 用户批准
            cli.inform_system_info(f"\n\033[33m⚠ {reason}\033[0m")
            cli.inform_system_info(f"    Tool: {block.name}({block.input})")
            choice = cli.get_user_input("\n    是否继续？(y/N): ").strip().lower()
            if choice not in ("y", "yes"):
                return "权限已被用户拒绝"

    return None