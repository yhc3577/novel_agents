# novel-agents 后端（FastAPI + uvicorn）。国内环境默认走清华 PyPI 镜像。
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /srv

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/prompts ./prompts
COPY backend/config ./config
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations

RUN pip install --no-cache-dir -e .

EXPOSE 8000

# 先幂等建表，再启动 uvicorn
CMD ["sh", "-c", "python -m app.db.init_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
