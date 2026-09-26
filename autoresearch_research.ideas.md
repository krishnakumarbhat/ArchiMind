# Ideas Backlog (variation tree — drain before declaring done)

- [ ] v0_baseline_linear: original DAG, fixed query, single-shot Gemini (baseline run). **Done, run 1.**
- [ ] v1_eval_optimizer: + Mermaid validator + reflection ≤3 retries. **Deprioritised run 2:** validity already 1.0 on the fixture ⇒ 0 pts. Requeue vs a fixture that actually fails validation.
- [x] v2_treesitter_cpg: resolved CPG (stdlib `ast`, no tree-sitter needed) + dynamic oracle. **Done, run 2.** precision 1.0 / recall 0.5 / dead 0.3333 / RAM 22.4MB / $0 tokens. Shipped as `src/00_cpg_static.py` + `src/01_dyn_oracle.py`.
- [ ] **v3_trace_informed_repair (highest potential, N4):** bind each `cpg_unresolved` entry to a trace dispatch to promote a static edge. Targets recall 0.5→≥0.8 and dead 0.333→≥0.6. 30 F1 points gated behind the one remaining root cause.
- [ ] v3_hybrid_cpg_rag: CPG backbone + Gemini leaf summaries (expect docs quality↑, cost controlled).
- [ ] v4_governance_harness: + blast-radius (CPG method shipped, UI not) + 3 invariants + coverage correlation. Needs the all-pairs bitset matrix (eq. row 2).
- [ ] v5_full_agentic_system: + dual-agent review + taint tracer + MCP server.
- [ ] Oracle completeness bound: report `|D|/|T|` to quantify the incomplete-oracle bias in eq. row 4 instead of assuming it.
- [ ] Ablations: oracle on/off (value of the oracle to the *metric*); dunder-exempt on/off; CPG±vectors; coverage on/off; dual-agent on/off.
- [x] Benchmark repos: synthetic_bad_repo (⚠️ circular import — unloadable, cannot be an oracle subject), synthetic_cpg_repo (new, acyclic), pallets/flask, psf/requests, tiangolo/sqlmodel, Textualize/rich. **Real repos still unmeasured; dynamic oracle must stay OFF for them (it executes code).**
