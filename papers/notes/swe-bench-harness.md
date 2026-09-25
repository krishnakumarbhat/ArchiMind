---
title: SWE-bench harness (Docker layered evaluation)
arxiv: 2402.03011
venue: ICLR 2024 oral
citedByCount: 2000+
mechanisms: [docker layered images, run_evaluation, FAIL_TO_PASS resolution]
cracks: [120GB storage + 16GB RAM, pass/fail only, no architectural reasoning, no blast-radius]
---

SWE-bench evaluates patches in containers; SOTA ~72.8% Verified (OpenHands SDK + Claude Sonnet 4.5). Our gap: deterministic CPG + governance invariants at 512MB.
