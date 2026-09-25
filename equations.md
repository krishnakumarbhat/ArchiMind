# Equations Log: ArchiMind CPG Harness

**Session started:** 2026-09-25

| # | Source (paper/arXiv id) | Original equation | Fault found | Variation derived | Verification (numeric run) | Status |
|---|------------------------|-------------------|-------------|-------------------|---------------------------|--------|
| 1 | invented (this loop) | `harness_score = 30*valid + 30*F1 + 20*dead + 10*(1-blast_ms/2000)+ + 10*(1-peak_mb/512)` | unclamped negatives if blast>2000/peak>512 | clamp each sub-score to [0,1] before weighting | pending run-1 numeric check | pending |
| 2 | Kosaraju/SCC (standard) | `SCC via DFS order + reverse DFS = components` | none (correct); cost O(V+E) | compressed-bitset reachability for blast-radius <50ms | pending benchmark | pending |
| 3 | Newman modularity | `Q = (1/2m)Σ[Aij − kikj/2m]δ(ci,cj)` | resolution limit on small repos | label-propagation fallback for <200 nodes | pending | pending |
