# Autoresearch Research: ArchiMind Agentic CPG & Architecture Governance Harness

## Objective
Elevate ArchiMind from passive linear RAG (ingest→chunk→embed→single-shot generate, `worker.py:252`, `services.py:1147`) into an industrial-grade **Agentic Code Property Graph & Architecture Governance Harness**. Systematically explore the variation tree (v0 baseline … v5 full agentic, plus feature on/off ablations A/B/C) and find the best variation that maximizes structural correctness + diagram validity while satisfying the **Render 512MB hard invariant** and ≤1000 req/day throughput. Unattended 6–7h run.

Win = a kept variation with `harness_score ≥ 70` AND all hard constraints green (peak RSS ≤380MB, no in-RAM vector DB, no local LLM, no full git clone, max 1 concurrent job), committed with evidence artifacts and benchmark tables.

## Publish Venue
Engineering track: ICSE/FSE/ASE (software engineering) + MLSys; theory grounding from arXiv cs.SE / cs.AI. LaTeX paper only if a variation shows ≥10× latency/RAM win or novel CPG formulation (else leaderboard + architecture docs suffice).

## Metrics
- **Primary**: harness_score (0-100, higher is better) = `30*mermaid_validity_rate + 30*structural_f1 + 20*dead_code_acc + 10*latency_score + 10*ram_score`, where `latency_score = max(0,1-blast_ms/2000)`, `ram_score = max(0,1-peak_mb/512)`.
- **Secondary** (once tracked, always tracked):
  - `mermaid_validity_rate` (0-1, first-pass + post-reflection)
  - `structural_f1` (0-1, call/import edges vs AST ground truth)
  - `blast_latency_ms` (lower better)
  - `peak_ram_mb` (lower better, hard ceiling 380)
  - `token_cost_usd` (lower better)
  - `dead_code_acc` (0-1)
  - `prior_art_clear` (0/1)

## Research Resources (nearest venues for this topic)
1. arXiv cs.SE/cs.AI + Semantic Scholar citation-sorted: SWE-bench (Jimenez et al. 2024, ICLR oral), SWE-agent (Princeton/Stanford, 20k★), OpenHands SDK paper (arXiv:2511.03690, 64k★ framework).
2. Microsoft GraphRAG / Code-Graph-RAG (Tree-sitter + Memgraph/NX, dead-code + FLOWS_TO taint edges, MCP server).
3. LangGraph docs: cycles + ToolNode + `tools_condition` + evaluator-optimizer workflow; MLflow LangGraph tracing cookbook.
4. Grounding paper: Reliable Graph-RAG for Codebases (arXiv:2601.08773) — deterministic AST graph 15/15 vs naive RAG 6/15.

## High-Index Targets
- SWE-bench harness (Docker layered eval: base→env→instance; `run_evaluation`): crack = 120GB/16GB requirements, no architectural reasoning, pass/fail only.
- SWE-agent ACI (LM-centric commands + sandbox): crack = free-flow agency, no CPG determinism, no governance invariants.
- OpenHands SDK (sandboxed execution + lifecycle + multi-LLM routing, 72.8% SWE-Verified): crack = heavy runtime, no 512MB path, no CPG-backed blast-radius.
- CodeGraph-RAG / CodeGraph (Tree-sitter + NetworkX, 15/15 tracing): crack = analysis-only, no evaluator-optimizer, no PR gate, no SWE-task synthesis.
- Gap to attack: **deterministic CPG backbone + cyclic agentic repair + CI governance + 512MB compliance in one harness** — nobody combines all four.

## Files in Scope
`app.py`, `worker.py`, `services.py`, `models.py`, `config.py`, `src/variations/v*.py`, `src/**` (new 00–09 modules), `scripts/run_auto_research.py`, `scripts/benchmark_repos.sh`, `scripts/memory_stress_test.py`, `tests/benchmarks/**`, `docs/**`.

## Off Limits
- `.env` / secrets / API keys (use `.env.example` only); never commit keys.
- `node_modules/`, `__pycache__/`, `*.pyc`, `.autoresearch-loop.lock` tampering.
- No destructive `git` ops (no reset --hard on main, no force-push). Work on `research/archimind-cpg-harness-20260925` only.
- No native in-RAM ChromaDB, no local LLM/embedding models, no full `git clone` (tarball stream only).

## Constraints
- Hard: peak RSS ≤380MB; max 1 concurrent analysis job (HTTP 202 + poll); external neural APIs only (Gemini/Groq); shallow tarball ingestion; Pydantic v2 + strict hints; structured logging, no bare except; absolute imports from package root; SRP one-class-per-file with `NN_` sequential prefixes for new `src/` modules.
- Loop: ONE idea iteration per driver invocation then exit; evidence-based keeps (real benchmark log `experiments/run-N.log` or verified `equations.md` row); max 1 `unvalidated` per segment; strategy diversity enforced via `strategies.md` + strategy graph; web via `autoresearch-fetch.sh` cache→backoff→proxy; never stall on blocked domains (mark `prior_art_check: pending`, do local work).
- No fabricated results/citations; every foundation paper logs Semantic Scholar citedByCount in `equations.md`.

## What's Been Tried
- (Setup, 2026-09-25) Mapped baseline: linear DAG confirmed (`services.py:1147-1156`, `worker.py:252-397`), zero tool-calling/conditional edges, single-shot Gemini, regex Mermaid repair. Baseline metrics pending first benchmark run (run 1 = v0 on synthetic_bad_repo + pallets/flask tarball).
- Variation tree queued: v0_baseline_linear → v1_eval_optimizer → v2_treesitter_cpg → v3_hybrid_cpg_rag → v4_governance_harness → v5_full_agentic_system, plus ablations (CPG±, reflection±, coverage±, dual-agent±, MCP±).
