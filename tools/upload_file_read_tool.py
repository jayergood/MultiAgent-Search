import logging
from pathlib import Path
from typing import Annotated, Optional

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from api.monitor import monitor
from api.context import get_session_context
from tools.tool_result import error_result
from utils.path_utils import resolve_path

# 尝试导入可选依赖，实现按需加载
try:
    import docx
except ImportError:
    docx = None

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import pandas as pd
except ImportError:
    pd = None


# def read_file_content(filename: str, instruction: str = "提取全部内容") -> str:
#     """
#     读取指定文件的内容。支持 Markdown(.md)、Word(.docx)、PDF(.pdf) 和 Excel(.xlsx/.xls)。
#     对于 Excel 文件，会自动提供数据统计信息（head 和 describe）。

#     Args:
#         filename: 要读取的文件名或路径（支持 .md, .docx, .pdf, .xlsx, .xls）
#         instruction: 对提取内容的具体指令（例如：'提取摘要', '统计数据'）

@tool
def read_file_content(
        filename: Annotated[str, "要读取的文件名或路径（支持 .md, .docx, .pdf, .xlsx, .xls）"],
        instruction: Annotated[str, "对提取内容的具体指令（例如：'提取摘要', '统计数据'）"] = "提取全部内容",
        tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str | ToolMessage:
    """
    读取指定文件的内容。支持 Markdown(.md)、Word(.docx)、PDF(.pdf) 和 Excel(.xlsx/.xls)。
    对于 Excel 文件，会自动提供数据统计信息（head 和 describe）。
    """
    monitor.report_tool("文件内容读取工具", {"filename": filename, "instruction": instruction})

    try:
        # ====================== 1. Path 重构路径解析 ======================
        session_dir = get_session_context()
        file_path = Path(resolve_path(filename, session_dir))  # 转为Path对象

        # 检查文件是否存在（替代os.path.exists）
        if not file_path.exists():
            return error_result(
                tool_call_id=tool_call_id,
                tool_name="read_file_content",
                message=f"文件 '{filename}' 不存在。",
                error_type="FileNotFoundError",
                context={"filename": filename},
            )

        # 获取后缀名（替代os.path.splitext，自动转小写）
        ext = file_path.suffix.lower()

        if ext in ['.md', '.txt']:
            # Path直接读取文本（替代open + os.path）
            return file_path.read_text(encoding='utf-8')

        elif ext == '.docx':
            if docx is None:
                return error_result(
                    tool_call_id=tool_call_id,
                    tool_name="read_file_content",
                    message="读取 Word 文件所需依赖未安装。",
                    error_type="DependencyError",
                    context={"dependency": "python-docx"},
                )
            doc = docx.Document(str(file_path))  # 转字符串传给docx
            full_text = [para.text for para in doc.paragraphs]
            return '\n'.join(full_text)

        elif ext == '.pdf':
            if pypdf is None:
                return error_result(
                    tool_call_id=tool_call_id,
                    tool_name="read_file_content",
                    message="读取 PDF 文件所需依赖未安装。",
                    error_type="DependencyError",
                    context={"dependency": "pypdf"},
                )
            reader = pypdf.PdfReader(str(file_path))  # 转字符串传给pypdf
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
            return text

        elif ext in ['.xlsx', '.xls']:
            if pd is None:
                return error_result(
                    tool_call_id=tool_call_id,
                    tool_name="read_file_content",
                    message="读取 Excel 文件所需依赖未安装。",
                    error_type="DependencyError",
                    context={"dependency": "pandas"},
                )

            try:
                df = pd.read_excel(str(file_path))  # 转字符串传给pandas
            except Exception as e:
                return error_result(
                    tool_call_id=tool_call_id,
                    tool_name="read_file_content",
                    message="读取 Excel 文件失败。",
                    error_type=type(e).__name__,
                    context={"filename": filename},
                )

            result = [
                f"文件: {filename}",
                f"行数: {len(df)}, 列数: {len(df.columns)}",
                f"列名: {', '.join(df.columns.astype(str))}",
                "\n[前5行数据预览]:",
                df.head().to_string(index=False),
                "\n[统计描述]:",
                df.describe().to_string()
            ]
            return "\n".join(result)

        else:
            # 尝试作为纯文本读取
            try:
                return file_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                return error_result(
                    tool_call_id=tool_call_id,
                    tool_name="read_file_content",
                    message=f"不支持的文件格式 '{ext}'，且无法作为文本读取。",
                    error_type="UnicodeDecodeError",
                    context={"filename": filename},
                )

    except Exception as e:
        return error_result(
            tool_call_id=tool_call_id,
            tool_name="read_file_content",
            message="读取文件失败。",
            error_type=type(e).__name__,
            context={"filename": filename},
        )

# ====================== 测试入口（完全按你要求的格式） ======================
if __name__ == '__main__':
    # 1. 固定 session_dir（仅赋值，不Mock）
    def get_session_context():
        return "./test_session_123"

    # 2. 定义测试文件路径
    md_path = "sub_dir/测试文件.md"
    excel_path = "sub_dir/测试数据.xlsx"

    # 3. 测试调用（先测试MD文件，指令用默认）
    result = read_file_content.invoke({
        "name": "read_file_content",
        "args": {"filename": md_path},
        "id": "local_test_call",
        "type": "tool_call",
    })
    print("===== 读取MD文件结果 =====")
    print(result)

    # 可选：测试Excel文件（取消注释即可）
    # result_excel = read_file_content.invoke({
    #     "filename": excel_path,
    #     "instruction": "统计数据"
    # })
    # print("\n===== 读取Excel文件结果 =====")
    # print(result_excel)
