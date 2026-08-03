# 简化版模型 API 统一协议

本文解释新增代码的结构。为了和项目现有代码保持一致，新版本尽量使用简单的字典、列表和 dataclass。

## 1. 文件作用

`contract.py` 定义统一请求、响应和响应块；`model_adapter.py` 定义共同调用流程；其余三个文件分别负责 Anthropic、OpenAI Chat 和 Gemini 的格式转换。

Adapter 可以理解成“翻译器”：

```text
ModelRequest → 厂商请求 → 厂商响应 → ModelResponse
```

现有代码的消息本来就是字典，例如：

```python
{"role": "user", "content": "hello"}
```

所以新协议继续使用字典，不创建复杂的消息对象树。

## 2. `contract.py`

`TextPart` 表示文本：

```python
TextPart(text="hello")
```

`ToolCallPart` 表示工具调用：

```python
ToolCallPart(id="call-1", name="read_file", input={"path": "README.md"})
```

这两个对象只是把当前代码中 `SimpleNamespace` 的字段写清楚：`type`、`text`、`id`、`name` 和 `input`。

`ModelRequest` 把一次调用的参数放在一起：

```python
request = ModelRequest(
    model="test-model",
    messages=[{"role": "user", "content": "hello"}],
    system_prompt="你是一个助手。",
    tools=[],
    max_tokens=1024,
)
```

`ModelResponse` 保留了旧代码的使用方式：

```python
response.content
response.stop_reason
```

同时提供 `response.text` 和 `response.tool_calls`，帮助调用方少写遍历代码。

## 3. `model_adapter.py`

适配器只约定三个方法：

```python
def encode_request(self, request):
    raise NotImplementedError

def send(self, payload):
    raise NotImplementedError

def decode_response(self, raw_response):
    raise NotImplementedError
```

这里故意没有使用复杂的 `ABC` 和 `abstractmethod`，因为当前项目更适合直接、容易阅读的写法。

`complete()` 只是把三步串起来：

```python
payload = self.encode_request(request)
response = self.send(payload)
return self.decode_response(response)
```

三个步骤的含义是：内部请求转成厂商请求、调用 SDK、再把厂商响应转回内部响应。

`get_value()` 同时支持字典和 SDK 对象；`json_text()` 把工具参数转换成 JSON 字符串；`tool_schema()` 读取工具参数 schema。

## 4. 三个适配器

`AnthropicAdapter` 的内部消息本身就接近 Anthropic 格式，所以主要是组合 `model`、`messages`、`system`、`tools` 和 `max_tokens`。响应中的 `text block` 转成 `TextPart`，`tool_use` 转成 `ToolCallPart`。

`OpenAIAdapter` 只处理 Chat Completions。它把 system prompt 转成 `role="system"`，把 assistant 的 `tool_use` 转成 `tool_calls`，把工具结果转成 `role="tool"`，并在字典和 JSON 字符串之间转换工具参数。

`GeminiAdapter` 把用户消息转换成 `Content(role="user")`，把助手消息转换成 `Content(role="model")`，再把工具调用和工具结果转换成 `function_call` 与 `function_response`。Gemini 的 `thought_signature` 直接保存在 `ToolCallPart.thought_signature`。

## 5. 一次完整调用

```python
from api.anthropic_adapter import AnthropicAdapter
from api.contract import ModelRequest

adapter = AnthropicAdapter.from_model_config({
    "model_url": "http://localhost:8000",
    "api_key": "no-key",
})

request = ModelRequest(
    model="test-model",
    messages=[{"role": "user", "content": "你好"}],
)

response = adapter.complete(request)
print(response.text)
```

执行顺序就是：`ModelRequest` → `encode_request()` → `send()` → `decode_response()` → `ModelResponse`。

测试时可以直接传入 fake client，因此不需要访问真实 API。

## 6. 为什么暂时不修改旧文件

旧调用链仍然是 `core.loop → api.call_model() → 旧 API 文件`。新增代码暂时是 `ModelRequest → 新 Adapter → ModelResponse`。

两套代码并行，可以先学习和测试，不会破坏当前 Agent。确认稳定后，再让 `call_model()` 使用新的适配器。

## 7. 推荐阅读顺序

先看 `TextPart` 和 `ToolCallPart`，再看 `ModelRequest` 和 `ModelResponse`，然后看 `ModelAdapter.complete()`。之后阅读 OpenAI 的消息转换、Anthropic 的响应转换，最后阅读 Gemini 的 `Content` 和 `Part` 转换。

最重要的主线是：

```text
内部字典消息 → 厂商请求 → 厂商响应 → 统一 ModelResponse
```
