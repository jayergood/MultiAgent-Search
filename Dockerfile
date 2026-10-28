# ============================================
# MultiAgent-Search - Docker 镜像
# ============================================
# 注意：Word COM (pywin32) 仅 Windows 可用，
# Docker 环境下 PDF 转换功能不可用，但不影响
# Markdown 报告生成、搜索、数据库查询等功能。
# 如需 Docker 环境下的 PDF 转换，可切换为 WeasyPrint。
# ============================================

FROM python:3.11-slim

LABEL org.opencontainers.image.title="MultiAgent-Search"
LABEL org.opencontainers.image.description="轻量级多智能体协作系统"
LABEL org.opencontainers.image.licenses="MIT"

# 设置工作目录
WORKDIR /app

# 安装系统依赖（MySQL 客户端库 + WeasyPrint 可选依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libcairo2-dev \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
# 跳过 Windows 专用包 (pywin32)，Docker 下不需要
RUN pip install --no-cache-dir \
    $(grep -v 'pywin32\|pywin32-300' requirements.txt) && \
    pip install --no-cache-dir weasyprint

# 复制项目源码
COPY . .

# 创建运行时目录
RUN mkdir -p output updated data

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')" || exit 1

# 启动服务
CMD ["python", "api/server.py"]
