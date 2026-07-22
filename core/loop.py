""" Agent 的工作循环 Modules.

该循环负责调用模型接口，执行工具调用，保存模型输出。

Typical usage example:
    from core.loop import agent_loop
    agent_loop(messages)
"""
from pathlib import Path

import cli
import api
import tools
# import builtin
import hook


# 工作目录
    # Path.cwd() 返回的是 Path 对象，不是普通字符串。os.getcwd() 返回的是普通字符串。
    # WORKDIR：当前工作目录
    # TOOL_RESULT_DIR：工具调用结果保存目录
    # SKILL_DIR：技能目录
WORKDIR = Path.cwd()
TOOL_RESULT_DIR = WORKDIR / ".agents" / ".task_output" / "tool_results"
TRANSCRIPT_DIR = WORKDIR / ".agents" / "transcripts"
SKILL_DIR = WORKDIR / ".agents" / "skills"
# skill 注册表
SKILL_REGISTRY: dict[str, dict] = {}

# 设置系统提示词、子智能体系统提示词
SYSTEM = (f"你是一个编码助手，位于 {WORKDIR}，当前系统环境是 Windows。使用 PowerShell 解决任务。行动，无需解释。"
          "在开始任何多步骤任务之前，请使用 todo_write 来规划您的步骤。"
          "随时更新状态。"
          "对于复杂的子问题，可以使用任务工具生成子智能体。"
)

# 记录自上次 todo_write 调用以来的轮数（仅用作演示）
rounds_since_todo = 0


def agent_loop(messages: list):
    """ Agent 的工作循环 object.

    该循环负责调用模型接口，执行工具调用，保存模型输出。
    
    Args:
        messages: 包含用户输入和模型输出的消息列表。
    
    Returns:
        None

    Raises:
        None
    """

    global rounds_since_todo

    while True:

        # (此处只为演示效果)如果模型连续 3 轮未更新待办事项，则注入此提醒
        if rounds_since_todo >= 3 and messages:
            messages.append({"role": "user", "content": "<reminder>请更新待办事项。</reminder>"})
            rounds_since_todo = 0
        
        # 调用模型接口
        response = api.call_model(messages = messages,
                                  system_prompt = SYSTEM,
                                  tools = tools.TOOL_LIST)

        # 保存模型输出
        messages.append({"role": "assistant", "content": response.content})

        # 判断模型返回消息中是否有工具调用
        if response.stop_reason != "tool_use":
            # 触发 Stop hook
            force = hook.trigger_hooks("Stop", messages)
            if force:
                messages.append({"role": "user", "content": force})
            return
        
        # (此处只为演示效果)增加轮数计数器
        rounds_since_todo += 1

        # 初始化模型输出储存列表
        results = []
        # 判断本 block 是否为工具调用
        for block in response.content:
            if block.type != "tool_use":
                continue
            
            # 打印工具调用名称
            cli.put_agent_other_info(f"[TOOL]: {block.name}")

            # 在执行之前，触发 PreToolUse hook
            blocked = hook.trigger_hooks("PreToolUse", block)
            if blocked:
                # 返回并记录 PreToolUse hook 的结果
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(blocked)})
                continue

            # 执行工具调用
            output = tools.call_tool(block.name, block.input)

            # 触发 PostToolUse hook
            hook.trigger_hooks("PostToolUse", block, output)

            # 调用 todo_write 时重置 nag 计数器
            if block.name == "todo_write":
                rounds_since_todo = 0
            
            cli.put_agent_other_info(f"{output[:200]}")
            # 保存工具调用结果
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })

        # 将调用工具的结果作为新消息追加，以供 model 调用（当没有使用压缩工具时）
        messages.append({"role": "user", "content": results})
        continue