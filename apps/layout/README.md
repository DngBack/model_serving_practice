# Layout Inference Service

API layout detection dùng **docling-ibm-models** LayoutPredictor.

## Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/healthz` | Health check |
| POST | `/predict` | Layout prediction (`file=@image`) |
| GET | `/metrics` | Prometheus metrics |

## Chạy

```bash
cd apps/layout
docker build -t layout:dev .
docker run -p 8000:8000 layout:dev
```

```bash
curl -X POST http://localhost:8000/predict -F "file=@image.png"
```
