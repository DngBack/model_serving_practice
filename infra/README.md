# Step-by-step: Minikube + KServe (Standard mode)

This guide uses **Minikube** and runs each step as separate commands so you can verify and debug easily. No all-in-one bash scripts.

**Goals:** Run a local Kubernetes cluster, install KServe in Standard mode, deploy the Layout (and optionally Table) inference services as `InferenceService`, and call `/healthz` and `/predict`.

**Tổng quan:** Luồng gồm: (1) Start Minikube (không GPU hoặc có GPU nếu đã cài NVIDIA Container Toolkit), (2) Tạo namespace, (3) Cài metrics-server, (4) Cert Manager, (5) Ingress addon, (6) KServe CRD rồi KServe controller, (7) Build ảnh trong Minikube, (8) Deploy InferenceService layout, (9) Gọi API qua Ingress (Host + NodePort) hoặc port-forward. Form predict: `infra/kserve/predict-form.html` (POST /predict). Các lỗi thường gặp khi chạy được liệt kê ở cuối tài liệu.

---

## Prerequisites

- **Docker** installed and running
- **kubectl** installed
- **Helm** 3.x installed
- **Minikube** installed
- **4+ CPU, 8+ GB RAM** recommended

Verify:

```bash
kubectl version --client
helm version
minikube version
docker info
```

---

## Step 1 — Start Minikube

Start a cluster with enough resources. KServe 0.16 expects Kubernetes 1.32+; use a recent Minikube and optionally pin the Kubernetes version. If you already have a cluster (e.g. v1.34.0), use that version when starting—Minikube does not support downgrading (e.g. `--kubernetes-version=v1.34.0`).

**Without GPU** (recommended if you don't have NVIDIA Container Toolkit):

```bash
minikube delete   # if you had GPU profile and it failed
minikube start --driver=docker --cpus=4 --memory=8192 --kubernetes-version=v1.32.0
```

To **restart** an existing cluster without changing version: `minikube start --kubernetes-version=v1.34.0` (use the version your cluster already has).

**With GPU** (requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) and `nvidia-smi` on host):

```bash
minikube delete
minikube start --driver=docker --container-runtime=docker --gpus=all --cpus=4 --memory=8192 --kubernetes-version=v1.34.0
```

Check that the cluster is up:

```bash
kubectl get nodes
kubectl get ns
```

---

## Step 2 — Create namespaces

From the **repository root**:

```bash
kubectl apply -f infra/cluster/namespaces.yaml
```

This creates:

- `kserve-system` — for KServe controller (may be overridden by Helm)
- `ocr-dev` — where you will deploy Layout and Table InferenceServices

Verify:

```bash
kubectl get ns | grep -E 'kserve-system|ocr-dev'
```

---

## Step 3 — Install metrics-server (for HPA later)

Metrics-server is required for `kubectl top` and for HPA.

```bash
minikube addons enable metrics-server
```

Wait a minute, then check:

```bash
kubectl top nodes
kubectl top pods -A
```

If `top` fails, wait a bit and retry; the metrics-server needs time to scrape.

---

## Step 4 — Install Cert Manager

KServe needs Cert Manager for webhooks (min version 1.15.0).

**4.1 — Add the Helm repo and install:**

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true
```

**4.2 — Wait for pods to be ready:**

```bash
kubectl wait --for=condition=Ready pods -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=120s
```

**4.3 — Verify:**

```bash
kubectl get pods -n cert-manager
```

---

## Step 5 — Install a network controller (Ingress)

KServe needs an Ingress (or Gateway API) to expose services. For Minikube, the simplest is the built-in Ingress addon.

**5.1 — Enable ingress addon:**

```bash
minikube addons enable ingress
```

**5.2 — Wait for ingress controller pods:**

```bash
kubectl get pods -n ingress-nginx -w
```

Stop the watch (Ctrl+C) when the controller pod is `Running`. Then confirm the IngressClass exists:

```bash
kubectl get ingressclass
```

Note the name (often `nginx` or `nginx` under minikube). You will use it when installing KServe (e.g. `--set kserve.controller.gateway.ingressGateway.className=nginx`).

---

## Step 6 — Install KServe (Standard mode)

We install KServe in **Standard** mode (no Knative), using **Ingress** and the class from Step 5.

**6.1 — Install KServe CRDs:**

The OCI chart requires an explicit `--version` (e.g. `v0.16.0`).

```bash
helm install kserve-crd oci://ghcr.io/kserve/charts/kserve-crd --version v0.16.0
```

**6.2 — Create namespace for KServe (if not present):**

```bash
kubectl create namespace kserve --dry-run=client -o yaml | kubectl apply -f -
```

**6.3 — Install KServe controller in Standard mode with Ingress:**

Replace `nginx` with your IngressClass from Step 5.2 if different.

```bash
helm install kserve oci://ghcr.io/kserve/charts/kserve --version v0.16.0 \
  --namespace kserve \
  --set kserve.controller.deploymentMode=Standard \
  --set kserve.controller.gateway.ingressGateway.className=nginx \
  --timeout 5m
