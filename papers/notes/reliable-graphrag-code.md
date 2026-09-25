---
title: Reliable Graph-RAG for Codebases (AST graphs vs LLM graphs)
arxiv: 2601.08773
venue: arXiv 2026
citedByCount: young-paper (track; threshold 30)
mechanisms: [tree-sitter AST graph, bidirectional expansion, deterministic traversal]
cracks: [analysis-only, no repair loop, no CI gate, no memory budget]
---

Deterministic AST graph 15/15 vs naive RAG 6/15 on Shopizer tracing suite. Foundation for our CPG backbone claim.
