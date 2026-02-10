# Table Inference Service

API nhận diện cấu trúc bảng dùng **docling-ibm-models** TFPredictor (TableFormer).

## Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/healthz` | Health check |
| POST | `/predict` | Table structure prediction |
| GET | `/metrics` | Prometheus metrics |

## Input /predict

- **file**: Ảnh chứa bảng
- **table_bboxes**: JSON array `[[x1,y1,x2,y2], ...]` – vị trí các bảng (lấy từ Layout API)
- **iocr_json**: (Optional) IOCR JSON từ docling để match text vào cells

## Chạy

```bash
# Dùng weights từ HF (download lần đầu)
cd apps/table
docker build -t table:dev .
docker run -p 8001:8001 table:dev

# Dùng weights local (build từ project root)
docker build -f apps/table/Dockerfile -t table:dev .
# Cần thêm COPY weights trong Dockerfile hoặc mount volume
```

## Test

```bash
# table_bboxes từ layout API output (boxes có label=Table)
curl -X POST http://localhost:8001/predict \
  -F "file=@image.png" \
  -F 'table_bboxes=[[178,748,1061,976],[177,1163,1062,1329]]'
```

## Pipeline gợi ý

1. Gọi Layout API → lấy `boxes` có `text="Table"`
2. Extract `[x1,y1,x2,y2]` từ mỗi box
3. Gọi Table API với image + table_bboxes
