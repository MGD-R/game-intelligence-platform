FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY configs /app/configs

RUN pip install --upgrade pip \
    && pip install -e .[ui]

EXPOSE 8501

CMD ["streamlit", "run", "src/ui/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
