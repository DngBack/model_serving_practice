"""
Prometheus metrics for Table inference service.
"""

from prometheus_client import Counter, Histogram

REQUESTS_TOTAL = Counter(
    "table_requests_total",
    "Total number of predict requests",
    ["status"],
)

INFERENCE_LATENCY = Histogram(
    "table_inference_latency_seconds",
    "Inference latency in seconds",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

TABLES_PER_REQUEST = Histogram(
    "table_tables_per_request",
    "Number of tables processed per request",
    buckets=(1, 2, 5, 10, 20),
)
