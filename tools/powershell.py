""" PowerShell 工具。

该工具用于执行 PowerShell 命令。

Typical usage example:
    import tools
    result = tools.run_powershell("Get-Process")
"""

import os
import subprocess
import threading
import signal
import time
import atexit
import config
from .tool_class import ToolContext


_shell_process: set[subprocess.Popen] = set()
""" 正在运行的 PowerShell 进程集合。 

    set[subprocess.Popen]：集合里面存放的元素必须是 subprocess.Popen 对象  
    set(): 给变量赋初始值：创建一个空集合。
"""
_shell_process_lock = threading.RLock()
""" 用于保护 _shell_process 集合的锁。 

    RLock：递归锁，允许在同一线程中多次获取锁。  
           1、同一线程，可以多次获取锁；获取多少次，就要 release 多少次。
           2、其他线程，只要锁被占有，就会阻塞等待。
           3、专门用于：同一个函数内部，嵌套调用也需要再次加锁的场景。
"""

def _build_shell_command(command: str) -> list[str]:
    """ 构建平台对应的命令。

    该函数用于根据当前操作系统，构建对应命令解释器的启动参数。

    Args:
        command: 要执行的命令。

    Returns:
        list[str]: 平台对应的命令和启动参数。
    """
    system_info = config.get_system_info()
    if system_info["system"] == "Windows":
        # Windows 使用 PowerShell 执行命令。
        return [
            system_info["executable"],
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command",
            command,
        ]
    # Linux 使用 Bash 执行命令，-l 载入登录环境，-c 执行传入的命令字符串。
    return [system_info["executable"], "-lc", command]


def _process_creation_kwargs() -> dict:
    """ 构建平台对应的进程启动参数。

    该函数用于让命令进程与主进程隔离，便于程序退出或超时时清理子进程。

    Returns:
        dict: subprocess.Popen 使用的进程启动参数。
    """
    if config.get_system_info()["system"] == "Windows":
        # Windows 使用新的进程组，便于 taskkill 终止整个进程树。
        creation_flag = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return {"creationflags": creation_flag} if creation_flag else {}
    # Linux 使用新的会话，使当前进程成为待清理进程组的组长。
    return {"start_new_session": True}


def _stop_process_group(process: subprocess.Popen) -> None:
    """ 停止进程组。

    该函数用于停止进程组。

    Args:
        process: 要停止的进程。
    """
    if config.get_system_info()["system"] == "Windows":
        # Windows 没有 os.killpg，使用 taskkill 的 /T 参数终止整个进程树。
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            # taskkill 返回非零状态时，回退到终止当前进程。
            if getattr(result, "returncode", 0) == 0:
                return
            if process.poll() is None:
                process.terminate()
        except (FileNotFoundError, OSError):
            # taskkill 不可用或执行失败时，至少终止当前进程，避免进程残留。
            try:
                if process.poll() is None:
                    process.terminate()
            except (OSError, AttributeError):
                pass
        return

    # Linux 第一轮 SIGTERM（15）：请求进程组里面所有进程正常退出，进程可以做清理工作、保存数据。
    # sleep 0.05 秒，给一点时间让进程组退出。
    # 如果进程组还活着，第二轮发送 SIGKILL(9) 强制杀死进程组。
    # 某些非 Linux 环境没有 SIGKILL，此时回退使用 SIGTERM，避免模块加载失败。
    force_signal = getattr(signal, "SIGKILL", signal.SIGTERM)
    for sig in (signal.SIGTERM, force_signal):
        try:
            os.killpg(process.pid, sig)     # os.killpg(pgid, signal)：向整个进程组发送信号，而不是单个进程，
                                            # 防止子进程的子进程残留（僵尸 / 孤儿进程）。
        except (OSError, ProcessLookupError):
            # ProcessLookupError：这个 pid 对应的进程组已经不存在了（已经全部退出）
            # OSError：其他系统层面错误，例如进程组早已销毁、权限不足等。
            return
        time.sleep(0.05)


def _stop_all_shell_processes():
    """ 停止所有 PowerShell 进程。

    该函数用于停止所有 PowerShell 进程。
    """
    with _shell_process_lock:
        processes = list(_shell_process)
    for process in processes:
        _stop_process_group(process)


