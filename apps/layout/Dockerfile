# Layout inference service - docling-ibm-models LayoutPredictor
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY apps/layout/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/layout/src/ ./src/

ENV PYTHONUNBUFFERED=1
ENV LAYOUT_DEVICE=cpu
ENV LAYOUT_NUM_THREADS=4

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
