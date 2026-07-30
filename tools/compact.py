""" 上下文压缩工具 

该工具用于总结早期聊天记录，释放上下文空间。

Typical usage example:
    messages[:] = tool_result_budget(messages)
    messages[:] = snip_compact(messages)
    messages[:] = micro_compact(messages)

    messages[:] = compact_history(messages)
"""

import time
import json
import config
import api


# 内容长度参数
content_length = config.Config().get_content_length()
CHARS_PER_TOKEN_ESTIMATE = content_length["CHARS_PER_TOKEN"]         # 每个 token 大约多少个字符
CTX_TOKENS = content_length["CTX_TOKENS"]                   # 总上下文窗口大小
MAIN_OUTPUT_TOKENS = content_length["MAIN_OUTPUT_TOKENS"]     # 主输出预算
SUMMARY_OUTPUT_TOKENS = content_length["SUMMARY_OUTPUT_TOKENS"]  # 摘要输出预算
SAFETY_TOKENS = content_length["SAFETY_TOKENS"]              # 安全余量
MAX_INLINE_TOOL_RESULT_TOKENS = content_length["MAX_INLINE_TOOL_RESULT_TOKENS"]  # 单个工具调用输出结果触发值（0.1）
MAIN_INPUT_BUDGET = content_length["MAIN_INPUT_BUDGET"]  # 主输入预算（0.65）
SUMMARY_INPUT_BUDGET = content_length["SUMMARY_INPUT_BUDGET"]  # 触发摘要的输入预算（0.8）
COMPACT_TRIGGER_TOKENS = content_length["COMPACT_TRIGGER_TOKENS"]  # 压缩触发阈值（0.4875）

# 工作目录
    # Path.cwd() 返回的是 Path 对象，不是普通字符串。os.getcwd() 返回的是普通字符串。
    # WORKDIR：当前工作目录
    # TOOL_RESULT_DIR：工具调用结果保存目录
WORKDIR = config.Config().get_path_config("project_path")
TOOL_RESULT_DIR = config.Config().get_path_config("tool_result_dir")
TRANSCRIPT_DIR = config.Config().get_path_config("transcript_dir")

# ═══════════════════════════════════════════════════════════
# 上下文压缩
# ═══════════════════════════════════════════════════════════

# ----------------------- L1 裁剪式压缩 ----------------------

def estimate_size(msgs): return len(str(msgs))

def _block_type(block):
    """ 检测 block 的类型
    
    Args:
        block (dict): 要检测的 block。
    
    Returns:
        str: block 的类型，如果是 dict 类型，则返回 type 字段的值，否则返回 None。
    """
    return block.get("type") if isinstance(block, dict) else getattr(block, "type", None)


def _message_has_tool_use(msg):
    """ 检测当前消息是否为模型输出调用工具的消息
    
    Args:
        msg (dict): 聊天记录消息，包含 role 和 content 字段。
    
    Returns:
        False: 如果消息不是 assistant 类型, 则返回 False。
        None: 如果消息内容不是 list 类型, 则返回 None。
        bool: 如果消息内容中包含 tool_use 类型的 block, 则返回 True。
    """
    # 检查消息是否是 assistant 类型
    if msg["role"] != "assistant":
        return False
    
    # 检测消息中是否有 tool_use 类型的 block
    content = msg.get("content")
    if not isinstance(content, list):
        return 
    
    # 检测消息中是否有 tool_use 类型的 block
    return any(_block_type(block) == "tool_use" for block in content)


def _is_tool_message(msg):
    """ 检查当前信息是否是执行工具调用的消息
    
    Args:
        msg (dict): 聊天记录消息，包含 role 和 content 字段。
    
    Returns:
        bool: 如果消息是执行工具调用的消息，则返回 True，否则返回 False。
    """
    # 检查消息是否是 user 类型
    if msg["role"] != "user":
        return False
    
    # 检测消息内容是否是 list 类型,tool 调用在 message 中的填充的 content 是 list 类型的
    content = msg.get("content")
    if not isinstance(content, list):
        return False
    
    # 检查消息内容是否是 tool_use 类型，只要 content 中有一个 block 是 tool_use 类型，就返回 True
    return any(isinstance(block, dict) and block.get("type") == "tool_use" for block in content)



