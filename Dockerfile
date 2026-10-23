FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BOTTLENECK_FRONTEND_DIR=/app/frontend/vanilla \
    BOTTLENECK_DATA_DIR=/app/data

WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend ./backend
RUN python -m pip install --upgrade pip && python -m pip install '.[agents]'

COPY data ./data
COPY frontend ./frontend
COPY scripts ./scripts

EXPOSE 8000

CMD ["python", "scripts/start_api.py"]
