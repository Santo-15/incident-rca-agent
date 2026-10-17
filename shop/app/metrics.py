from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter(  
    "http_requests_total",  
    "HTTP requests handled by shop-api",  
    ["method", "path", "status"],  
)

LATENCY = Histogram(  
    "http_request_duration_seconds", 
    "Time shop-api took to answer a request",  
    ["method", "path"],  
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),  
)

IN_PROGRESS = Gauge(  
    "http_requests_in_progress", 
    "Requests shop-api is currently handling", 
)

def route_label(request: Request) -> str:  
    route = request.scope.get("route")  
    return route.path if route is not None else "unmatched"