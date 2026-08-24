""" 任务系统 

"""

from dataclasses import dataclass, asdict
from pathlib import Path
import secrets
import json
import re
from .tool_class import ToolContext
import config

TASKS_DIR = config.Config().get_path_config("tasks_path")
TASK_ID_PATTERN = r"^task_[0-9a-f]{8}$"
TASK_ID_RE = re.compile(TASK_ID_PATTERN)


class TaskError(ValueError):
    """可预期的任务工具错误。"""


def _validate_task_id(task_id: str) -> str:
    """校验并返回规范格式的任务 ID。"""
    if not isinstance(task_id, str) or TASK_ID_RE.fullmatch(task_id) is None:
        raise TaskError(
            f"task_id {task_id!r} 必须符合格式 task_[0-9a-f]{{8}}"
        )
    return task_id

@dataclass
class Task:
    """ 任务类 
    Args:
        id (str): 任务 ID
        subject (str): 任务主题
        description (str): 任务描述
        status (str): 任务状态: pending | in_progress | completed
        owner (str | None, optional): 负责当前任务的 Agent. Defaults to None.
        blockedBy (list[str]): 依赖的任务 ID 列表
    """
    id: str
    subject: str
    description: str
    status: str          # pending | in_progress | completed
    owner: str | None    # 负责当前任务的 Agent
    blockedBy: list[str] # 依赖的任务 ID 列表


