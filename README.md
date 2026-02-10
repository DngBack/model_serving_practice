# model_serving_practice

> **Goal**: Host an model as a **platform** (API + governance) with **autoscaling** and strong **control** (auth, rate limits, policy, observability).
> This repo focuses on a **local-first** setup for rapid iteration and reproducible testing before moving to cloud.

---

## 1) What you will build

### Core capabilities

* **OCR inference service** exposed via HTTP API (`/predict`) with health checks (`/healthz`).
* **Model serving as a platform** using **KServe** `InferenceService` (versioned deployments, rollouts).
* **Autoscaling**

  * **Baseline (required):** Kubernetes **HPA** scaling pods up/down under load.
  * **Optional:** **Scale-to-zero** using **Knative Serving**.
  * **Optional (recommended for bursty OCR):** **Async jobs** + queue + **KEDA** scaling workers by queue length.
* **Control / Governance**

  * **mTLS** internal traffic + **AuthorizationPolicy** via **Istio** (optional but recommended).
  * **Rate limiting** at the ingress gateway (Istio/Envoy).
  * **Audit-friendly logging** and **metrics**.
* **Observability**

  * Prometheus metrics endpoint from the OCR service.
  * (Optional) Prometheus/Grafana dashboards.

### Non-goals (for this repo)

* Training the OCR model (assume you already have a built model artifact).
* GPU performance tuning (you can add later; platform foundation comes first).

---

## 2) Tech stack (local-first)

### Mandatory

* **Docker** (build images)
* **Kubernetes local cluster**: **kind** *or* **minikube**
* **kubectl**
* **Helm**
* **KServe** (standard mode)
* **metrics-server** (for HPA)

### Recommended (control plane)

* **Istio** (service mesh for mTLS + authz + rate limit)

### Optional (advanced autoscaling)

* **Knative Serving** (scale-to-zero)
* **Queue**: RabbitMQ / Redis Streams / Kafka (choose one)
* **KEDA** (event-driven autoscaling for workers)

### Testing & tooling

* Load test: **k6** or **Locust**
* Python service runtime: **FastAPI** (recommended) or Flask
* Observability: Prometheus client library

---

## 3) What to learn (learning path)

> Learn in this order; each step unlocks the next.

1. **Kubernetes fundamentals**: Deployments, Services, Ingress, requests/limits
2. **HPA autoscaling**: how metrics drive replica scaling
3. **KServe basics**: `InferenceService`, predictor container, routing
4. **Istio basics** (recommended): sidecars, mTLS, AuthorizationPolicy
5. **Rate limiting** (Istio/Envoy) for platform protection
6. **Async job architecture** + **KEDA** (optional but recommended for OCR burst)
7. **Knative** (optional) for scale-to-zero/cost-saving semantics

---

## 4) Local setup prerequisites

### Install

* Docker
* kubectl
* Helm
* kind **or** minikube
* (Optional) istioctl
* (Optional) k6/locust

### Resource recommendation (local)

* **CPU:** 4+ cores
* **RAM:** 8+ GB (more if running Istio + monitoring)

---

## 5) Repository structure (suggested)

```
.
├─ apps/
│  ├─ layout/                    # Layout API (LayoutPredictor)
│  │  ├─ Dockerfile
│  │  ├─ src/
│  │  │  ├─ main.py
│  │  │  ├─ model_loader.py
│  │  │  ├─ inference.py
│  │  │  ├─ schemas.py
│  │  │  └─ metrics.py
│  │  └─ requirements.txt
│  └─ table/                     # Table API (TFPredictor)
│     ├─ Dockerfile
│     ├─ src/
│     │  ├─ main.py
│     │  ├─ model_loader.py
│     │  ├─ inference.py
│     │  ├─ schemas.py
│     │  └─ metrics.py
│     └─ requirements.txt
│
├─ infra/
│  ├─ cluster/
│  │  ├─ kind-config.yaml         # or minikube notes
│  │  └─ bootstrap.sh             # create cluster + namespaces
│  ├─ kserve/
│  │  ├─ install.sh               # install KServe + deps
│  │  └─ ocr-isvc.yaml            # InferenceService manifest
│  ├─ autoscaling/
│  │  └─ hpa.yaml                 # optional explicit HPA (if needed)
│  ├─ istio/
│  │  ├─ install.sh
│  │  ├─ mtls-strict.yaml
│  │  ├─ authz-policy.yaml
│  │  └─ rate-limit/              # Envoy rate limit config
│  └─ keda/
│     ├─ install.sh
│     └─ scaledobject.yaml
│
├─ tests/
│  └─ load/
│     ├─ k6_predict.js
│     └─ sample_images/
│
└─ README.md
```

---

## 6) API contract (baseline)

### `GET /healthz`

Returns `200 OK` if ready.

### `POST /predict`

Input:

* `multipart/form-data` with `file=@image.png`

Output (example):

```json
{
  "request_id": "...",
  "text": "...",
  "confidence": 0.97,
  "latency_ms": 123,
  "boxes": [
    {"x1":0, "y1":0, "x2":10, "y2":10, "text":"...", "conf":0.9}
  ]
}
```

---

## 7) Detailed plan — To‑Do checklist (local-first)

### Phase 0 — Decide the local cluster

* [ ] Choose **kind** or **minikube**
* [ ] Ensure Docker works and your machine has enough resources

### Phase 1 — Bootstrap local Kubernetes

* [ ] Create cluster (kind/minikube)
* [ ] Create namespaces: `kserve-system`, `ocr-dev`
* [ ] Install **metrics-server**
* [ ] Verify:

  * [ ] `kubectl get nodes`
  * [ ] `kubectl top nodes` works (metrics available)

