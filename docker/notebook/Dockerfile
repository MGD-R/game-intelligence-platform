FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY configs /app/configs

RUN pip install --upgrade pip \
    && pip install -e . \
    && pip install \
        "jupyterlab>=4.4,<5.0" \
        "ipykernel>=6.30,<7.0" \
        "ipywidgets>=8.1,<9.0" \
        "pandas>=2.2,<3.0" \
        "plotly>=5.24,<6.0" \
        "nbconvert>=7.16,<8.0"

EXPOSE 8888

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]
