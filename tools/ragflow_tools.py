#  get_assistant_list 获取聊天助手和知识库信息
#  create_ask_delete  创建提问和删除会话获取rag查询结果
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool

# 导入依赖
from ragflow_sdk import RAGFlow #链接rag服务的客户端

from api.monitor import monitor
from rawflow.rag_config import _load_ragflow_env
from tools.tool_result import error_result

# 创建一个ragflow的客户端
api_key , base_url =_load_ragflow_env()
ragflow_client = RAGFlow(api_key=api_key,base_url=base_url)



# 1. 查询现在知识库中有哪些聊天助手和对应知识库的信息 （方便我们知道rag可以给我们提供哪些数据）
@tool
def get_assistant_list(
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str | ToolMessage:
    """
    调用此工具，可以查询ragflow服务器中有哪些助手和助手关联的知识库信息！
    供模型参考，可以从哪个助手获取对应的内部文档信息！
    强调：想向某个助手提问，必须想要调用此工具查询助手的信息和名称
    返回结果： 有-> 名称:助手名称,助手描述：xxxx,关联的知识库：知识库的名、知识库的名字、
             没有 -> 没有任何可用助手
             异常 -> 查询助手信息异常，无可用助手
    :return:
    """

    # 埋点,调用工具了告诉前端哪个工具被调用了！！
    monitor.report_tool(tool_name="ragflow聊天助手列表查询工具：get_assistant_list")

    # 1. 创建ragflow客户端
    try:
        # 2. ragflow客户端查询所有的聊天助手 page: int = 1, page_size: int = 30
        chat_list = ragflow_client.list_chats()
        if not chat_list:
            return "没有任何可用助手"
        # 3. 查询聊天助手的知识库信息
        count_chat_info = "" #存储所有会话信息
        for chat in chat_list:
            dataset_names = []
            dataset_list = chat.datasets #当前聊天助手关联的知识库
            if dataset_list and isinstance(dataset_list,list):
                # 知识库的name
                for dataset in dataset_list:
                    # print(dataset)
                    dataset_names.append(dataset['name']) # 将一个助手的知识库的名字加入到列表中

            # 拼接格式: 助手名称 + 介绍 + 关联知识库列表
            count_chat_info += f"助手名称:{chat.name};功能介绍：{chat.description}; 关联的知识库：{'、'.join(dataset_names)} \n"
        return count_chat_info
    except Exception as exc:
        return error_result(
            tool_call_id=tool_call_id,
            tool_name="get_assistant_list",
            message="知识库助手查询失败，请稍后重试。",
            error_type=type(exc).__name__,
        )

# 2. 对某个助手进行提问（创建会话 -》 提问 -》 删除会话）
@tool
def create_ask_delete(
    chat_name,
    question,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str | ToolMessage:
    """
    想某个助手，创建单次会话进行提问，提问完毕以后会关闭会话！
    主要查询ragflow中相关的信息！
    注意：调用此工具之前，必须先调用 get_assistant_list工具明确查询助手的名字和对应的问题
    :param chat_name: 助手的名字！上一个工具get_assistant_list告诉大模型的只有名字
    :param question: 本次提问的问题
    :return: 返回提问的结果
    """
    # 埋点,调用工具了告诉前端哪个工具被调用了！！
    monitor.report_tool(tool_name="ragflow提问助手工具：create_ask_delete",args={"chat_name":chat_name,"question":question})
    # 1. 创建ragflow客户端
    # 2. 查询对应name的chat
    try:
        chats = ragflow_client.list_chats(name=chat_name)
        use_chat = chats[0] #选中我们要使用的助手
        # 3. chat上创建一个会话
        session = use_chat.create_session(name="temp_session_ask")
        # 4. 使用会话进行提问
        # 返回的提问结果是流式
        response = session.ask(question = question,stream=True)
        # 接收总结果
        result = ""
        # 流的每一部分的对象 part
        for part in response:
            # 数据存在对象中content上！！
            # print(part.content)
            result = part.content
        # 5. 关闭提问的会话
        # chat -> 关闭 -》  session
        use_chat.delete_sessions(ids=[session.id])
        # 6. 返回结果
        return result
    except Exception as exc:
        return error_result(
            tool_call_id=tool_call_id,
            tool_name="create_ask_delete",
            message="知识库提问失败，请稍后重试。",
            error_type=type(exc).__name__,
            context={"chat_name": chat_name},
        )

# if __name__ == '__main__':
#     # print(get_assistant_list())
#     # print(create_ask_delete("你的助手名称", "你的问题"))