```

If you see **"connection refused"** calling `kserve-webhook-server.validator`: the webhook is registered before its pod is ready. Use the workaround in **Troubleshooting** below (delete webhook configs, wait for webhook pod, then `helm upgrade`).

**6.4 — Wait for the controller to be ready:**

```bash
kubectl wait --for=condition=Available deployment/kserve-controller-manager -n kserve --timeout=120s
```

**6.5 — Verify:**

```bash
kubectl get pods -n kserve
kubectl get crd | grep serving.kserve.io
```

---

## Step 7 — Build and load images into Minikube

Your services use custom images `layout:dev` and `table:dev`. Minikube uses its own Docker daemon, so build **inside** Minikube’s Docker environment.

**7.1 — Use Minikube’s Docker:**

```bash
eval $(minikube docker-env)
```

**7.2 — From the repository root, build the Layout image:**

```bash
docker build -f apps/layout/Dockerfile -t layout:dev .
```

**7.3 — (Optional) Build the Table image:**

If you have weights available (e.g. under `docling-ibm-models/weights/tableformer`), you can build and use the table image. For a first run you can skip this and only deploy Layout.

```bash
docker build -f apps/table/Dockerfile -t table:dev .
```

**7.4 — Confirm images:**

```bash
docker images | grep -E 'layout|table'
```

Do **not** run `eval $(minikube docker-env)` in the same shell where you normally build for local Docker; that would point your host Docker to Minikube. Use a dedicated terminal or unset with `eval $(minikube docker-env -u)` when done.

---

## Step 8 — Deploy Layout as an InferenceService

**8.1 — Apply the Layout InferenceService:**

From repo root:

```bash
kubectl apply -f infra/kserve/layout-isvc.yaml -n ocr-dev
```

**8.2 — Watch until the deployment is ready:**

```bash
kubectl get inferenceservice layout -n ocr-dev -w
```

Wait until `READY` is `True`. Then check pods and service:

```bash
kubectl get pods -n ocr-dev -l serving.kserve.io/inferenceservice=layout
kubectl get svc -n ocr-dev
```

**8.3 — Get the service URL (for later):**

```bash
kubectl get inferenceservice layout -n ocr-dev -o jsonpath='{.status.url}'
```

Note the hostname (e.g. `layout-ocr-dev.example.com`). You will use it with the Ingress host/port in the next step.

---

## Step 9 — Expose and call the Layout API

KServe creates an Ingress. On Minikube, the Ingress is usually reached via `minikube ip` and the NodePort or the ingress controller port.

**9.1 — Get Minikube IP and Ingress NodePort:**

```bash
export MINIKUBE_IP=$(minikube ip)
echo "Minikube IP: $MINIKUBE_IP"
```

```bash
kubectl get svc -n ingress-nginx
```

Find the Service that has type `NodePort` (or `LoadBalancer`) and note the **NodePort** for HTTP (e.g. `80:31799/TCP` → use `31799`). From your **browser** you must use this NodePort; port 80 is only inside the cluster.

```bash
export INGRESS_PORT=31799   # use the NodePort from kubectl get svc (e.g. 31799)
```

Optional: to open the URL in a browser with the KServe hostname, add it to hosts:  
`echo "$(minikube ip) layout-ocr-dev.example.com" | sudo tee -a /etc/hosts`  
Then open `http://layout-ocr-dev.example.com:31799/healthz` (you will see JSON; there is no HTML UI).

**9.2 — Set the hostname KServe assigned to the InferenceService:**

```bash
export SERVICE_HOST=$(kubectl get inferenceservice layout -n ocr-dev -o jsonpath='{.status.url}' | sed 's|https\?://||' | cut -d/ -f1)
echo "Host header: $SERVICE_HOST"
```