def _handle_termination_signal(signum: int, _frame: None) -> None:
    """ 处理终止信号。

    该函数用于处理终止信号，例如 Ctrl+C。
    """
    _stop_all_shell_processes()
    raise SystemExit(128 + signum)


atexit.register(_stop_all_shell_processes)
""" 注册 _stop_all_shell_processes 函数，在程序退出时调用。

    注册 “程序正常退出时要执行的回调函数”。
        atexit.register(func)：把函数注册到退出钩子。  
        当程序正常结束的时候（不是被系统暴力杀死），会自动调用你注册的函数。
"""
signal.signal(signal.SIGTERM, _handle_termination_signal)
""" 注册 SIGTERM 信号处理函数。

    捕获操作系统发来的信号，自定义信号到来时执行什么逻辑。  
    默认行为：收到 SIGTERM，解释器直接退出，不会跑 atexit 注册的函数。
"""


def _run_bash_process(command: str) -> tuple[str, int | None]:
    """ 执行平台 Shell 命令。

    该函数用于执行 Bash 或 PowerShell 命令。
    
    Args:
        command: 要执行的平台 Shell 命令。
        
    Returns:
        命令执行结果。
    """
    process = None
    try:
        # 使用参数列表直接启动命令解释器，避免 shell=True 在不同平台上的参数解析差异。
        process = subprocess.Popen(
            _build_shell_command(command),
            shell=False,
            cwd = os.getcwd(),
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            text=True,
            encoding='utf-8', errors='ignore',
            **_process_creation_kwargs(),
        )
        with _shell_process_lock:
            _shell_process.add(process)
        stdout, stderr = process.communicate(timeout = 120)
        output = (stdout + stderr).strip()
        return (output[:5000] if output else "(no output)"), process.returncode
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)", None
    except OSError as error:
        return f"Error: {type(error).__name__}: {error}", None
    # 若进程在执行完毕后未退出，尝试强制进程组退出。
    finally:
        if process is not None:
            try:
                _stop_process_group(process)
            except Exception:
                # 清理异常不能覆盖命令执行结果或后台任务状态。
                pass
            finally:
                try:
                    process.wait(timeout = 0.2)
                except (subprocess.TimeoutExpired, OSError):
                    pass
                with _shell_process_lock:
                    _shell_process.discard(process)


def _format_bash_result(output: str, exit_code: int | None) -> str:
    """ 格式化 Bash 命令执行结果。

    该函数用于格式化 Bash 命令执行结果。
    
    Args:
        output: 命令执行输出。
        exit_code: 命令退出码。
        
    Returns:
        str: 格式化后的结果。
    """
    if exit_code in (0, "None"):
        return output
    return f"Error: 命令退出码为 {exit_code}\n{output}"


def run_bash(context: ToolContext, command: str, run_in_background: bool = False) -> str:
    """ 执行 Bash 命令。

    该函数用于执行 Bash 命令。
    
    Args:
        command: 要执行的 Bash 命令。
        run_in_background: 是否在后台运行命令。默认值为 False。
        
    Returns:
        命令执行结果。
    """
    return _format_bash_result(*_run_bash_process(command))


