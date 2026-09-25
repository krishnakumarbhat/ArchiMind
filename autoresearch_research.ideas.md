# Ideas Backlog (variation tree — drain before declaring done)

- [ ] v0_baseline_linear: original DAG, fixed query, single-shot Gemini (baseline run).
- [ ] v1_eval_optimizer: + Mermaid validator + reflection ≤3 retries (expect validity→1.0).
- [ ] v2_treesitter_cpg: pure AST CPG (Tree-sitter+NX), zero vectors (expect F1↑, tokens→0).
- [ ] v3_hybrid_cpg_rag: CPG backbone + Gemini leaf summaries (expect docs quality↑, cost controlled).
- [ ] v4_governance_harness: + blast-radius + 3 invariants + coverage correlation.
- [ ] v5_full_agentic_system: + dual-agent review + taint tracer + MCP server.
- [ ] Ablations: CPG±vectors; reflection on/off; coverage on/off; dual-agent on/off; tarball-vs-clone RAM; SQLite precache on/off.
- [ ] Benchmark repos: synthetic_bad_repo, pallets/flask, psf/requests, tiangolo/sqlmodel, Textualize/rich.
