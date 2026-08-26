"""Git linked-worktree lifecycle for writer teammates.

The coordinator owns this object. A teammate receives only the resulting path;
it never needs to construct or mutate Git worktrees itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess


class WorktreeError(RuntimeError):
    """可预期的 Git worktree 操作错误。"""


@dataclass(frozen=True, slots=True)
class WorktreeHandle:
    """一个 writer teammate 对应的 linked worktree。"""

    member: str
    path: Path
    branch: str
    base_ref: str


class WorktreeManager:
    """为单个 Agent Team 管理 sibling-layout 的 Git worktree。"""

    _MEMBER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")

    def __init__(self, *, repo_root: Path, team_id: str):
        """初始化 worktree manager。

        Worktree 放在主仓库 sibling 目录中，例如
        ``../.lite_harness-worktrees/{team_id}/alice``。
        """

        self.repo_root = Path(repo_root).resolve()
        if not self.repo_root.is_dir():
            raise WorktreeError(f"仓库目录不存在: {self.repo_root}")
        if not isinstance(team_id, str) or not team_id or Path(team_id).name != team_id:
            raise WorktreeError("team_id 不能包含路径分隔符")
        self.team_id = team_id
        self.root = (
            self.repo_root.parent
            / f".{self.repo_root.name}-worktrees"
            / team_id
        ).resolve()

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        """在指定目录执行 Git，并将失败转换成 WorktreeError。"""

        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.repo_root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            raise WorktreeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout.strip()

    def ensure_clean_base(self) -> None:
        """确保 lead 仓库没有未提交修改。"""

        status = self._git("status", "--porcelain", "--untracked-files=all")
        if status:
            raise WorktreeError(
                "创建 writer worktree 前，lead workspace 必须没有未提交修改"
            )

    def _path_for(self, member: str) -> Path:
        if not isinstance(member, str) or self._MEMBER_RE.fullmatch(member) is None:
            raise WorktreeError("worktree member 名称不合法")
        path = (self.root / member).resolve()
        if not path.is_relative_to(self.root):
            raise WorktreeError("worktree 路径超出 team worktree 根目录")
        return path

    def create(self, *, member: str, base_ref: str = "HEAD") -> WorktreeHandle:
        """从 ``base_ref`` 创建并锁定一个 writer worktree。"""

        self.ensure_clean_base()
        path = self._path_for(member)
        branch = f"agent/{self.team_id}/{member}"

        if path.exists():
            raise WorktreeError(f"worktree 已存在: {path}")

        self._git("check-ref-format", "--branch", branch)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._git(
                "worktree",
                "add",
                "--lock",
                "--reason",
                f"lite_harness team {self.team_id} member {member}",
                "-b",
                branch,
                str(path),
                base_ref,
            )
        except Exception:
            # git worktree add 失败时通常不会留下完整 worktree；保留 Git 自己的
            # 状态，让调用方决定是否需要进一步诊断，不强制删除用户目录。
            raise

        return WorktreeHandle(
            member=member,
            path=path,
            branch=branch,
            base_ref=base_ref,
        )

    def status(self, handle: WorktreeHandle | None = None) -> str:
        """返回主仓库或指定 worktree 的 Git 状态。

        不传 handle 时返回 Git worktree 清单；传入 handle 时返回该成员的
        ``git status --short`` 输出，空字符串表示工作区干净。
        """

        if handle is None:
            return self._git("worktree", "list", "--porcelain")
        path = self._validate_handle(handle)
        return self._git("status", "--short", cwd=path)

    def _validate_handle(self, handle: WorktreeHandle) -> Path:
        if not isinstance(handle, WorktreeHandle):
            raise WorktreeError("无效的 worktree handle")
        path = self._path_for(handle.member)
        if path != handle.path.resolve():
            raise WorktreeError("worktree handle 路径不属于当前 team")
        return path

    def remove(self, handle: WorktreeHandle, *, discard: bool = False) -> None:
        """移除 worktree；默认拒绝丢弃未提交修改。

        ``discard=True`` 只应由创建失败等明确的内部回滚路径使用。正常
        shutdown 不会调用此方法，因此不会自动删除 writer 的工作成果。
        """

        path = self._validate_handle(handle)
        if not path.exists():
            return
        if not discard and self.status(handle):
            raise WorktreeError(
                f"worktree {handle.member!r} 仍有未提交修改，不能删除"
            )
        args = ["worktree", "remove"]
        if discard:
            # 一个 force 忽略未提交修改，第二个 force 才允许移除被
            # ``worktree add --lock`` 锁定的 linked worktree。
            args.extend(("--force", "--force"))
        else:
            # worktree 默认会被锁定以避免 prune；Git 要求两个 force 才能
            # 移除 locked worktree。前面的 status 检查保证这里不会丢弃修改。
            args.extend(("--force", "--force"))
        args.append(str(path))
        self._git(*args)
