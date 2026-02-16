from pathlib import Path
from typing import Any

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class SampleTool(Tool):
    @property
    def name(self) -> str:
        return "sample"

    @property
    def description(self) -> str:
        return "sample tool"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 2},
                "count": {"type": "integer", "minimum": 1, "maximum": 10},
                "mode": {"type": "string", "enum": ["fast", "full"]},
                "meta": {
                    "type": "object",
                    "properties": {
                        "tag": {"type": "string"},
                        "flags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["tag"],
                },
            },
            "required": ["query", "count"],
        }

    async def execute(self, **kwargs: Any) -> str:
        return "ok"


def test_validate_params_missing_required() -> None:
    tool = SampleTool()
    errors = tool.validate_params({"query": "hi"})
    assert "missing required count" in "; ".join(errors)


def test_validate_params_type_and_range() -> None:
    tool = SampleTool()
    errors = tool.validate_params({"query": "hi", "count": 0})
    assert any("count must be >= 1" in e for e in errors)

    errors = tool.validate_params({"query": "hi", "count": "2"})
    assert any("count should be integer" in e for e in errors)


def test_validate_params_enum_and_min_length() -> None:
    tool = SampleTool()
    errors = tool.validate_params({"query": "h", "count": 2, "mode": "slow"})
    assert any("query must be at least 2 chars" in e for e in errors)
    assert any("mode must be one of" in e for e in errors)


def test_validate_params_nested_object_and_array() -> None:
    tool = SampleTool()
    errors = tool.validate_params(
        {
            "query": "hi",
            "count": 2,
            "meta": {"flags": [1, "ok"]},
        }
    )
    assert any("missing required meta.tag" in e for e in errors)
    assert any("meta.flags[0] should be string" in e for e in errors)


def test_validate_params_ignores_unknown_fields() -> None:
    tool = SampleTool()
    errors = tool.validate_params({"query": "hi", "count": 2, "extra": "x"})
    assert errors == []


async def test_registry_returns_validation_error() -> None:
    reg = ToolRegistry()
    reg.register(SampleTool())
    result = await reg.execute("sample", {"query": "hi"})
    assert "Invalid parameters" in result


class LoopingProvider(LLMProvider):
    def __init__(self, tool_iterations: int, final_content: str | None):
        super().__init__(api_key="test")
        self.tool_iterations = tool_iterations
        self.final_content = final_content
        self.calls: list[dict[str, Any]] = []
        self._next_id = 1

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self.calls.append({"tools": tools, "messages": messages})

        if tools is None:
            return LLMResponse(content=self.final_content)

        if len(self.calls) <= self.tool_iterations:
            call_id = f"tc_{self._next_id}"
            self._next_id += 1
            return LLMResponse(
                content=None,
                tool_calls=[ToolCallRequest(id=call_id, name="list_dir", arguments={"path": "."})],
                finish_reason="tool_calls",
            )

        return LLMResponse(content="normal final response")

    def get_default_model(self) -> str:
        return "test-model"


@pytest.mark.asyncio
async def test_agent_loop_forces_summary_after_max_iterations(tmp_path: Path) -> None:
    provider = LoopingProvider(tool_iterations=2, final_content="forced final response")
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        max_iterations=2,
    )

    final_content, tools_used = await loop._run_agent_loop([{"role": "user", "content": "hello"}])

    assert final_content == "forced final response"
    assert tools_used == ["list_dir", "list_dir"]
    assert provider.calls[-1]["tools"] is None


@pytest.mark.asyncio
async def test_agent_loop_fallback_when_summary_is_empty(tmp_path: Path) -> None:
    provider = LoopingProvider(tool_iterations=1, final_content=None)
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        max_iterations=1,
    )

    final_content, tools_used = await loop._run_agent_loop([{"role": "user", "content": "hello"}])

    assert tools_used == ["list_dir"]
    assert final_content is not None
    assert "I finished running tools (list_dir)" in final_content
