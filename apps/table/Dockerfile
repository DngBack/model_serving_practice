# Table inference service - docling-ibm-models TFPredictor (TableFormer)
# Build từ project root: docker compose up -d  hoặc  docker build -f apps/table/Dockerfile -t table:dev .
# Table service cần volume mount weights (xem docker-compose.yml)

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY apps/table/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/table/src/ ./src/

# Optional: copy weights nếu có (nếu không, dùng volume mount hoặc tải từ HF)
# COPY docling-ibm-models/weights/tableformer /app/weights/tableformer

ENV PYTHONUNBUFFERED=1
ENV TABLE_DEVICE=cpu
ENV TABLE_NUM_THREADS=4
EXPOSE 8001

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
