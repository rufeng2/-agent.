FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt ./backend-requirements.txt
RUN pip install --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple -r backend-requirements.txt

COPY backend/requirements-langchain.txt ./requirements-langchain.txt
RUN pip install --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements-langchain.txt

# 复制源码（开发模式通过 volume 挂载）
COPY backend ./backend
COPY alembic.ini ./alembic.ini

RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
