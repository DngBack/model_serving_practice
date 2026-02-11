# Documentation

This folder consolidates project and infrastructure documentation.

## Contents

| Document | Description |
|----------|-------------|
| [Overview](overview.md) | Project goal, current state, and roadmap |
| [Infra files explained](infra-files.md) | What each YAML in `infra/` does (namespaces, InferenceServices, HPA) |
| [Minikube setup](setup-minikube.md) | Step-by-step Minikube + KServe setup (summary and link to full guide) |

## Quick links

- **Full step-by-step guide (all commands):** [infra/README.md](../infra/README.md)
- **Layout API:** `apps/layout/` — `GET /healthz`, `POST /predict`, `GET /metrics`
- **Table API:** `apps/table/` — same endpoints, different input (image + table_bboxes)
- **Predict form (local test):** [infra/kserve/predict-form.html](../infra/kserve/predict-form.html) for `POST /predict`

## Repository layout

```
.
├── apps/
│   ├── layout/          # Layout inference service (LayoutPredictor)
│   └── table/           # Table inference service (TFPredictor)
├── docling-ibm-models/   # Model library (Layout, TableFormer, etc.)
├── infra/
│   ├── cluster/         # Namespaces
│   ├── kserve/          # InferenceService manifests + predict form
│   ├── autoscaling/     # HPA example
│   └── README.md        # Full Minikube step-by-step
├── docs/                # This folder — consolidated docs
└── README.md            # Project goal, tech stack, phased plan
```
