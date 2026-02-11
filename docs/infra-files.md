# Infra files explained

Detailed explanation of each file under `infra/`.

---

## 1. `infra/cluster/namespaces.yaml`

**Purpose:** Declares two Kubernetes **namespaces** so system and app workloads are separated.

| Field | Meaning |
|-------|--------|
| `apiVersion: v1` | Core Kubernetes API (Namespace is a built-in resource). |
| `kind: Namespace` | Resource type is Namespace. |
| `metadata.name: kserve-system` | Namespace reserved for KServe controller (Helm may install into `kserve` instead; this keeps naming consistent with the main README). |
| `metadata.name: ocr-dev` | **Main app namespace** where Layout and Table InferenceServices and HPA live. |

**Usage:** From repo root: `kubectl apply -f infra/cluster/namespaces.yaml`.

---

## 2. `infra/kserve/layout-isvc.yaml`

**Purpose:** Defines one **InferenceService** for the Layout service. KServe will create a Deployment, Service, and (if configured) Ingress so the `layout:dev` container serves `/healthz` and `/predict`.

| Section | Meaning |
|--------|--------|
| **apiVersion / kind** | KServe CRD `InferenceService` (v1beta1). |
| **metadata.name: layout** | Service name; generated Deployment/Service names will be based on this (e.g. `layout-predictor-default-...`). |
| **metadata.namespace: ocr-dev** | Deploy into `ocr-dev`. |
| **spec.predictor** | Describes the predictor (the container that runs inference). |
| **minReplicas: 1** | At least one replica always; no scale-to-zero here. |
| **containers** | Custom predictor: your image, not a built-in runtime (e.g. sklearn). |
| **image: layout:dev** | Image built from `apps/layout/Dockerfile` with tag `layout:dev`. |
| **imagePullPolicy: Never** | **Important for Minikube:** do not pull from a registry; use the image built **inside** Minikube’s Docker (`eval $(minikube docker-env)` then `docker build ...`). Default `Always` would try to pull from Docker Hub and fail. |
| **ports.containerPort: 8000** | Layout FastAPI listens on 8000; Kubernetes needs this for Service and probes. |
| **resources.requests / limits** | Requests: minimum guaranteed (250m CPU, 512Mi RAM). Limits: cap (2 CPU, 2Gi). Avoids one pod starving the node. |
| **livenessProbe** | Kubernetes calls `GET http://pod:8000/healthz`. If it fails repeatedly, the container is restarted. `initialDelaySeconds: 60` gives the layout model time to load; `periodSeconds: 10` checks every 10s. |
| **readinessProbe** | Same endpoint. If it fails, the pod is removed from the Service (no traffic). `initialDelaySeconds: 30` is shorter so “ready” is detected sooner once the app is up. |

---

## 3. `infra/kserve/table-isvc.yaml`

**Purpose:** Same idea as Layout but for the **Table** (TableFormer) service: custom image `table:dev`, port 8001, with env vars and optional volume placeholders for weights.

| Section | Meaning |
|--------|--------|
| **name / image / port** | InferenceService name `table`, image `table:dev`, container port 8001. |
| **env (TABLE_DEVICE, TABLE_NUM_THREADS)** | Passed into the container (same as in docker-compose): run on CPU with 4 threads. |
| **resources** | Heavier than Layout (500m–2 CPU, 1Gi–4Gi) because TableFormer is more demanding. |
| **Probes (90s / 60s)** | Longer initial delays than Layout because the table model loads slower. |
| **Commented volumeMounts / volumes** | Table needs weights (e.g. under `/app/weights/tableformer`). The comments show how to add a PVC and mount it; uncomment and create the PVC when you use it. |

---

## 4. `infra/autoscaling/layout-hpa.yaml`

**Purpose:** Defines a **HorizontalPodAutoscaler (HPA)** so the Layout predictor Deployment scales up/down by CPU (and optionally other metrics).

| Section | Meaning |
|--------|--------|
| **apiVersion: autoscaling/v2** | HPA v2: supports multiple metrics (CPU, memory, custom). |
| **scaleTargetRef** | What to scale: a Deployment. |
| **name: DEPLOY_NAME** | **Placeholder:** In Standard mode, KServe creates a Deployment with a **generated** name (e.g. `layout-predictor-default-00001`). So you must run `kubectl get deploy -n ocr-dev`, get the real name, and use: `kubectl autoscale deploy <that-name> -n ocr-dev --min=1 --max=10 --cpu-percent=70`. This file is a **reference**; the README tells you to use the imperative command. |
| **minReplicas / maxReplicas** | Between 1 and 10 pods. |
| **metrics (CPU 70%)** | metrics-server reports CPU; when average utilization goes above 70%, HPA adds replicas; when it goes down, it removes them (never below minReplicas). |

---

## 5. `infra/README.md`

**Purpose:** Step-by-step guide to run Minikube + KServe **manually** (no single bash script). Each step is separate commands so you can verify and debug easily.

**Flow summary:**

1. Start Minikube (resources, Kubernetes version).
2. Create namespaces (`kubectl apply -f infra/cluster/namespaces.yaml`).
3. Enable metrics-server addon.
4. Install Cert Manager (Helm).
5. Enable Ingress addon and note IngressClass (e.g. `nginx`).
6. Install KServe (CRDs, then controller in **Standard** mode with that Ingress class).
7. Build images **inside** Minikube (`eval $(minikube docker-env)`, then `docker build`).
8. Deploy Layout InferenceService and wait until Ready.
9. Call the API (Ingress + Host header, or `kubectl port-forward`).
10. (Optional) Deploy Table and/or create HPA with the real deployment name.

The same content is summarized in [setup-minikube.md](setup-minikube.md) with a pointer to `infra/README.md` for the full command list.
