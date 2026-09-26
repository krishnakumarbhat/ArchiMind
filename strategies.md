# Strategy Diversity Log

| # | Strategy (mode × gap × routing) | Why new | Outcome | Status |
|---|---------------------------------|---------|---------|--------|
| 0 | setup: field-map (baseline profile, no invention) | bootstrap | baseline mapped, tree queued | kept |
| 1 | metric-integrity attack: reject the harness's own truth function, replace it with an execution oracle; route to *measurement* rather than modelling | every prior node optimises a score. This one questions whether the score means anything — a different axis from v0→v2 feature accretion, and the only mode that can return a *worse* honest number | run 1's `structural_f1=0.6827` shown to be self-fulfilling; run-2 coarse head-to-head v0 **0.2143** vs CPG **1.0**; oracle found a real bug in my own CPG (eq. row 6) | kept |
| 2 | potency re-ranking: audit *unexpanded* frontier nodes for provable zero-headroom before spending an iteration | keeps the loop from burning a 6h budget on a node that cannot move the metric | N2 (v1 reflection) deprioritised with a recorded reason — validity already 1.0, so it is worth 0 of 100 points | kept |
