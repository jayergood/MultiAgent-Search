from __future__ import annotations

from typing import Any

from langchain_core.messages import ToolMessage

from api.monitor import monitor


def error_result(
    *,
    tool_call_id: str,
    tool_name: str,
    message: str,
    error_type: str,
    context: dict[str, Any] | None = None,
) -> ToolMessage:
    """Build a failed tool result that the Agent and observability layers can detect."""
    artifact = {
        "tool_name": tool_name,
        "error_type": error_type,
        "context": context or {},
    }
    monitor.report_tool_error(
        tool_name=tool_name,
        error_type=error_type,
        message=message,
    )
    return ToolMessage(
        content=message,
        name=tool_name,
        tool_call_id=tool_call_id,
        status="error",
        artifact=artifact,
    )
