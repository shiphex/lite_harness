import json
from types import SimpleNamespace

import builtin.memory as memory
from api.contract import ModelResponse, TextPart


class FakeAdapter:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return ModelResponse(
            content=[TextPart(next(self.responses))],
            stop_reason="end_turn",
        )


def _runtime():
    return SimpleNamespace(
        policy=SimpleNamespace(
            model={"model_name": "fake-memory-model"},
            tools_list=[{"name": "write_file"}],
        )
    )


def _manager(tmp_path):
    return memory.MemoryManager(
        root=tmp_path / ".agents" / ".memory" / "master",
        policy=memory.MemoryPolicy(
            mode=memory.MemoryMode.READ_WRITE,
            namespace="master",
        ),
    )


def test_memory_requests_use_new_api_without_agent_tools(tmp_path, monkeypatch):
    manager = _manager(tmp_path)
    memory.write_memory_file(manager, "existing", "project", "Existing", "Existing body")
    adapter = FakeAdapter(
        [
            "[0]",
            json.dumps(
                [
                    {
                        "name": "project-detail",
                        "type": "project",
                        "description": "Project detail",
                        "body": "Stored in the master namespace.",
                    }
                ]
            ),
            json.dumps(
                [
                    {
                        "name": "consolidated",
                        "type": "project",
                        "description": "Consolidated memory",
                        "body": "Consolidated body",
                    }
                ]
            ),
        ]
    )
    monkeypatch.setattr(memory, "create_adapter", lambda _config: adapter)
    runtime = _runtime()

    assert manager.load(runtime, [{"role": "user", "content": "project"}])
    manager.extract(runtime, [{"role": "user", "content": "Remember this project detail."}])
    assert (manager.root / "project-detail.md").exists()
    assert "project-detail" in manager.index_path.read_text(encoding="utf-8")

    for index in range(memory.CONSOLIDATE_THRESHOLD):
        memory.write_memory_file(
            manager,
            f"old-{index}",
            "project",
            f"Old {index}",
            f"Old body {index}",
        )
    manager.consolidate(runtime)

    assert len(adapter.requests) == 3
    assert all(request.tools == [] for request in adapter.requests)
    assert (manager.root / "project-detail.md").exists() is False
    assert (manager.root / "consolidated.md").exists()
    assert "consolidated" in manager.index_path.read_text(encoding="utf-8")