### Phase 2 — Build OCR inference service

* [ ] Implement FastAPI service with:

  * [ ] `GET /healthz`
  * [ ] `POST /predict`
  * [ ] `GET /metrics` (Prometheus)
* [ ] Add structured JSON logs:

  * [ ] request_id, tenant_id (header), status_code, latency_ms, payload_size
* [ ] Add basic limits:

  * [ ] max image size
  * [ ] timeout guard
* [ ] Build Docker image:

  * [ ] `ocr:dev`
* [ ] Load image into cluster:

  * [ ] kind: `kind load docker-image ocr:dev`
  * [ ] minikube: build inside minikube Docker env

### Phase 3 — Install KServe (Standard mode)

* [ ] Install KServe and verify controllers are running
* [ ] Apply a sample `InferenceService` to confirm CRDs + routing
* [ ] Document any required ingress setup for local

### Phase 4 — Deploy OCR as `InferenceService`

* [ ] Create `infra/kserve/ocr-isvc.yaml`:

  * [ ] `predictor.containers[0].image = ocr:dev`
  * [ ] requests/limits (CPU/RAM)
  * [ ] readiness/liveness probes
* [ ] Deploy:

  * [ ] `kubectl apply -f infra/kserve/ocr-isvc.yaml`
* [ ] Verify:

  * [ ] `kubectl get inferenceservice -n ocr-dev`
  * [ ] call `/predict` from your host

### Phase 5 — Autoscaling (HPA)

* [ ] Enable/attach HPA for the OCR service
* [ ] Set:

  * [ ] minReplicas = 1
  * [ ] maxReplicas = 10 (adjust)
  * [ ] target CPU util = 60–70%
* [ ] Load test:

  * [ ] run k6/locust against `/predict`
  * [ ] verify replicas scale up/down
* [ ] Capture evidence:

  * [ ] `kubectl get hpa -w`
  * [ ] screenshots/logs

### Phase 6 — Control plane (recommended): Istio security & policy

* [ ] Install Istio
* [ ] Enable sidecar injection for `ocr-dev`
* [ ] Enforce mTLS STRICT
* [ ] Add AuthorizationPolicy:

  * [ ] Only allow ingress gateway → OCR service
  * [ ] Deny all else by default
* [ ] Add rate limit at ingress:

  * [ ] 10 rps per API key (example)
  * [ ] return 429 when exceeded
* [ ] Verify with tests:

  * [ ] unauthorized blocked
  * [ ] rate limit enforced

### Phase 7 (Optional but recommended) — Async jobs + KEDA

* [ ] Add queue (RabbitMQ recommended for simplicity)
* [ ] Create Job API:

  * [ ] `POST /jobs` enqueue
  * [ ] `GET /jobs/{id}` fetch result
* [ ] Create Worker deployment
* [ ] Install KEDA
* [ ] Create ScaledObject:

  * [ ] scale worker replicas based on queue length
* [ ] Load test burst:

  * [ ] enqueue 1k jobs
  * [ ] verify KEDA scales workers and drains queue

### Phase 8 (Optional) — Scale-to-zero with Knative

* [ ] Install Knative Serving
* [ ] Configure OCR service to scale to zero when idle
* [ ] Measure cold start latency and decide whether to keep min=1

### Phase 9 — Observability baseline

* [ ] Ensure `/metrics` is populated
* [ ] (Optional) Install Prometheus + Grafana
* [ ] Create dashboards:

  * [ ] RPS, latency p95/p99
  * [ ] error rate
  * [ ] HPA events / replicas
  * [ ] queue depth (if Phase 7)

### Phase 10 — Local CI-like reproducibility

* [ ] Add `make` targets:

  * [ ] `make cluster-up`, `make cluster-down`
  * [ ] `make kserve-install`
  * [ ] `make deploy-ocr`
  * [ ] `make load-test`
* [ ] Add a “one-command” bootstrap script

---

## 8) Milestones / Acceptance criteria

### Milestone 1 (must-have)

* KServe deploys OCR as `InferenceService`
* HPA scales replicas under load
* `/predict` stable + health checks + metrics

### Milestone 2 (platform control)

* Istio mTLS strict + AuthorizationPolicy
* Ingress rate limiting returns 429 correctly

### Milestone 3 (burst control)

* Async job pipeline + KEDA scales workers by queue depth

---

## 9) References

### KServe

* KServe quickstart: [https://kserve.github.io/website/docs/getting-started/quickstart-guide/](https://kserve.github.io/website/docs/getting-started/quickstart-guide/)
* KServe Kubernetes deployment (standard mode): [https://kserve.github.io/website/docs/admin-guide/kubernetes-deployment](https://kserve.github.io/website/docs/admin-guide/kubernetes-deployment)

### Istio

* Getting Started: [https://istio.io/latest/docs/setup/getting-started/](https://istio.io/latest/docs/setup/getting-started/)
* Istio on kind: [https://istio.io/latest/docs/setup/platform-setup/kind/](https://istio.io/latest/docs/setup/platform-setup/kind/)

### Knative

* Serving architecture: [https://knative.dev/docs/serving/architecture/](https://knative.dev/docs/serving/architecture/)

### KEDA

* Setup scalers: [https://keda.sh/docs/2.18/setupscaler/](https://keda.sh/docs/2.18/setupscaler/)

---

## 10) Next steps

1. Pick **kind vs minikube**.
2. Implement the OCR service skeleton + Docker build.
3. Install KServe and deploy `InferenceService`.
4. Validate HPA with a load test.
5. Add Istio control plane and rate limits.