class BackgroundManager:
    def __init__(self):
        """ 初始化后台任务管理器。 
        
        初始化后台任务管理器，用于管理后台任务的执行和结果存储。

            tasks: 任务字典，用于存储后台任务。  
            results: 结果字典，用于存储后台任务执行结果。  
            _ready: 就绪任务列表，用于存储完成执行正等待收集的任务。  
            _counter: 任务计数器，用于生成唯一任务 ID。  
            _lock: 互斥锁，用于保护任务字典和就绪任务列表的并发访问。  
        """
        self.tasks: dict[str, dict] = {}
        self.results: dict[str, str] = {}
        self._ready: list[str] = []
        self._counter = 0
        self._lock = threading.Lock()

    def start(self, block) -> str:
        """ 启动后台任务。
        
        启动后台任务，用于执行 Bash 命令或 PowerShell 命令。
        
        Args:
            block: 包含命令的工具调用块。
            
        Returns:
            任务 ID。
        """
        if block.name != "bash" and block.name != "powershell":
            raise ValueError("只有 Bash 命令和 PowerShell 命令可以在后台运行。")
        command = block.input.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("Bash、PowerShell 命令的命令参数不能为空。")

        with self._lock:
            self._counter += 1
            task_id = f"bg_{self._counter:04d}"
            self.tasks[task_id] = {
                "tool_use_id": block.id,
                "command": command,
                "status": "running",
            }

        thread = threading.Thread(
            target = self._run,
            args = (task_id, command),
            daemon = True,  # 开启守护线程，主线程退出时自动退出。
        )
        try:
            thread.start()
        except Exception:
            with self._lock:
                self.tasks.pop(task_id, None)
            raise
        # print(f"  [background] started {task_id}: {command[:60]}")
        return task_id

    def _run(self, task_id: str, command: str):
        """ 执行后台任务。

        执行后台任务，用于执行 Bash 命令或 PowerShell 命令。
        执行后，将任务状态和结果存储到任务字典和结果字典中。
        
        Args:
            task_id: 任务 ID。
            command: 要执行的命令。
        """
        try:
            output, exit_code = _run_bash_process(command)
            result = _format_bash_result(output, exit_code)
            status = "completed" if exit_code == 0 else "failed"
        except Exception as error:
            result = f"Error: {type(error).__name__}: {error}"
            status = "failed"

        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return
            task["status"] = status
            self.results[task_id] = result
            self._ready.append(task_id)

    def collect(self) -> list[str]:
        """ 收集后台任务结果。
        
        收集后台任务结果，用于获取已完成任务的 ID、状态、命令和摘要。
        
        Returns:
            list[str]: 包含任务通知的 XML 字符串列表。
        """
        with self._lock:
            ready = []
            for task_id in self._ready:
                task = self.tasks.pop(task_id, None)
                result = self.results.pop(task_id, "")
                if task is not None:
                    ready.append((task_id, task, result))
            self._ready.clear()

        notifications = []
        for task_id, task, result in ready:
            notifications.append(
                f"<task_notification>\n"
                f"  <task_id>{task_id}</task_id>\n"
                f"  <status>{task['status']}</status>\n"
                f"  <command>{task['command']}</command>\n"
                f"  <summary>{result[:500]}</summary>\n"
                f"</task_notification>"
            )
            # print(f"  [background] collected {task_id}: {task['status']}")
        return notifications


BACKGROUND = BackgroundManager()
background_tasks = BACKGROUND.tasks
background_results = BACKGROUND.results


def should_run_background(tool_name: str, tool_input: dict) -> bool:
    """ 判断是否应该在后台运行任务。
    
    判断是否应该在后台运行任务，用于确定是否需要启动后台线程。
    该函数判断工具名称是否为 Bash 或 PowerShell，以及工具输入中是否包含 run_in_background 参数。
    
    Args:
        tool_name: 工具名称。
        tool_input: 工具输入参数。
        
    Returns:
        是否应该后台运行任务。
    """
    return (
        (tool_name == "bash" or tool_name == "powershell")
        and tool_input.get("run_in_background") is True
    )


def start_background_task(block) -> str:
    return BACKGROUND.start(block)


def collect_background_results() -> list[str]:
    return BACKGROUND.collect()


def inject_background_results(messages: list) -> int:
    """ 向消息列表中注入后台任务结果。
    
    该函数用于将后台任务结果注入到消息列表中。
    每个任务通知会转换为一个文本块，然后添加到消息列表中。
    
    Args:
        messages: 包含消息的列表，每个消息是一个字典，包含 role 和 content 键。
        
    Returns:
        注入的任务通知数量。
    """
    notifications = collect_background_results()
    if not notifications:
        return 0

    blocks = [{"type": "text", "text": item} for item in notifications]
    if messages and messages[-1].get("role") == "user":
        content = messages[-1].get("content", "")
        if isinstance(content, list):
            content.extend(blocks)
        else:
            messages[-1]["content"] = [
                {"type": "text", "text": str(content)},
                *blocks,
            ]

    else:
        messages.append({"role": "user", "content": blocks})

    return len(notifications)



def run_powershell(context: ToolContext, command: str) -> str:
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
        r = subprocess.run(
                            _build_shell_command(command),
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
