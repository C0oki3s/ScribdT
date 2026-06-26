FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

COPY setup.py README.md filters.json ./
COPY scribd_tool/ scribd_tool/

RUN pip install --no-cache-dir . && \
    python -m spacy download en_core_web_lg && \
    rm -rf /root/.cache/pip /root/.cache/huggingface

ENTRYPOINT ["ScribdT"]
CMD ["--help"]
