# Minikube + KServe setup (summary)

This page summarizes the step-by-step setup. **For the full list of commands**, use **[infra/README.md](../infra/README.md)** — each step is run separately (no all-in-one script) so you can verify and debug easily.

---

## Prerequisites

- Docker, kubectl, Helm, Minikube
- 4+ CPU, 8+ GB RAM recommended

```bash
kubectl version --client
helm version
minikube version
docker info
```

---

## Steps (overview)

| Step | What you do |
|------|--------------|
| **1** | Start Minikube: `minikube start --driver=docker --cpus=4 --memory=8192 --kubernetes-version=v1.32.0` (or your supported version). |
| **2** | Create namespaces: `kubectl apply -f infra/cluster/namespaces.yaml`. |
| **3** | Enable metrics-server: `minikube addons enable metrics-server`. |
| **4** | Install Cert Manager via Helm (repo + install + wait for pods). |
| **5** | Enable ingress: `minikube addons enable ingress`; note IngressClass (e.g. `nginx`). |
| **6** | Install KServe: CRDs → create namespace `kserve` → Helm install controller with `deploymentMode=Standard` and `ingressGateway.className=nginx` (or your class). |
| **7** | Use Minikube’s Docker: `eval $(minikube docker-env)`; from repo root build `layout:dev` (and optionally `table:dev`) with `docker build -f apps/layout/Dockerfile -t layout:dev .`. |
| **8** | Deploy Layout: `kubectl apply -f infra/kserve/layout-isvc.yaml -n ocr-dev`; wait until InferenceService is Ready. |
| **9** | Call API: get Minikube IP and Ingress port, set `SERVICE_HOST` from `kubectl get inferenceservice layout -n ocr-dev -o jsonpath='{.status.url}'`, then `curl -H "Host: $SERVICE_HOST" "http://$MINIKUBE_IP:$INGRESS_PORT/healthz"` or use `kubectl port-forward -n ocr-dev svc/layout-predictor-default 8080:80` and hit `http://localhost:8080/healthz` and `POST /predict`. |
| **10** | (Optional) Deploy Table: `kubectl apply -f infra/kserve/table-isvc.yaml -n ocr-dev`. |
| **11** | (Optional) HPA: `kubectl get deploy -n ocr-dev` to get the real deployment name, then `kubectl autoscale deploy <name> -n ocr-dev --min=1 --max=10 --cpu-percent=70`. |

---

## Important details

- **Images:** Must be built **inside** Minikube’s Docker so the cluster can use them. Use `eval $(minikube docker-env)` in a dedicated shell, then build; do not use your host Docker for the same tags if you set `imagePullPolicy: Never`.
- **Ingress:** KServe creates an Ingress; you need the correct **Host** header (from InferenceService status URL) and the right port (often 80 or the NodePort of the ingress controller).
- **Port-forward:** Easiest for local testing: `kubectl port-forward -n ocr-dev svc/layout-predictor-default 8080:80`, then `curl http://localhost:8080/healthz` and `curl -F "file=@image.png" http://localhost:8080/predict`.

---

## Troubleshooting (see full guide)

- InferenceService not Ready → `kubectl describe inferenceservice layout -n ocr-dev`, `kubectl get pods -n ocr-dev`, `kubectl logs ...`
- ImagePullBackOff → Build image inside Minikube and keep `imagePullPolicy: Never` in the YAML.
- 502 / connection refused → Check Ingress and Host header; try port-forward.

**Full commands and troubleshooting:** [infra/README.md](../infra/README.md).