def snip_compact(messages, max_massages = 50):
    """ 裁剪式压缩函数

    该函数用于裁剪聊天记录, 保留最开始的 messages 和最近的 messages, 删除中间的 messages。
    注意：不能把 assistant(tool_use) 和后面的 user(tool_result) 拆开。

    Args:
        messages (list): 聊天记录列表，每个元素是一个字典，包含 role 和 content 字段。
        max_massages (int, optional): 最大保留的消息数。 Defaults to 50.
    
    Returns:
        list: 压缩后的聊天记录列表。
    """
    KEEP_HEAD = 3
    KEEP_TAIL = max_massages - KEEP_HEAD

    # 若消息数量小于等于最大消息数，则直接返回
    if len(messages) <= max_massages:
        return messages
    
    # 若消息数大于最大消息数，则保留最开始的 messages 和最近的 messages
    head_end, tail_start = KEEP_HEAD, len(messages) - KEEP_TAIL

    # 如果 head_end 指向的是 tool_use 类型的消息，则 head_end 加 1，包含这条消息
    if head_end > 0 and _is_tool_message(messages[head_end - 1]):
        head_end += 1

    # 如果 tail_start 指向的是 tool_use 类型的消息，且上一条消息有 Agent 对工具的调用，则 tail_start 减 1，包含这条消息
    if (tail_start > 0 and tail_start < len(messages)
        and _is_tool_message(messages[tail_start])
        and _message_has_tool_use(messages[tail_start - 1])):
        tail_start -= 1

    # 再对工具调用消息进行包含后，再比较 head_end 和 tail_start，判定新的消息段是否就是原 messages
    if tail_start <= head_end:
        return messages

    # 若新的消息段不是原 messages，则返回新的消息段
    snipped = tail_start - head_end
    return messages[:head_end] + \
           [{"role": "user", "content": f"已裁切 {snipped} 条消息"}] + \
           messages[tail_start:]


# --------------- L2 占位符替代旧的工具调用结果 ----------------
KEEP_RECENT = 3
EARLIER_TOOL_RESULTS_MAX_LEN = 120


def _collect_tool_results(messages):
    """ 收集工具调用结果
    
    Args:
        messages (list): 聊天记录列表，每个元素是一个字典，包含 role 和 content 字段。
    
    Returns:
        blocks (list): 包含工具调用结果的元组列表，每个元组包含 messages 索引、 block 索引、 block 内容。
    """
    blocks = []
    # 检索每条 messages 是否是 user 类型的消息，并且 content 是 list 类型
    for mi, msg in enumerate(messages):
        if msg.get("role") != "user" or not isinstance(msg.get("content"), list):
            continue

        # 检索每条 block 中的 tool_result 类型的
        for bi, block in enumerate(msg.get("content")):
            if isinstance(block, dict) and block.get("type") == "tool_result":
                blocks.append((mi, bi, block))  # 以元组的形式存储 messages 索引、 block 索引、 block 内容

    return blocks


def micro_compact(messages):
    """ 旧工具结果占位符替换函数
    
    该函数用于将聊天记录中早期的工具调用结果压缩为占位符，
    以避免占用过多的字符空间。
    
    Args:
        messages (list): 聊天记录列表，每个元素是一个字典，包含 role 和 content 字段。
    
    Returns:
        messages (list): 压缩后的聊天记录列表。
    """

    # 收集工具调用结果
    tool_results = _collect_tool_results(messages)
    if len(tool_results) <= KEEP_RECENT:
        return messages
    
    # 遍历早期的工具调用结果，若长度超过最大长度，则替换为占位符
    for _, _, block in tool_results[:-KEEP_RECENT]:
        if len(block.get("content", "")) > EARLIER_TOOL_RESULTS_MAX_LEN:
            block["content"] = "[早期的工具运行结果已压缩。如有需要，请重新运行。]"
    
    return messages


# ------------------ L3 将大的输出保存到磁盘 ------------------
# 单个工具调用结果的最大字符数
PERSIST_THRESHOLD_CHARS = int(MAX_INLINE_TOOL_RESULT_TOKENS * CHARS_PER_TOKEN_ESTIMATE)   
# 所有工具调用结果之和的最大字符数
TOOL_RESULT_MAX_CHARS = int(COMPACT_TRIGGER_TOKENS * CHARS_PER_TOKEN_ESTIMATE)      

def persist_large_output(tool_use_id, output):
    """ 保存大的输出到磁盘
    
    Args:
        tool_use_id (str): 工具调用 ID。
        output (str): 要保存的大的输出。
    
    Returns:
        str: 包含完整输出所在路径和预览的字符串。
    """
    if len(output) <= PERSIST_THRESHOLD_CHARS:
        return output
    
    TOOL_RESULT_DIR.mkdir(parents = True, exist_ok = True)
    path = TOOL_RESULT_DIR / f"{tool_use_id}.txt"
    if not path.exists():
        path.write_text(output, encoding = "utf-8")

    return f"<persisted-output>\n完整输出所在路径: {path}\n预览:\n{output[:200]}\n</persisted-output>"


