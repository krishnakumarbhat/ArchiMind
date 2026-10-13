# Profiling: production engine budgets

Render 512 MB tier: hard ceiling 380 MB RSS, 1 worker job, $0 measurement tokens.

## Soak verdict (2026-09-27, 100 req/min × 150 min, gunicorn 1 worker × 4 threads)

15,000 requests, **0 errors** (13,125×200 + 1,875×400 intentional validation probes).
p50 9.9 ms · p95 27.9 ms · p99 37.5 ms · max 937.5 ms · mean 10.6 ms.
Server RSS: 12.7 MB idle, **23.6 MB peak** under load (16× headroom to ceiling).
Burst probe (600 rpm × 1 min): 600/600 clean, p50 12.4 ms, p95 36.8 ms.
Verdict: **PASS**. Rig: `scripts/soak_test.py` (raw log gitignored by `*.log`).

## Engine budgets (measured)

| Operation | Budget | Measured |
|-----------|--------|----------|
| CPG build, 31-file fixture (test) | RSS growth < 150 MB, traced < 50 MB | pass |
| Blast-radius BFS | < 2000 ms | 0.5 ms (fixture), ms-scale golden |
| Golden corpora (flask/requests/sqlmodel) | ≤ 250 files each | 24/20/40 py files, ≤ 673 KB artifact |
| Tarball ingest | ≤ 60 MB, ≤ 400 files | enforced in `stream_files` |

## Concurrency

`MAX_CONCURRENT_JOBS = 1`: second `/api/analyze` while one runs → HTTP 429 + `retry: true`
(covered by `tests/integration/test_engine_resources.py`).
