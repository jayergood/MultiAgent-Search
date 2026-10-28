import os
from typing import Annotated
from dotenv import load_dotenv
from api.monitor import monitor
from mysql.connector import connect
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool

from tools.tool_result import error_result

load_dotenv()


# 加载配置文件方便后续使用
def get_db_config():
    """Get database configuration from environment variables."""
    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE"),
        "charset": os.getenv("MYSQL_CHARSET", "utf8mb4"),
        "collation": os.getenv("MYSQL_COLLATION", "utf8mb4_unicode_ci"),
        "autocommit": True,
        "connection_timeout": int(os.getenv("MYSQL_TIMEOUT", "10")),
        "sql_mode": os.getenv("MYSQL_SQL_MODE", "TRADITIONAL"),
    }
    # 移除 None 值（核心必要操作）
    config = {k: v for k, v in config.items() if v is not None}

    # 补充：校验核心配置是否存在（可选但推荐）
    required_keys = ["user", "password", "database"]
    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        raise ValueError(f"缺失数据库核心配置：{', '.join(missing_keys)}")

    return config

@tool
def list_sql_tables(
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str | ToolMessage:
    """
    查询当前库中所有可用的表！
    作用：为了模型识别有哪些可用的表！方便进行后续的自定义sql查询
    :return: 有表： 可用的表有：表1,表2,表3....  没有表: 没有可用的表   出现异常：查询出现异常：异常信息
    """

    # 埋点,调用工具了告诉前端哪个工具被调用了！！
    monitor.report_tool(tool_name="数据库表名查询工具：list_sql_tables", args={})
    # 1. 创建一个链接
    # 2. 创建cursor
    # 3. cursor执行sql语句
    # 4. cursor获取返回结果
    # 5. 释放连接和cursor资源
    # 确保要捕捉异常信息，返回异常提示，避免直接报错！
    try:
        # 加载数据库信息配置
        config = get_db_config()
        # 确保资源使用完毕一定释放 with
        with connect(**config) as  conn:
            with conn.cursor() as cursor:
                sql = "show tables"
                cursor.execute(sql)
                # 捕捉执行结果 要所有的表名称
                # [(表1),(表2),(表3)]
                tables = cursor.fetchall()
                if not tables:
                    return "没有可用的表"
                # 可用的表有：表1,表2,表3....
                # [表1,表2,表3]
                table_names = [table[0] for table in tables]
                return f"可用的表有：{', '.join(table_names)}"
    except Exception as exc:
        return error_result(
            tool_call_id=tool_call_id,
            tool_name="list_sql_tables",
            message="数据库查询失败，请检查数据库配置或稍后重试。",
            error_type=type(exc).__name__,
        )


@tool
def get_table_data(
    table_name,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str | ToolMessage:
    """
    查询指定表名的数据！当前工具调用之前，必须先调用list_sql_tables完成表名的校验！
    此工具的作用：1.可以完成单表数据的查询 2. 可以为多表查询提供表结果信息（列名&数据格式）
    :param table_name: 表名
    :return: csv格式的数据（模拟表格数据格式）
             1.第一行是列信息，列之间使用,（英文的逗号）分割
             2.第二行开始是表数据，值之间也使用,(英文的逗号)分割
             3.行和行之间使用\n分割
             4.至多表数据查询100条
             例如：
                id,name,age\n -> 列头
                1,张三,18\n
                1,张三,18\n    -> 至多查询100条
                1,张三,18\n
                1,张三,18\n
    """
    # 埋点,调用工具了告诉前端哪个工具被调用了！！
    monitor.report_tool(tool_name="数据库表数据查询工具：get_table_data", args={"table_name":table_name})

    # 1. 创建一个链接
    # 2. 创建cursor
    # 3. cursor执行sql语句
    # 4. cursor获取返回结果
    # 5. 释放连接和cursor资源
    # 确保要捕捉异常信息，返回异常提示，避免直接报错！
    try:
        # 获取数据库参数
        config = get_db_config()
        # 1. 创建一个链接
        with connect(**config) as  conn:
            # 2. 创建cursor
            with conn.cursor() as cursor:
                # 3. cursor执行sql语句
                sql = f"select * from {table_name} limit 100"
                cursor.execute(sql)
                # 4. cursor获取返回结果
                # 4.1 获取列的信息
                # 返回的查询结果的列的信息
                # description => [(id,列长度...),(),()]
                # 如果查询没有结果 -》 description 也是None
                description = cursor.description
                if not description:
                    return f"数据表：{table_name}为空没有数据！"
                # 4.2 获取查询结果
                # description =>  [(id,列长度...),(date,....),()] => 元组 index = 0 列名
                # [列1,列2,列3...]
                columns = [ desc[0] for desc in description ] # [1,2,3,4]
                # 表数据
                # [(1,张三),(2,李四),(3,二狗子)]
                rows = cursor.fetchall()
                # (1,张三) -> ('1','张三') -> '1,张三'
                # ['1,张三','1,张三','1,张三','1,张三','1,张三']
                results = [ ",".join(map(str,row)) for row in rows]

                # columns -> csv -> header
                # id,name,age
                header_str = ",".join(columns)
                # '1,张三'\n
                data_str = "\n".join(results)
                return f"{header_str}\n{data_str}"
    except Exception as exc:
        return error_result(
            tool_call_id=tool_call_id,
            tool_name="get_table_data",
            message="数据库查询失败，请检查表名、数据库配置或稍后重试。",
            error_type=type(exc).__name__,
            context={"table_name": table_name},
        )


@tool
def execute_sql_query(
    query,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> str | ToolMessage:
    """
    执行自定义查询sql语句！切记：执行之前，需要通过执行 list_sql_tables明确表名！执行get_table_data
    明确表结构和数据格式！
    :param query: 要执行的自定义sql语句
    :return: csv格式的数据（模拟表格数据格式）
             1.第一行是列信息，列之间使用,（英文的逗号）分割
             2.第二行开始是表数据，值之间也使用,(英文的逗号)分割
             3.行和行之间使用\n分割
             4.至多表数据查询100条
             例如：
                id,name,age\n -> 列头
                1,张三,18\n
                1,张三,18\n    -> 至多查询100条
                1,张三,18\n
                1,张三,18\n
    """
    # 埋点,调用工具了告诉前端哪个工具被调用了！！
    monitor.report_tool(tool_name="数据库表数据查询工具：execute_sql_query", args={"query":query})

    # 1. 创建一个链接
    # 2. 创建cursor
    # 3. cursor执行sql语句
    # 4. cursor获取返回结果
    # 5. 释放连接和cursor资源
    # 确保要捕捉异常信息，返回异常提示，避免直接报错！
    try:
        # 获取数据库参数
        config = get_db_config()
        # 1. 创建一个链接
        with connect(**config) as  conn:
            # 2. 创建cursor
            with conn.cursor() as cursor:
                # 3. cursor执行sql语句
                cursor.execute(query)
                # 4. cursor获取返回结果
                # 4.1 获取列的信息
                # 返回的查询结果的列的信息
                # description => [(id,列长度...),(),()]
                # 如果查询没有结果 -》 description 也是None
                description = cursor.description
                if not description:
                    return f"执行自定义SQL语句查询没有结果，sql为：{query}！"
                # 4.2 获取查询结果
                # description =>  [(id,列长度...),(date,....),()] => 元组 index = 0 列名
                # [列1,列2,列3...]
                columns = [ desc[0] for desc in description ] # [1,2,3,4]
                # 表数据
                # [(1,张三),(2,李四),(3,二狗子)]
                rows = cursor.fetchall()
                # (1,张三) -> ('1','张三') -> '1,张三'
                # ['1,张三','1,张三','1,张三','1,张三','1,张三']
                results = [ ",".join(map(str,row)) for row in rows]

                # columns -> csv -> header
                # id,name,age
                header_str = ",".join(columns)
                # '1,张三'\n
                data_str = "\n".join(results)
                return f"{header_str}\n{data_str}"
    except Exception as exc:
        return error_result(
            tool_call_id=tool_call_id,
            tool_name="execute_sql_query",
            message="数据库查询失败，请检查 SQL、数据库配置或稍后重试。",
            error_type=type(exc).__name__,
        )



if __name__ == "__main__":
    print(execute_sql_query("SELECT * FROM orders WHERE category = '数码电子'"))