**9.3 — Health check:**

```bash
curl -v -H "Host: $SERVICE_HOST" "http://${MINIKUBE_IP}:${INGRESS_PORT}/healthz"
```

You should get `200` and a body like `{"status":"ok","ready":true}`.

**9.4 — Predict (replace with a real image path):**

```bash
curl -v -H "Host: $SERVICE_HOST" \
  -F "file=@/path/to/your/image.png" \
  "http://${MINIKUBE_IP}:${INGRESS_PORT}/predict"
```

If the Ingress port is 80, you can omit `:${INGRESS_PORT}`.

**Alternative: port-forward (no Ingress)**

For quick local testing without dealing with Ingress/host header:

```bash
kubectl port-forward -n ocr-dev svc/layout-predictor 8080:80
```

Then in another terminal:

```bash
curl http://localhost:8080/healthz
curl -F "file=@/path/to/image.png" http://localhost:8080/predict
```

To call `/predict` from the **browser** (POST with file): open `infra/kserve/predict-form.html`; set `BASE_URL` to `http://localhost:8080` if using port-forward, or `http://layout-ocr-dev.example.com:31799` if using Ingress (replace 31799 with your NodePort). If the browser blocks (CORS), serve the folder with `python3 -m http.server 8888` and open `http://localhost:8888/predict-form.html`.

---

## Step 10 — (Optional) Deploy Table InferenceService

If you built `table:dev` and have table weights, you can deploy the Table service similarly.

**10.1 — Apply Table InferenceService:**

The Table service may need a PVC or volume for weights; for a minimal test you can use the same image and add a volume in the manifest if required. Example apply:

```bash
kubectl apply -f infra/kserve/table-isvc.yaml -n ocr-dev
```

**10.2 — Check status and call Table API:**

```bash
kubectl get inferenceservice table -n ocr-dev
```

Then use the same pattern as Layout: get `SERVICE_HOST` from status URL and call with `Host` header, or use `kubectl port-forward` to the Table predictor service.

---

## Step 11 — (Optional) HPA for Layout

KServe (Standard mode) creates a Deployment with a generated name (e.g. `layout-predictor-default-xxxxx`). You must target that exact name in the HPA.

**11.1 — Get the predictor deployment name:**

```bash
kubectl get deploy -n ocr-dev
```

Use the deployment name that starts with `layout-predictor-default` (e.g. `layout-predictor-default-00001`).

**11.2 — Create HPA (replace DEPLOY_NAME with the name from 11.1):**

```bash
kubectl autoscale deploy DEPLOY_NAME -n ocr-dev --min=1 --max=10 --cpu-percent=70
```

Example:

```bash
kubectl autoscale deploy layout-predictor-default-00001 -n ocr-dev --min=1 --max=10 --cpu-percent=70
```

**11.3 — Check HPA:**

```bash
kubectl get hpa -n ocr-dev
kubectl top pods -n ocr-dev
```

---

## Troubleshooting

- **KServe install: "connection refused" to kserve-webhook-server.validator:**  
  The webhook is registered before its pod is ready. After the failed `helm install`:
  1. Wait for the webhook server (up to 90s):  
     `kubectl wait --for=condition=Available deployment/kserve-webhook-server -n kserve --timeout=90s 2>/dev/null || true`
  2. Delete KServe validating/mutating webhook configs (so upgrade can create remaining resources):  
     `kubectl get validatingwebhookconfiguration -o name | while read r; do kubectl get "$r" -o jsonpath='{.metadata.name}' | grep -q kserve && kubectl delete "$r"; done`  
     `kubectl get mutatingwebhookconfiguration -o name | while read r; do kubectl get "$r" -o jsonpath='{.metadata.name}' | grep -q kserve && kubectl delete "$r"; done`
  3. Complete install with upgrade:  
     `helm upgrade kserve oci://ghcr.io/kserve/charts/kserve --version v0.16.0 --namespace kserve --set kserve.controller.deploymentMode=Standard --set kserve.controller.gateway.ingressGateway.className=nginx --timeout 5m`

- **InferenceService not Ready:**  
  `kubectl describe inferenceservice layout -n ocr-dev` and `kubectl get pods -n ocr-dev` and `kubectl logs -n ocr-dev -l serving.kserve.io/inferenceservice=layout`.

