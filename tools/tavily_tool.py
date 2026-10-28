# 定义一个网络搜索的工具！
# ======================== 导入核心依赖 ========================
from typing import Annotated, Literal
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from tavily import TavilyClient

import os
from dotenv import load_dotenv

from api.monitor import monitor
from tools.tool_result import error_result
from utils.retry import retry_with_backoff

# ======================== 初始化配置 ========================
load_dotenv()

# Tavily 客户端（超时 30 秒，防止网络卡死）
tavily_client = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY"),
)


# ======================== 带重试的搜索封装 ========================

@retry_with_backoff(
    max_retries=3,
    base_delay=1.0,
    max_delay=10.0,
    exceptions=(Exception,),
)
def _search_with_retry(query: str, topic: str, max_results: int, include_raw_content: bool):
    """
    对 Tavily 搜索调用包装指数退避重试。
    网络抖动或 Tavily 临时不可用时自动重试，最多 3 次。
    """
    return tavily_client.search(
        query=query,
        topic=topic,
        max_results=max_results,
        include_raw_content=include_raw_content,
    )


# ======================== LangChain 工具定义 ========================

@tool
def internet_search(
    query: str,
    topic: Literal["news", "finance", "general"] = "general",
    max_results: int = 5,
    include_raw_content: bool = False,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str | ToolMessage:
    """
    根据用户问题，进行网络信息搜索！
    注意：主要搜索公开的网络信息！如果指定查询数据库或者rag不能使用此工具！
    :param query: 用户的查询信息
    :param topic: 查询的类型 (general/news/finance)
    :param max_results: 返回的最大条数
    :param include_raw_content: 是否返回原内容 False 精简 True 详细
    :return: 搜索结果
    """
    # 每次调用工具，都向前端推送调用进度
    monitor.report_tool(
        tool_name="网络搜索工具",
        args={
            "query": query,
            "topic": topic,
            "max_results": max_results,
            "include_raw_content": include_raw_content,
        },
    )

    # 带重试的搜索调用（指数退避，最多 3 次）
    try:
        return _search_with_retry(
            query=query,
            topic=topic,
            max_results=max_results,
            include_raw_content=include_raw_content,
        )
    except Exception as exc:
        return error_result(
            tool_call_id=tool_call_id,
            tool_name="internet_search",
            message="网络搜索失败，请稍后重试或改用其他信息来源。",
            error_type=type(exc).__name__,
            context={"query": query, "topic": topic},
        )
