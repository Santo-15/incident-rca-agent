# Eval metrics (50 Locust users, 1 run per scenario)

v2 reran 6 scenarios (4 v1 misses + kill_db, redis_down as regression checks); the other 6 are v1 rows.

## v1 (before fixes)

- top-1, scenarios that alerted: 7/11 = 64%
- top-1, all scenarios (no alert / crash = miss): 7/12 = 58%
  - known: 4/5 = 80% (alerted: 4)
  - variant: 0/2 = 0% (alerted: 2)
  - unseen: 3/5 = 60% (alerted: 5)
- agent time (alert → report): median 4.1 s, max 7.2 s
- alert wait (fault → first alert): median 70 s, max 300 s
- LLM calls per incident: mean 3.36, max 4
- critic correction rate (first answer wrong → final right): 0/3 = 0% []
- critic made it worse (first right → final wrong): 1 ['redis_hang']
- deploy named correctly (named only when a deploy caused it): 11/11 = 100%
- primary LLM failures (Groq → Gemini fallback): 0

| scenario | kind | expected | got | correct | hypotheses | agent s | LLM calls |
|---|---|---|---|---|---|---|---|
| bad_pool_config | known | db_pool_exhausted | db_pool_exhausted | ✅ | db_pool_exhausted → db_pool_exhausted | 7.2 | 4 |
| kill_db | known | postgres_down | postgres_down | ✅ | postgres_down | 4.9 | 4 |
| memory_leak | known | memory_leak | memory_leak | ✅ | memory_leak | 3.8 | 3 |
| redis_down | known | redis_down | redis_down | ✅ | redis_down | 3.0 | 3 |
| slow_query | known | slow_query | – | no alert fired | – | – | – |
| postgres_hang | variant | postgres_down | db_pool_exhausted | ❌ | db_pool_exhausted | 2.4 | 3 |
| redis_hang | variant | redis_down | insufficient_evidence | ❌ | redis_down → insufficient_evidence | 4.1 | 3 |
| code_exception | unseen | code_exception | code_exception | ✅ | code_exception | 4.6 | 4 |
| db_lock | unseen | db_lock | db_pool_exhausted | ❌ | db_pool_exhausted | 3.3 | 3 |
| redis_oom | unseen | redis_out_of_memory | code_exception | ❌ | db_pool_exhausted → code_exception | 5.2 | 3 |
| shop_api_down | unseen | shop_api_down | shop_api_down | ✅ | shop_api_down → shop_api_down | 3.7 | 3 |
| wrong_service_address | unseen | wrong_service_address | wrong_service_address | ✅ | wrong_service_address | 4.6 | 4 |

## final (v1 + v2 reruns)

- top-1, scenarios that alerted: 10/11 = 91%
- top-1, all scenarios (no alert / crash = miss): 10/12 = 83%
  - known: 4/5 = 80% (alerted: 4)
  - variant: 2/2 = 100% (alerted: 2)
  - unseen: 4/5 = 80% (alerted: 5)
- agent time (alert → report): median 4.6 s, max 7.2 s
- alert wait (fault → first alert): median 60 s, max 280 s
- LLM calls per incident: mean 3.45, max 4
- critic correction rate (first answer wrong → final right): 1/2 = 50% ['postgres_hang']
- critic made it worse (first right → final wrong): 0 []
- deploy named correctly (named only when a deploy caused it): 11/11 = 100%
- primary LLM failures (Groq → Gemini fallback): 1

| scenario | kind | expected | got | correct | hypotheses | agent s | LLM calls |
|---|---|---|---|---|---|---|---|
| bad_pool_config | known | db_pool_exhausted | db_pool_exhausted | ✅ | db_pool_exhausted → db_pool_exhausted | 7.2 | 4 |
| kill_db | known | postgres_down | postgres_down | ✅ | postgres_down | 5.1 | 3 |
| memory_leak | known | memory_leak | memory_leak | ✅ | memory_leak | 3.8 | 3 |
| redis_down | known | redis_down | redis_down | ✅ | redis_down | 3.1 | 3 |
| slow_query | known | slow_query | – | no alert fired | – | – | – |
| postgres_hang | variant | postgres_down | postgres_down | ✅ | db_pool_exhausted → postgres_down | 5.1 | 4 |
| redis_hang | variant | redis_down | redis_down | ✅ | redis_down → redis_down | 3.7 | 3 |
| code_exception | unseen | code_exception | code_exception | ✅ | code_exception | 4.6 | 4 |
| db_lock | unseen | db_lock | db_pool_exhausted | ❌ | db_pool_exhausted → db_pool_exhausted | 5.9 | 4 |
| redis_oom | unseen | redis_out_of_memory | redis_out_of_memory | ✅ | redis_out_of_memory | 3.0 | 3 |
| shop_api_down | unseen | shop_api_down | shop_api_down | ✅ | shop_api_down → shop_api_down | 3.7 | 3 |
| wrong_service_address | unseen | wrong_service_address | wrong_service_address | ✅ | wrong_service_address | 4.6 | 4 |
