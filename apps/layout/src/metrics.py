"""
Prometheus metrics for Layout inference service.
"""

from prometheus_client import Counter, Histogram

REQUESTS_TOTAL = Counter(
    "layout_requests_total",
    "Total number of predict requests",
    ["status"],
)

INFERENCE_LATENCY = Histogram(
    "layout_inference_latency_seconds",
    "Inference latency in seconds",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

REGIONS_PER_REQUEST = Histogram(
    "layout_regions_per_request",
    "Number of layout regions detected per request",
    buckets=(1, 5, 10, 20, 50, 100, 200),
)
