from __future__ import annotations

import os

import pytest
from langchain_core.messages import ToolMessage
from mysql.connector import Error as DatabaseError

os.environ.setdefault("TAVILY_API_KEY", "tvly-test")
os.environ.setdefault("RAGFLOW_API_KEY", "ragflow-test")
os.environ.setdefault("RAGFLOW_API_URL", "http://localhost:9380")


def invoke_tool(tool, args: dict, call_id: str = "call_test"):
    return tool.invoke(
        {
            "name": tool.name,
            "args": args,
            "id": call_id,
            "type": "tool_call",
        }
    )


def assert_error_message(result, *, call_id: str = "call_test"):
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert result.tool_call_id == call_id
    assert result.artifact["error_type"]
    assert result.content


def test_tool_call_id_is_hidden_from_model_schema():
    from tools import db_tools, markdown_tools, pdf_tools, ragflow_tools, tavily_tool, upload_file_read_tool

    tools = [
        tavily_tool.internet_search,
        db_tools.list_sql_tables,
        db_tools.get_table_data,
        db_tools.execute_sql_query,
        ragflow_tools.get_assistant_list,
        ragflow_tools.create_ask_delete,
        upload_file_read_tool.read_file_content,
        markdown_tools.generate_markdown,
        pdf_tools.convert_md_to_pdf,
    ]

    for tool in tools:
        assert "tool_call_id" not in tool.args


def test_network_search_returns_error_tool_message(monkeypatch):
    from tools import tavily_tool

    def fail_search(**kwargs):
        raise RuntimeError("search backend unavailable")

    monkeypatch.setattr(tavily_tool, "_search_with_retry", fail_search)

    result = invoke_tool(
        tavily_tool.internet_search,
        {
            "query": "AI agents",
            "topic": "general",
            "max_results": 3,
            "include_raw_content": False,
        },
    )

    assert_error_message(result)
    assert "网络搜索失败" in result.content
    assert result.artifact["error_type"] == "RuntimeError"


@pytest.mark.parametrize(
    ("tool_name", "args"),
    [
        ("list_sql_tables", {}),
        ("get_table_data", {"table_name": "orders"}),
        ("execute_sql_query", {"query": "SELECT * FROM orders"}),
    ],
)
def test_database_tools_return_error_tool_message(monkeypatch, tool_name, args):
    from tools import db_tools

    monkeypatch.setattr(
        db_tools,
        "get_db_config",
        lambda: {
            "host": "localhost",
            "user": "test",
            "password": "test",
            "database": "test",
        },
    )

    def fail_connect(**kwargs):
        raise DatabaseError("database unavailable")

    monkeypatch.setattr(db_tools, "connect", fail_connect)

    result = invoke_tool(getattr(db_tools, tool_name), args)

    assert_error_message(result)
    assert "数据库查询失败" in result.content
    assert result.artifact["error_type"] == "Error"


def test_rag_assistant_list_returns_error_tool_message(monkeypatch):
    from tools import ragflow_tools

    def fail_list_chats(**kwargs):
        raise RuntimeError("ragflow unavailable")

    monkeypatch.setattr(ragflow_tools.ragflow_client, "list_chats", fail_list_chats)

    result = invoke_tool(ragflow_tools.get_assistant_list, {})

    assert_error_message(result)
    assert "知识库助手查询失败" in result.content


def test_rag_ask_returns_error_tool_message(monkeypatch):
    from tools import ragflow_tools

    def fail_list_chats(**kwargs):
        raise RuntimeError("ragflow unavailable")

    monkeypatch.setattr(ragflow_tools.ragflow_client, "list_chats", fail_list_chats)

    result = invoke_tool(
        ragflow_tools.create_ask_delete,
        {"chat_name": "运营助手", "question": "退款政策是什么？"},
    )

    assert_error_message(result)
    assert "知识库提问失败" in result.content


def test_missing_uploaded_file_returns_error_tool_message(monkeypatch, tmp_path):
    from tools import upload_file_read_tool

    monkeypatch.setattr(
        upload_file_read_tool,
        "get_session_context",
        lambda: str(tmp_path),
    )

    result = invoke_tool(
        upload_file_read_tool.read_file_content,
        {"filename": "missing.md", "instruction": "提取全文"},
    )

    assert_error_message(result)
    assert result.artifact["error_type"] == "FileNotFoundError"


def test_markdown_write_failure_returns_error_tool_message(monkeypatch):
    from tools import markdown_tools

    def fail_resolve_path(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(markdown_tools, "resolve_path", fail_resolve_path)

    result = invoke_tool(
        markdown_tools.generate_markdown,
        {
            "content": "# report",
            "filename": "report.md",
            "path": "",
        },
    )

    assert_error_message(result)
    assert "Markdown 文件生成失败" in result.content


def test_missing_markdown_for_pdf_returns_error_tool_message(monkeypatch, tmp_path):
    from tools import pdf_tools

    monkeypatch.setattr(
        pdf_tools,
        "get_session_context",
        lambda: str(tmp_path),
    )

    result = invoke_tool(
        pdf_tools.convert_md_to_pdf,
        {"md_filename": "missing.md", "pdf_filename": None},
    )

    assert_error_message(result)
    assert result.artifact["error_type"] == "FileNotFoundError"


def test_pdf_converter_failure_returns_error_tool_message(monkeypatch, tmp_path):
    from tools import pdf_tools

    (tmp_path / "report.md").write_text("# report", encoding="utf-8")
    monkeypatch.setattr(
        pdf_tools,
        "get_session_context",
        lambda: str(tmp_path),
    )

    def fail_conversion(*args, **kwargs):
        raise RuntimeError("word engine unavailable")

    monkeypatch.setattr(
        pdf_tools,
        "convert_md_to_pdf_via_word",
        fail_conversion,
    )

    result = invoke_tool(
        pdf_tools.convert_md_to_pdf,
        {"md_filename": "report.md", "pdf_filename": None},
    )

    assert_error_message(result)
    assert result.artifact["error_type"] == "RuntimeError"
