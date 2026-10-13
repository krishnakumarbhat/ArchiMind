# Architecture (production)

## Layers

```
browser (landing → studio, pan/zoom canvas, guarded chat)
  │  HTTP: /api/analyze|status|golden|blast-radius|challenge|chat|history
app.py (Flask factory, auth, 429 single-job guard, shareable completed reads)
  │  subprocess
worker.py (tarball-first ingest → Chroma index → CPG → generate → repair → status JSON)
  ├── src/ingestion   tarball stream (64KB chunks, 60MB/file caps) + subtree fetch + filter
  ├── src/cpg         tree-sitter (py/ts) AST → scoped symbols → NetworkX DiGraph
  │                   (CALLS resolved per-scope; >3 ambiguous refused; reverse blast radius)
  ├── src/orchestration  LangGraph generate→validate→reflect (cap 3) + normalize +
  │                   valid-by-construction fallback diagrams + handbook builder
  ├── src/governance  BFS impact + presentation/acyclic/domain invariants
  ├── src/agentic     deterministic CPG tools + Challenge-Me seam synthesis
  ├── src/security    prompt guardrail + model fingerprint scrubber
  └── src/storage     SQLite cache + committed golden_fixtures/ (pytorch/openclaw/requests)
services.py (repository/vector/documentation backends: ChromaDB default, Pinecone opt-in, local JSON)
models.py (User, AnalysisLog, RepositoryHistory) — SQLite locally, Postgres on Render
```

## Data contracts

- Status file `data/status_<id>.json`: `{status, stage, progress, result{chat_response, hld/lld/flow_graph, chat_summary, cpg_artifact, invariants, repair_log, engine}}`.
- Golden fixture: `{id, title, subtitle, stats, chat_summary, chat_response, hld/lld/flow_mermaid, invariants, repair_log, cpg_artifact}`; list endpoint strips the CPG blob.
- Chat: `{answer, engine, tools_used[]}`; guardrail rejections carry `guardrail: true`.

## Invariants (512MB tier)

Single worker job (HTTP 202 + poll, 429 when busy); no in-RAM vector DB (Chroma persistent);
no local models (Gemini API or hash fallback; ONNX embedding function never invoked —
all vectors supplied explicitly); no `git clone` on the hot path; `.env` never committed.
Measured: 23.6MB peak RSS under 15k-request soak; see `docs/profiling.md`.