class TaskStore:

    def __init__(self, directory: Path):
        """ 任务存储类 
        Args:
            directory (Path): 任务存储根目录
        """
        self.directory = directory

    def _root(self, create: bool = False) -> Path:
        """ 获取任务存储根目录
        Args:
            create (bool, optional): 是否创建目录. Defaults to False.
        Returns:
            Path: 任务存储根目录
        """
        if create:
            self.directory.mkdir(parents=True, exist_ok=True)
        return self.directory.resolve()     # 返回绝对路径

    def _path(self, task_id: str, create_root: bool = False) -> Path:
        """ 获取任务存储路径
        Args:
            task_id (str): 任务 ID
            create_root (bool, optional): 是否创建根目录. Defaults to False.
        Returns:
            Path: 任务存储路径
        """
        task_id = _validate_task_id(task_id)
        root = self._root(create = create_root)
        path = (root / f"{task_id}.json").resolve()
        if not path.is_relative_to(root):   # 检查路径是否在根目录下
            raise TaskError(f"task_id {task_id!r} 无效")
        return path

    def exists(self, task_id: str) -> bool:
        """ 检查任务是否存在

        通过检查 task id 对应路径是否存在来判断任务是否存在

        Args:
            task_id (str): 任务 ID
        Returns:
            bool: 任务是否存在
        """
        return self._path(task_id).is_file()
    
    def create(self, subject: str, description: str) -> Task:
        """ 创建任务

        Args:
            subject (str): 任务主题
            description (str): 任务描述
        Returns:
            Task: 创建的任务
        Raises:
            ValueError: 任务主题不能为空
        """
        # 数据预处理
        subject = subject.strip()
        if not subject:
            raise TaskError("任务主题不能为空")

        # 创造 task 储存根目录
        self._root(create = True)

        for _ in range(100):
            task = Task(
                id = f"task_{secrets.token_hex(4)}",
                subject = subject,
                description = description,
                status = "pending",
                owner = None,
                blockedBy = [],
            )
            try:
                with self._path(task_id = task.id, 
                                create_root = True).open("x", encoding="utf-8") as handle:
                    json.dump(asdict(task), handle, indent=2, ensure_ascii=False,)
                return task
            except FileExistsError:
                continue
        raise RuntimeError("无法分配唯一的任务 ID")

    def _depends_on(self, task_id: str, target_id: str)-> bool:
        """ 检查任务 task_id 是否依赖于任务 target_id
        Args:
            task_id (str): 任务 ID
            target_id (str): 依赖任务 ID
        Returns:
            bool: 任务是否依赖于任务
        """
        pending = [task_id]
        visited = set()     # 已访问任务 ID 集合
        while pending:
            current = pending.pop()
            if current == target_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(self.load(current).blockedBy)

        return False

    def update_dependencies(self, 
                            task_id: str, 
                            add_blocked_by: list[str])-> Task:
        """ 更新任务依赖
        
        Args:
            task_id (str): 任务 ID
            add_blocked_by (list[str]): 新的依赖任务 ID 列表
        
        Returns:
            Task: 更新后的任务
        """
        # 前置工作：检查任务是否存在且状态为 pending 且无 owner
        if not isinstance(add_blocked_by, list):
            raise TaskError("addBlockedBy 必须是任务 ID 列表")

        task = self.load(task_id)
        if task.status != "pending" or task.owner is not None:
            raise TaskError("只能更新 pending 状态且无 owner 的任务依赖")

        dependencies = list(dict.fromkeys(add_blocked_by))
        for dependency in dependencies:
            if dependency == task_id:
                raise TaskError("任务不能依赖于自己")
            if not self.exists(dependency):
                raise TaskError(f"依赖任务 {dependency} 不存在")
            # 任务 dependency 依赖于任务 task_id，不能添加到依赖列表
            if dependency not in task.blockedBy and self._depends_on(dependency, task_id):
                raise TaskError(
                    f"依赖任务 {dependency} 依赖于任务 {task_id}，不能添加到依赖列表"
                )

        # 更新任务依赖
        task.blockedBy.extend(
            dependency for dependency in dependencies 
            if dependency not in task.blockedBy
        )

        self.save(task)
        return task

    def save(self, task: Task) -> None:
        """ 保存任务
        
        Args:
            task (Task): 任务对象
        """
        self._path(task.id, create_root = True).write_text(
            json.dumps(asdict(task), indent=2, ensure_ascii=False,),
            encoding="utf-8",
        )

    def load(self, task_id: str) -> Task:
        """ 加载任务
        
        Args:
            task_id (str): 任务 ID
        Returns:
            Task: 任务对象
        """
        task_id = _validate_task_id(task_id)
        path = self._path(task_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise TaskError(f"任务 {task_id!r} 不存在") from exc
        # 用 Task 类包装加载的 json 数据，创建一个 Task 类的实例对象。
        task = Task(**data)
        if task.id != task_id:
            raise TaskError(
                f"任务 ID 与文件名不匹配，文件名: {task_id}, 任务 ID: {task.id}"
            )
        if task.status not in ("pending", "in_progress", "completed"):
            raise TaskError(f"任务状态 {task.status} 无效")
        return task

    def list(self) -> list[Task]:
        """ 列出所有任务
        
        Returns:
            list[Task]: 所有任务的列表
        """
        if not self.directory.exists():
            return []
        root = self._root()
        return [self.load(path.stem)
                for path in sorted(root.glob("task_*.json"))]
    

TASKS = TaskStore(TASKS_DIR)
""" 任务存储实例 """


def create_task(subject: str, description: str) -> Task:
    """ 创建任务
    
    Args:
        subject (str): 任务主题
        description (str): 任务描述
    Returns:
        Task: 创建的任务
    """
    return TASKS.create(subject, description)


def update_task(task_id: str, addBlockedBy: list[str]) -> Task:
    """ 更新任务依赖
    
    Args:
        task_id (str): 任务 ID
        addBlockedBy (list[str]): 新的依赖任务 ID 列表
    """
    return TASKS.update_dependencies(task_id, addBlockedBy)


def load_task(task_id: str) -> Task:
    """ 加载任务
    
    Args:
        task_id (str): 任务 ID
    Returns:
        Task: 任务对象
    """
    return TASKS.load(task_id)


def list_tasks() -> list[Task]:
    """ 列出所有任务
    
    Returns:
        list[Task]: 所有任务的列表
    """
    return TASKS.list()


def get_task(task_id: str) -> str:
    """ 获取任务内容
    
    Args:
        task_id (str): 任务 ID
    Returns:
        str: 任务对象的 JSON 字符串
    """
    return json.dumps(asdict(load_task(task_id)), indent=2)


def incomplete_dependencies(task: Task) -> list[str]:
    """ 获取任务的未完成依赖任务 ID 列表
    
    Args:
        task (Task): 任务对象
    Returns:
        list[str]: 未完成依赖任务 ID 列表
    """
    incomplete = []
    for dependency in task.blockedBy:
        try:
            if load_task(dependency).status != "completed":
                incomplete.append(dependency)
        # 加载失败：文件丢了 / 文件解析出错，也当成未完成依赖
        except (ValueError, FileNotFoundError):
            incomplete.append(dependency)
    return incomplete


def can_start(task_id: str) -> bool:
    """ 判断任务是否可以开始
    
    Args:
        task_id (str): 任务 ID
    Returns:
        bool: 如果任务可以开始，返回 True；否则返回 False
    """
    return not incomplete_dependencies(load_task(task_id))


def claim_task(task_id: str, owner: str = "agent") -> str:
    """ 领取任务
    
    Args:
        task_id (str): 任务 ID
        owner (str, optional): 领取任务的负责人，默认值为 "agent"
    Returns:
        str: 领取任务的确认信息
    """
    task = load_task(task_id)
    if task.status != "pending":
        return f"任务 {task_id} 状态不是 pending，不能被领取"
    dependencies = incomplete_dependencies(task)
    if dependencies:
        return f"任务 {task_id} 有未完成依赖 {dependencies}，不能被领取"
    task.owner = owner
    task.status = "in_progress"
    TASKS.save(task)
    # print(f"  [claim] {task.subject} -> in_progress (owner: {owner})")
    return f"Claimed {task.id} ({task.subject})"


def complete_task(task_id: str, owner: str = "agent") -> str:
    """ 完成任务
    
    完成任务后，检查是否有未完成依赖任务的可以开始
    如果有，解锁该任务

    Args:
        task_id (str): 任务 ID
        owner (str, optional): 完成任务的负责人，默认值为 "agent"
    Returns:
        str: 完成任务的确认信息，以及解锁的任务主题列表
    """
    task = load_task(task_id)
    if task.status != "in_progress":
        return f"任务 {task_id} 处于 {task.status} 状态，不能被完成"
    if task.owner != owner:
        return f"任务 {task_id} 属于 {task.owner} ，不属于 {owner}"

    # 加载所有任务，检查是否有未完成依赖任务的可以开始
    ready_before = {
        candidate.id
        for candidate in list_tasks()
        if candidate.status == "pending"
        and candidate.blockedBy     # 有依赖任务列表
        and can_start(candidate.id)
    }
    task.status = "completed"
    TASKS.save(task)

    unlocked = [candidate.subject for candidate in list_tasks()
                if candidate.status == "pending" 
                and candidate.blockedBy 
                and candidate.id not in ready_before 
                and can_start(candidate.id)]

    # print(f"  [complete] {task.subject}")
    messages = f"Completed {task.id} ({task.subject})"
    if unlocked:
        messages += f"\nUnlocked: {', '.join(unlocked)}"
    return messages


# ------------------------ 外部接口函数 ------------------------
def _task_error_result(error: TaskError) -> str:
    """将可预期的任务错误转换为工具可返回的文本。"""
    return f"Task error: {error}"


def run_create_task(context: ToolContext, subject: str, description: str = "") -> str:
    """ 创建任务
    
    Args:
        subject (str): 任务主题
        description (str, optional): 任务描述，默认值为空字符串
    Returns:
        str: 创建任务的确认信息
    """
    try:
        task = create_task(subject, description)
    except TaskError as exc:
        return _task_error_result(exc)
    return f"Created {task.id}: {task.subject}"


def run_update_task(context: ToolContext, task_id: str, addBlockedBy: list[str]) -> str:
    """ 更新任务
    
    Args:
        task_id (str): 任务 ID
        addBlockedBy (list[str]): 新的依赖任务 ID 列表
    Returns:
        str: 更新任务的确认信息
    """
    try:
        task = update_task(task_id, addBlockedBy)
    except TaskError as exc:
        return _task_error_result(exc)
    dependencies = ", ".join(task.blockedBy) or "(none)"
    return f"Updated {task.id} blockedBy: {dependencies}"


def run_list_tasks(context: ToolContext) -> str:
    """ 列出所有任务
    
    Returns:
        str: 所有任务的列表
    """
    tasks = list_tasks()
    if not tasks:
        return "当前没有任务。可使用 create_task 创建任务。"

    lines = []
    for task in tasks:
        maker = {
            "pending": "[ ]",
            "in_progress": "[>]",
            "completed": "[X]",
        }.get(task.status, "[?]")
        dependencies = (
            f"  blockedBy: {', '.join(task.blockedBy)}"
            if task.blockedBy else ""
        )
        owner = f" [{task.owner}]" if task.owner else ""
        lines.append(
            f"{maker} {task.id}: {task.subject} "
            f"[{task.status}]{owner}{dependencies}"
        )
    return "\n".join(lines)


def run_get_task(context: ToolContext, task_id: str) -> str:
    """ 获取任务内容
    
    Args:
        task_id (str): 任务 ID
    Returns:
        str: 任务对象的 JSON 字符串
    """
    try:
        return get_task(task_id)
    except TaskError as exc:
        return _task_error_result(exc)


def run_claim_task(context: ToolContext, task_id: str) -> str:
    """ 领取任务
    
    Args:
        context (ToolContext): 工具上下文
        task_id (str): 任务 ID
    Returns:
        str: 领取任务的确认信息
    """
    owner_name = context.runtime.agent_name
    try:
        return claim_task(task_id, owner=owner_name)
    except TaskError as exc:
        return _task_error_result(exc)


def run_complete_task(context: ToolContext, task_id: str) -> str:
    """ 完成任务
    
    Args:
        context (ToolContext): 工具上下文
        task_id (str): 任务 ID
    Returns:
        str: 完成任务的确认信息，以及解锁的任务主题列表
    """
    owner_name = context.runtime.agent_name
    try:
        return complete_task(task_id, owner=owner_name)
    except TaskError as exc:
        return _task_error_result(exc)