def tool_result_budget(messages, max_bytes = TOOL_RESULT_MAX_CHARS):
    """ 工具调用结果大小评估与储存函数
    
    Args:
        messages (list): 聊天记录列表，每个元素是一个字典，包含 role 和 content 字段。
        max_bytes (int): 最大字符数，默认值为 TOOL_RESULT_MAX_CHARS。
    
    Returns:
        messages (list): 压缩后的聊天记录列表。
    """
    last = messages[-1] if messages else None
    if not last or last.get("role") != "user" or not isinstance(last.get("content"), list):
        return messages
    
    # 收集工具调用结果
    blocks = [(ib, block) for ib, block in enumerate(last["content"]) \
              if isinstance(block, dict) \
              and block.get("type") == "tool_result"]
    
    # 若工具调用结果数量小于等于最大数量，则直接返回
    total = sum(len(block.get("content", "")) for _, block in blocks)
    if total <= max_bytes:
        return messages

    # 若工具调用结果数量大于最大数量，则将早期的工具调用结果储存到磁盘中
    ranked = sorted(blocks, key = lambda p: len(str(p[1].get("content", ""))), reverse = True)
    for _, block in ranked:
        if total <= max_bytes: break
        content = str(block.get("content", ""))
        if len(content) <= PERSIST_THRESHOLD_CHARS:
            continue
        tid = block.get("tool_use_id", "Unknown")
        block["content"] = persist_large_output(tid, content)
        # total = sum(len(block.get("content", "")) for _, block in blocks)

    return messages


# ---------------------- L4 LLM 全量摘要 ---------------------
SUMMARY_INPUT_CHARS = int(SUMMARY_INPUT_BUDGET * CHARS_PER_TOKEN_ESTIMATE)

def write_transcript(messages):
    """ 将聊天记录写入到一个文件中
    
    该函数用于将聊天记录写入到一个文件中，
    每个消息占一行，消息之间用换行符隔开。
    
    Args:
        messages (list): 聊天记录列表，每个元素是一个字典，包含 role 和 content 字段。
    
    Returns:
        path (Path): 写入的文件路径。
    """
    TRANSCRIPT_DIR.mkdir(parents = True, exist_ok = True)
    path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.txt"
    with path.open("w", encoding = "utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, default = str) + "\n")

    return path


def summarize_history(messages):
    """ 调用大模型进行总结历史聊天
    
    Args:
        messages (list): 聊天记录列表，每个元素是一个字典，包含 role 和 content 字段。
    
    Returns:
        str: 摘要后的字符串。
    """
    conversation = json.dumps(messages, default = str)[:SUMMARY_INPUT_CHARS]  # 处理前40000个字符（全部的输出）（不太合理，丢弃了后面的）
    prompt = (
        "请总结一下这次编码代理的对话，以便工作能够继续进行。\n"
        "保留以下内容：1. 当前目标，2. 主要发现/决定，3. 已阅读/已更改的文件，"
        "4. 剩余工作，5. 用户限制。\n要简洁明了，具体具体。\n\n" + conversation)
    response = api.call_model(messages = [{"role": "user", "content": prompt}], 
                              model_pattern = "summary")
    
    return "\n".join(getattr(block, "text", "")
                     for block in response.content
                     if getattr(block, "type", None) == "text").strip() or "(空摘要)"


def compact_history(messages):
    """ LLM 全量摘要函数
    
    该函数用于调用大模型进行总结历史聊天，
    并将摘要添加到聊天记录中。
    
    Args:
        messages (list): 聊天记录列表，每个元素是一个字典，包含 role 和 content 字段。
    
    Returns:
        messages (list): 压缩后的聊天记录列表。
    """
    transcript_path = write_transcript(messages)
    print(f"已将历史记录写入到 {transcript_path}")

    summary = summarize_history(messages)
    return [{"role": "user", "content": f"[已压缩]\n\n{summary}"}]
# ═══════════════════════════════════════════════════════════

# ------------------ 应急 reactive_compact -------------------

def reactive_compact(messages):
    """ 反应性压缩函数
    
    该函数用于在 API Error 时调用，
    重新使用 L3 -> L4 进行压缩。
    
    Args:
        messages (list): 聊天记录列表，每个元素是一个字典，包含 role 和 content 字段。
    
    Returns:
        messages (list): 压缩后的聊天记录列表。
    """
    transcript_path = write_transcript(messages)
    tail_start = max(0, len(messages) - 5)
    if (tail_start > 0 and tail_start < len(messages)) \
        and _is_tool_message(messages[tail_start]) \
        and _message_has_tool_use(messages[tail_start - 1]):
        tail_start -= 1

    summary = summarize_history(messages[:tail_start])

    return [{"role": "user", "content": f"[重新执行压缩]\n\n{summary}"}, *messages[tail_start:]]

    