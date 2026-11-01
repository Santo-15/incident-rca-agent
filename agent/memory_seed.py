from agent.memory import add_incident, get_collection, incident_text, search_similar
from agent.schemas import Finding as F

# 5 past incidents, written from the playbook decision table (docs/playbook.md) and docs/rca/
SEED = [
    dict(id="bad_pool_config-2026-10-26", scenario="bad_pool_config", cause="db_pool_exhausted",
         fix="git revert the bad commit, then ./deploy.sh rollback", source_doc="docs/rca/2026-10-26-bad-pool-config.md",
         alerts=["ShopHighLatency", "ShopHigh5xxRatio", "ShopApiDown"], silent=["PostgresDown", "RedisDown"],
         findings=[F(source="logs", signal="QueuePool limit reached", detail="QueuePool limit of size 1 overflow 0 reached, connection timed out, timeout 30.00 on all DB paths", severity="high"),
                   F(source="metrics", signal="p95 latency", detail="p95 flat at 30 s on /products, /cart, /checkout; 5xx ratio ~92%", severity="high"),
                   F(source="deploys", signal="deploy before first alert", detail="deploy tag a few minutes before ShopHighLatency fired"),
                   F(source="diff", signal="DB_POOL_SIZE lowered", detail="docker-compose.yml DB_POOL_SIZE 20 -> 1", severity="high")]),
    dict(id="kill_db-2026-10-26", scenario="kill_db", cause="postgres_down",
         fix="docker compose start postgres; shop-api reconnects (pool_pre_ping)", source_doc="docs/rca/2026-10-26-kill-db.md",
         alerts=["PostgresDown", "ShopHigh5xxRatio"], silent=["ShopApiDown", "RedisDown"],
         findings=[F(source="logs", signal="failed to resolve host 'postgres'", detail="OperationalError failed to resolve host 'postgres' on all DB paths", severity="high"),
                   F(source="metrics", signal="pg_up", detail="pg_up = 0; 5xx ratio ~90% on DB paths; p95 up from DNS timeouts", severity="high"),
                   F(source="deploys", signal="no recent deploy", detail="no deploy tag near the first alert", severity="low")]),
    dict(id="memory_leak-2026-10-27", scenario="memory_leak", cause="memory_leak",
         fix="git revert the bad commit, then ./deploy.sh rollback", source_doc="docs/rca/2026-10-27-memory-leak.md",
         alerts=["ShopApiHighMemory", "ShopApiRestarted"], silent=["ShopHigh5xxRatio", "ShopHighLatency", "ShopApiDown"],
         findings=[F(source="logs", signal="no error logs", detail="no 'request failed' lines in the window", severity="low"),
                   F(source="metrics", signal="process RSS", detail="RSS climbs in a sawtooth to the 256 MiB limit, restart count goes up", severity="high"),
                   F(source="deploys", signal="deploy before first alert", detail="deploy tag shortly before ShopApiHighMemory fired"),
                   F(source="diff", signal="unbounded list added", detail="shop code appends every request to a module-level list that is never cleared", severity="high")]),
    dict(id="slow_query-2026-10-27", scenario="slow_query", cause="slow_query",
         fix="CREATE INDEX ix_products_price ON products (price);", source_doc="docs/rca/2026-10-27-slow-query.md",
         alerts=["ShopHighLatency"], silent=["ShopHigh5xxRatio", "ShopApiDown", "PostgresDown", "RedisDown"],
         findings=[F(source="logs", signal="slow requests, no errors", detail="no 'request failed' lines; only high duration_ms on /products"),
                   F(source="metrics", signal="seq_tup_read on products", detail="seq_tup_read on products jumps from 0 to millions of rows/s; p95 high only on /products", severity="high"),
                   F(source="deploys", signal="no recent deploy", detail="no deploy tag near the first alert", severity="low")]),
    dict(id="redis_down-2026-10-27", scenario="redis_down", cause="redis_down",
         fix="docker compose start redis; carts return from AOF", source_doc="docs/rca/2026-10-27-redis-down.md",
         alerts=["RedisDown", "ShopHigh5xxRatio", "ShopHighLatency"], silent=["PostgresDown", "ShopApiDown"],
         findings=[F(source="logs", signal="Error -2 connecting to redis:6379", detail="Error -2 connecting to redis:6379 on /cart and /checkout", severity="high"),
                   F(source="metrics", signal="redis_up", detail="redis_up = 0; ~25% 5xx only on /cart and /checkout; /products 0 failures", severity="high"),
                   F(source="deploys", signal="no recent deploy", detail="no deploy tag near the first alert", severity="low")]),
]

# 3 test queries: a new kill_db-like incident, the same with leakage guard, and an incident type memory has never seen
NEW_DB = incident_text(
    ["PostgresDown since 06:02:11 UTC", "ShopHigh5xxRatio since 06:03:00 UTC"], ["ShopApiDown", "RedisDown"],
    [F(source="logs", signal="connection refused", detail="OperationalError connection to postgres:5432 refused on /products and /cart"),
     F(source="metrics", signal="pg_up", detail="pg_up = 0 since 06:01 UTC")])
UNSEEN = incident_text(
    ["ShopDiskAlmostFull since 07:10:00 UTC"], ["PostgresDown", "RedisDown"],
    [F(source="logs", signal="No space left on device", detail="OSError Errno 28 No space left on device while writing logs")])


def show(title: str, hits: list[dict]) -> None:
    print(f"\n{title}")
    for h in hits or [{"distance": "-", "scenario": "(no hits)", "cause": ""}]:
        print(f"  {h['distance']}  {h['scenario']}  {h['cause']}")


if __name__ == "__main__":
    for s in SEED:
        add_incident(s["id"], incident_text(s["alerts"], s["silent"], s["findings"]),
                     s["cause"], s["scenario"], s["fix"], s["source_doc"])
    print("records in memory:", get_collection().count())   # must be 5, even after running twice
    # KEY: max_distance=2.0 = no cutoff, so you see the RAW distances; we pick MAX_DISTANCE from these numbers
    show("new DB incident (expect kill_db first):", search_similar(NEW_DB, k=3, max_distance=2.0))
    show("same, kill_db excluded (leakage guard):", search_similar(NEW_DB, k=3, max_distance=2.0, exclude_scenario="kill_db"))
    show("unseen disk-full incident (expect only far hits):", search_similar(UNSEEN, k=3, max_distance=2.0))