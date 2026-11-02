# Baselines vs agent (offline, same saved findings, 50 users, 1 run each)

| kind | rules | single LLM call | agent |
|---|---|---|---|
| known | 4/4 = 100% | 4/4 = 100% | 4/4 = 100% |
| variant | 0/2 = 0% | 1/2 = 50% | 2/2 = 100% |
| unseen | 0/5 = 0% | 4/5 = 80% | 4/5 = 80% |
| all | 4/11 = 36% | 9/11 = 82% | 10/11 = 91% |

| scenario | kind | expected | rules | single | agent |
|---|---|---|---|---|---|
| bad_pool_config | known | db_pool_exhausted | db_pool_exhausted ✅ | db_pool_exhausted ✅ | db_pool_exhausted ✅ |
| kill_db | known | postgres_down | postgres_down ✅ | postgres_down ✅ | postgres_down ✅ |
| memory_leak | known | memory_leak | memory_leak ✅ | memory_leak ✅ | memory_leak ✅ |
| redis_down | known | redis_down | redis_down ✅ | redis_down ✅ | redis_down ✅ |
| postgres_hang | variant | postgres_down | db_pool_exhausted ❌ | db_pool_exhausted ❌ | postgres_down ✅ |
| redis_hang | variant | redis_down | other ❌ | redis_down ✅ | redis_down ✅ |
| code_exception | unseen | code_exception | other ❌ | code_exception ✅ | code_exception ✅ |
| db_lock | unseen | db_lock | db_pool_exhausted ❌ | db_pool_exhausted ❌ | db_pool_exhausted ❌ |
| redis_oom | unseen | redis_out_of_memory | other ❌ | redis_out_of_memory ✅ | redis_out_of_memory ✅ |
| shop_api_down | unseen | shop_api_down | other ❌ | shop_api_down ✅ | shop_api_down ✅ |
| wrong_service_address | unseen | wrong_service_address | other ❌ | wrong_service_address ✅ | wrong_service_address ✅ |
