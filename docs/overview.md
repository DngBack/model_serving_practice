# Project overview

## Goal

Host OCR models as a **platform**: API + governance, autoscaling, and control (auth, rate limits, policy, observability). This repo focuses on a **local-first** setup (Minikube) for fast iteration and reproducible testing before moving to cloud.

## What the platform should provide

- **OCR inference API** over HTTP: `/predict`, `/healthz`, `/metrics`
- **Model serving** via **KServe** `InferenceService` (versioned deployments, rollouts)
- **Autoscaling:** HPA (required), optional scale-to-zero (Knative), optional async jobs + queue + KEDA
- **Control:** optional mTLS + AuthorizationPolicy (Istio), rate limiting at ingress, audit logging and metrics
- **Observability:** Prometheus metrics from services; optional Prometheus/Grafana dashboards

**Out of scope for this repo:** training OCR models; GPU tuning (can be added later).

---

## Current state

### Implemented

| Component | Description |
|-----------|-------------|
| **Layout service** | FastAPI app in `apps/layout/`: LayoutPredictor (docling-ibm-models), `/healthz`, `POST /predict` (image), `/metrics`, limits (e.g. 50MB), structured logs |
| **Table service** | FastAPI app in `apps/table/`: TFPredictor (TableFormer), same endpoints; input: image + `table_bboxes` (+ optional `iocr_json`) |
| **Docker** | Dockerfiles for layout and table; `docker-compose.yml` runs both (ports 8000, 8001) |
| **Infra (Minikube)** | `infra/`: namespaces, Layout/Table InferenceService YAMLs, HPA example, step-by-step README (no all-in-one script) |
| **Model library** | `docling-ibm-models/` (Layout, TableFormer, etc.) |

### Not yet done

- Full Kubernetes/KServe deployment (follow [infra/README.md](../infra/README.md) to do it step by step)
- `infra/` automation (e.g. Makefile) — optional
- Istio (mTLS, authz, rate limit)
- KEDA / async jobs
- Load tests (k6/Locust) and sample assets in `tests/load/`

---

## Roadmap (from main README)

1. **Phase 0–1:** Choose Minikube, create cluster, namespaces, metrics-server  
2. **Phase 2:** Build and load images into Minikube  
3. **Phase 3–4:** Install KServe, deploy Layout (and optionally Table) as InferenceService  
4. **Phase 5:** HPA, verify scaling under load  
5. **Phase 6 (optional):** Istio — mTLS, AuthorizationPolicy, rate limiting  
6. **Phase 7 (optional):** Async jobs + queue + KEDA  
7. **Phase 8 (optional):** Knative scale-to-zero  
8. **Phase 9:** Observability (dashboards, alerts)

---

## Tech stack (local)

- **Mandatory:** Docker, Minikube (or kind), kubectl, Helm, KServe (Standard mode), metrics-server  
- **Recommended:** Istio (control plane)  
- **Optional:** Knative, RabbitMQ/Redis/Kafka, KEDA, k6/Locust