- **ImagePullBackOff:**  
  Image must be built inside Minikube’s Docker (`eval $(minikube docker-env)` then build). If you see pull errors, rebuild with `imagePullPolicy: Never` in the InferenceService (see `layout-isvc.yaml`).

- **502 / connection refused:**  
  Check Ingress class and that the Ingress resource was created: `kubectl get ingress -n ocr-dev`. Ensure you use the correct `Host` header and port (NodePort or 80).

- **KServe version / Kubernetes version:**  
  If your Minikube uses Kubernetes &lt; 1.32, you may need an older KServe version; check [KServe releases](https://github.com/kserve/kserve/releases) and docs.

---

## Common errors when running (kinh nghiệm khi chạy)

Danh sách lỗi gặp khi chạy theo hướng dẫn: **lỗi là gì**, **tại sao**, **sửa thế nào**, **ở đâu** (bước / file).

| # | Lỗi (thông báo / hiện tượng) | Nguyên nhân | Cách sửa | Ở đâu |
|---|-----------------------------|-------------|----------|--------|
| 1 | `docker: Error response from daemon: could not select device driver "" with capabilities: [[gpu]]` | Profile Minikube được tạo với `--gpus all` nhưng Docker trên host chưa có NVIDIA Container Toolkit (runtime GPU). | **Cách 1:** Cài [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html), cấu hình Docker, restart Docker; sau đó `minikube start ... --gpus=all`. **Cách 2:** Không dùng GPU: `minikube delete` rồi `minikube start ...` **không** có `--gpus`. | **Bước 1** — Start Minikube. README đã tách lệnh “Without GPU” và “With GPU”. |
| 2 | `kubectl top nodes` → `error: Metrics API not available` | Addon metrics-server chưa bật hoặc chưa kịp scrape. | Chạy `minikube addons enable metrics-server`, đợi 1–2 phút rồi chạy lại `kubectl top nodes`. | **Bước 3** — Install metrics-server. Dùng `kubectl get nodes` để xem node; `kubectl top nodes` chỉ hoạt động sau khi có metrics-server. |
| 3 | Cert-manager Helm: `Error: values don't meet the specifications... at '/crds': additional properties 'validation' not allowed` | Chart cert-manager mới không còn option `crds.validation` trong schema. | Bỏ `--set crds.validation=false` khỏi lệnh `helm install cert-manager`. Chỉ dùng `--set installCRDs=true`. | **Bước 4** — Install Cert Manager. README đã bỏ `crds.validation`. |
| 4 | KServe CRD: `Error: unable to locate any tags in provided repository: oci://ghcr.io/kserve/charts/kserve-crd` | Chart OCI bắt buộc phải chỉ định tag/version; Helm không tự chọn “latest”. | Thêm `--version v0.16.0` (hoặc version tương thích) vào lệnh: `helm install kserve-crd oci://ghcr.io/kserve/charts/kserve-crd --version v0.16.0`. | **Bước 6.1** — Install KServe CRDs. README đã ghi rõ dùng `--version`. |
| 5 | KServe install: `failed calling webhook "clusterservingruntime.kserve-webhook-server.validator": ... connection refused` | ValidatingWebhookConfiguration được áp dụng trước khi pod webhook server chạy (thứ tự tài nguyên khi Helm apply). | Sau khi lần `helm install` bị lỗi: (1) Đợi webhook sẵn sàng: `kubectl wait --for=condition=Available deployment/kserve-webhook-server -n kserve --timeout=90s`. (2) Xóa Validating/MutatingWebhookConfiguration của KServe (theo hướng dẫn trong Troubleshooting). (3) Chạy `helm upgrade kserve ...` để tạo nốt tài nguyên. | **Bước 6.3** — Install KServe. README có `--timeout 5m` và workaround trong Troubleshooting. |
| 6 | `Error: release name check failed: cannot reuse a name that is still in use` | Release Helm tên `kserve` đã tồn tại (từ lần cài thất bại trước). | Dùng `helm upgrade kserve ...` thay vì `helm install kserve ...`, hoặc gỡ trước: `helm uninstall kserve -n kserve` rồi `helm install kserve ...`. | **Bước 6** — Khi chạy lại sau lỗi webhook (mục 5). |
| 7 | Minikube: `Exiting due to K8S_DOWNGRADE_UNSUPPORTED: Unable to safely downgrade existing Kubernetes v1.34.0 cluster to v1.32.0` | Minikube không hỗ trợ hạ version Kubernetes; cluster hiện tại đã là v1.34.0. | Dùng đúng version cluster đang có: `minikube start --kubernetes-version=v1.34.0`. Hoặc nếu cần v1.32.0: `minikube delete` rồi tạo cluster mới với `--kubernetes-version=v1.32.0`. KServe 0.16 chạy ổn với 1.34. | **Bước 1** — Restart Minikube. README đã ghi chú dùng version cluster hiện có khi restart. |
| 8 | Mở URL `http://layout-ocr-dev.example.com` trong trình duyệt không thấy gì / không kết nối được | URL trong `status.url` là virtual host; từ máy host cần trỏ hostname về Minikube và dùng **NodePort** (không phải port 80 trong cluster). | **Cách 1 (đơn giản):** `kubectl port-forward -n ocr-dev svc/layout-predictor 8080:80`, mở `http://localhost:8080/healthz`. **Cách 2 (Ingress):** Thêm host vào `/etc/hosts`: `echo "$(minikube ip) layout-ocr-dev.example.com" | sudo tee -a /etc/hosts`. Lấy NodePort: `kubectl get svc -n ingress-nginx` (vd. `80:31799/TCP` → dùng 31799). Mở trong trình duyệt: `http://layout-ocr-dev.example.com:31799/healthz`. | **Bước 9** — Expose và gọi API. README đã nêu rõ dùng NodePort và port-forward. |
| 9 | Mở `/predict` trong trình duyệt → `{"detail":"Method Not Allowed"}` (HTTP 405) | Trình duyệt gửi GET khi mở URL; endpoint `/predict` chỉ chấp nhận POST (thường kèm file ảnh). | Gọi predict bằng POST: `curl -X POST -F "file=@/path/to/image.png" "http://layout-ocr-dev.example.com:31799/predict"`. Hoặc dùng form: mở `infra/kserve/predict-form.html` trong trình duyệt (hoặc serve qua `python3 -m http.server` nếu bị CORS). | **Bước 9** — Gọi predict. File `infra/kserve/predict-form.html` dùng để POST từ trình duyệt. |
| 10 | InferenceService không Ready / ImagePullBackOff | Ảnh `layout:dev` chưa có trong Minikube hoặc chưa build trong Docker của Minikube. | Build ảnh **trong** Minikube: `eval $(minikube docker-env)` rồi build; đảm bảo InferenceService dùng `imagePullPolicy: Never` nếu dùng ảnh local. Xem pod: `kubectl get pods -n ocr-dev` và `kubectl describe pod ... -n ocr-dev`. | **Bước 7–8** — Build image và deploy. File `infra/kserve/layout-isvc.yaml`. |
| 11 | 502 Bad Gateway hoặc connection refused khi gọi qua Ingress | Ingress class sai, hoặc thiếu Host header, hoặc dùng sai port (phải dùng NodePort từ host). | Kiểm tra Ingress: `kubectl get ingress -n ocr-dev`. Gọi curl với đúng Host và NodePort: `curl -H "Host: layout-ocr-dev.example.com" "http://$(minikube ip):31799/healthz"`. | **Bước 5, 9** — Ingress class (Step 5.2), cách gọi (Step 9). |

**Tóm tắt nhanh:**

- **Minikube không start (GPU):** bỏ `--gpus` hoặc cài NVIDIA Container Toolkit.
- **Metrics / cert-manager / KServe CRD:** bật addon, bỏ option không tồn tại, thêm `--version` cho OCI.
- **KServe install fail (webhook):** đợi webhook pod → xóa webhook config → `helm upgrade`.
- **Release name in use:** dùng `helm upgrade` hoặc `helm uninstall` trước.
- **Minikube version:** dùng đúng `--kubernetes-version` của cluster (không downgrade).
- **Truy cập từ browser:** dùng NodePort + Host hoặc port-forward; `/predict` phải gọi bằng POST.

---

## Cleanup

```bash
minikube stop
minikube delete
```

To only remove OCR resources and keep the cluster:

```bash
kubectl delete -f infra/kserve/layout-isvc.yaml -n ocr-dev
kubectl delete -f infra/cluster/namespaces.yaml
```

---

## Next steps (from main README)

- Enforce mTLS and AuthorizationPolicy with Istio (Phase 6).
- Add rate limiting at ingress (Phase 6).
- Async jobs + KEDA for burst scaling (Phase 7).
- Observability: Prometheus/Grafana and dashboards (Phase 9).
