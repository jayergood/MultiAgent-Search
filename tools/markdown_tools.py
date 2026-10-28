import logging
from pathlib import Path

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from api.monitor import monitor
from api.context import get_session_context
from tools.tool_result import error_result
from utils.path_utils import resolve_path


# Markdown生成工具
@tool
def generate_markdown(
        content: Annotated[str, "要写入Markdown文档的文本内容"],
        filename: Annotated[str, "Markdown文档的文件名（不包含扩展名或包含.md）"],
        path: Annotated[str, "文件保存的绝对路径"] = "",
        tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str | ToolMessage:
    """根据提供的文本内容，生成对应的Markdown(.md)文件"""
    monitor.report_tool("Markdown文档生成工具", {"写入的文本内容": content})
    if not filename.endswith('.md'):
        filename += '.md'

    try:
        # 获取上下文中的会话目录
        session_dir = get_session_context()

        # --- 路径清洗与重定向逻辑 ---
        # 结合 path 和 filename
        if path and path != ".":
            # 使用 Path 拼接，再转为字符串传给 resolve_path
            full_input_path = str(Path(path) / filename)
        else:
            full_input_path = filename
        full_path_str = resolve_path(full_input_path, session_dir)
        file_path = Path(full_path_str)

        # 获取父目录
        parent_dir = file_path.parent

        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)

        # 使用 Path 直接写入文本
        file_path.write_text(content, encoding='utf-8')

        return f"Markdown文件 '{file_path}' 已成功生成并保存。"
    except Exception as e:
        logging.error(f"写入Markdown文件失败: {e}", exc_info=True)
        return error_result(
            tool_call_id=tool_call_id,
            tool_name="generate_markdown",
            message="Markdown 文件生成失败。",
            error_type=type(e).__name__,
            context={"filename": filename},
        )


# -------------------------- 测试代码（仅修改这里，给session_dir配置固定值） --------------------------
if __name__ == "__main__":
    # ========== 核心：覆盖get_session_context的返回值（仅测试时生效） ==========
    # 不用Mock，直接重新定义这个函数，给session_dir赋值！
    def get_session_context():
        """测试专用：给session_dir配置固定初始化值"""
        return "./test_session_123"  # 你要的session_dir初始化值，随便改

    # ========== 极简测试逻辑（只传path/filename，session_dir已初始化） ==========
    test_content = "# 测试文档\n这是给session_dir配置固定值后的测试内容"
    test_filename = "测试文件"  # 无.md后缀，测试自动补全
    test_path = "sub_dir"       # 相对路径

    # 调用生成函数
    print("===== 开始测试（session_dir已配置为：./test_session_123） =====")
    result = generate_markdown.invoke({
        "name": "generate_markdown",
        "args": {
            "content": test_content,
            "filename": test_filename,
            "path": test_path,
        },
        "id": "local_test_call",
        "type": "tool_call",
    })

    # 验证结果
    print(f"\n调用结果：{result}")
    if "已成功生成" in result:
        file_path = Path(result.split("'")[1])
        print(f"✅ 验证：文件 {file_path} {'存在' if file_path.exists() else '不存在'}")
