# Profiling: memory, latency, cost

Measured on the score-bearing fixtures (`synthetic_cpg_repo`, `synthetic_taint_repo`,
4–8 files) and real-repo corpora (flask 83, requests 37, sqlmodel 333, rich 213 files).
Source: `experiments/run-N.log` + JSONL metrics. Render 512 MB tier: hard ceiling 380 MB RSS.

## Resident set size (ru_maxrss, MB)

| Run | Fixture RSS | Worst-case real repo | Verdict |
|-----|-------------|----------------------|---------|
| 1 (v0) | 19.66 | — | ✓ |
| 2 (v2 CPG) | 22.40 | — | ✓ |
| 5–7 (gates) | ~22–24 | rich 71.97 (213 files tokenised) | ✓ |
| 9–14 | ~22–24 | rich 72.63 (452 predicted-dead) | ✓ |

Headroom at close-out: **380 − 72.63 ≈ 307 MB (5.2×)**. Growth driver is corpus
tokenisation, not graph size (headline rows stay ~23 MB). `gc.collect()` after graph
construction; tarballs streamed via `io.BytesIO` 64 KB chunks, 60 MB cap.

## Latency

| Operation | Measured |
|-----------|----------|
| Blast-radius (BFS reverse reachability) | 0.51 ms (fixture), sub-ms throughout |
| Full v0 baseline run (4 files) | 0.01 s elapsed |
| Full CPG + oracle + gates (fixture) | seconds (dominated by harness execution under settrace) |
| Real-repo static pass (333 files) | minutes-scale, single job (max 1 concurrent by design) |

CPG queries (topological order, Kosaraju SCC, BFS) are milliseconds; the dynamic oracle
is the only super-linear cost and never runs on untrusted repos.

## Concurrency

Max 1 concurrent analysis job (HTTP 202 + polling per the master directive). No thread
pool in the measurement path; the oracle is single-process by necessity (settrace is
global interpreter state).

## Token / API cost

$0.00 on every measurement run (runs 2–14): no model in the loop. Run 1 v0 estimate
$0.008 (would-be Gemini leaf summaries). The only model spend in the whole programme was
the orchestrating agents' own inference, not the harness under test.

## Guarantee statement

Under full load (rich corpus, all gates, oracle on fixtures only): RSS ≤ 73 MB ⇒ zero
OOM risk on Render 512 MB. No native in-process vector DB (Chroma/Pinecone disk-backed
only), no local embedding/LLM weights in-container.
