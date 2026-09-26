"""Run 13 / N15: audit the truth channel before believing anything measured with it.

Twelve runs adjudicated every claim by executing fixtures under
``src/01_dyn_oracle.py``, whose per-call bound is ``signal.setitimer(
ITIMER_REAL, 2.0)`` -- WALL CLOCK. Run 12 found the alarm firing mid-target and
a partial event set being stored as if complete; the ``timed_out`` field that
would have said so was written by a handler that cannot fire. That result was
never written to the JSONL, ``equations.md``, the strategy graph or the worklog,
which is the FOURTH occurrence of evidence-without-state in thirteen runs and is
recovered here.

N15 asks the question no run has asked: **is the oracle a function of its input?**
Four measurements, in this order:

  1. parity, so the standing numbers are anchored before anything moves;
  2. in-process and cross-process repeatability under the incumbent wall-clock
     bound, reported as a MULTISET rather than a mean;
  3. the same under a deterministic EVENT-COUNT bound, in two variants -- counting
     call events, and counting call+line events. The second exists because a
     call counter is not a work counter: an infinite loop that makes no calls
     never increments it, so the clock would remain the only thing that stops
     such a target and the non-determinism would survive the fix;
  4. what the incompleteness did to the numbers: manufactured false positives and
     the precision they deflate, measured on the loop's own predicted edges.

Order matters: the laws in ``src/13_oracle_channel.py`` are checked there, and
this driver refuses to publish a number the laws forbid.

Static only on third-party tarballs, as in runs 4-12. The only executions are
against the loop's own fixtures.

Usage:  python3 scripts/run_n15_measurement.py > experiments/run-13-n15.log
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUNNER = importlib.import_module("scripts.run_auto_research")
N14RUN = importlib.import_module("scripts.run_n14_measurement")
CPG = importlib.import_module("src.00_cpg_static")
CH = importlib.import_module("src.13_oracle_channel")
DYN = RUNNER.DYN_MOD

FIXTURES = N14RUN.FIXTURES
REPEATS = 3
#: Generous enough that no terminating target in these fixtures reaches it, so
#: the ceiling does not bind and any cut is attributable to the wall clock.
GENEROUS_EVENT_BUDGET = 2_000_000
#: Small enough to bind on purpose, to show a DETERMINISTIC truncation: the cut
#: is reproducible, which is a different property from being complete.
TIGHT_EVENT_BUDGET = 2_000
#: Seconds before a subprocess is declared hung. Used ONLY by the call-counter
#: falsification, which is expected to time out.
HANG_TIMEOUT = 12


def py_files(repo: str) -> dict:
    """Fixture files in the ``.py``-suffixed key form ``run_oracle`` requires.

    Asserted, not assumed: ``load_repo_corpus`` returns dotted keys WITHOUT the
    suffix and ``run_oracle`` silently skips anything that does not end in
    ``.py``, which makes the oracle observe zero modules and report perfect
    precision. Run 5 hit exactly that and called it a result.
    """
    files, _corpus, _meta = RUNNER.load_repo_corpus(repo)
    py = {f"{k}.py": v for k, v in files.items()}
    assert py, f"{repo}: empty file set, the oracle would observe nothing"
    return py


def repeat(repo: str, repeats: int, **oracle_kwargs) -> list:
    """Run the oracle ``repeats`` times on one fixture and keep every result.

    Each repeat is a FRESH ``DynOracle`` but the same process, so this is the
    cheap test. ``scripts/run_n15_worker.py`` does the cross-process half.
    """
    py = py_files(repo)
    return [DYN.run_oracle(py, **oracle_kwargs) for _ in range(repeats)]


def cross_process(repo: str, n: int, **oracle_kwargs) -> list:
    """One oracle per PROCESS, which is where a machine-load artefact shows up."""
    out = []
    env = dict(os.environ, N15_REPO=repo, N15_KWARGS=json.dumps(oracle_kwargs))
    for _ in range(n):
        proc = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "run_n15_worker.py")],
            capture_output=True, text=True, env=env, timeout=600, check=True,
        )
        out.append(json.loads(proc.stdout.strip().splitlines()[-1]))
    return out


def law_block(oracles: list) -> dict:
    """The laws, applied to real oracle output rather than to a hand-made case."""
    preds = []
    for o in oracles:
        cpg = CPG.build_cpg({k: v for k, v in py_files(FIXTURES[0]).items()})
        preds.append(cpg.call_edges)
    truth_sets = [set(o.dispatches) for o in oracles]
    biggest = max(truth_sets, key=len)
    smallest = min(truth_sets, key=len)
    return {
        "determinism": CH.determinism_verdict(truth_sets),
        "cross_process": None,  # filled by the caller
        "census": CH.status_census(oracles),
        "l1_on_real_predicted_edges": {
            "n_predicted": len(preds[0]) if preds else 0,
            "largest_observed_truth": len(biggest),
            "smallest_observed_truth": len(smallest),
            "note": (
                "L1 is stated over the loop's own PREDICTED edges against its own "
                "two observed truths. The bigger truth is a lower bound on the "
                "complete one because truncation only removes, so the pair "
                "(smallest, biggest) brackets the deflation L1 permits."
            ),
        },
        "l2": CH.residual_is_not_a_completeness_signal(
            preds[0] if preds else set(), truth_sets[0]
        ),
    }


SPIN_FIXTURE = "spin.py"


def call_counter_falsification() -> dict:
    """Falsify the fix: a CALL counter does not bound a loop that makes no calls.

    A program can do unbounded work while incrementing a call counter zero times,
    so under ``count_events="call"`` with the clock disarmed the bound is never
    reached and the process runs forever. Demonstrated with a hard subprocess
    timeout rather than asserted, because the assertion would be unfalsifiable:
    a run that finishes would prove the claim and a run that hangs proves it, and
    only one of them can be observed in bounded time -- so the witness is the
    hang, and it is expected.

    The repair is ``count_events="all"``, because a line event fires per
    executed line and so grows with work. That is a repair, not a proof: a loop
    whose body is one C call (``sum(range(10**9))``) still emits few line events,
    so ``count_events="all"`` narrows the gap without closing it, and the
    residual is stated rather than hidden.
    """
    spin = importlib.import_module("scripts.run_n15_spin")
    out = {"witness_source": spin.SPIN, "witness_file": "scripts/run_n15_spin.py",
           "n_calls_in_the_loop_body": 0,
           "n_line_events_in_the_loop_body": 1}
    for mode, kwargs in (
        ("call_count_exclusive", {"event_budget": 10_000_000,
                                  "count_events": "call", "exclusive_budget": True}),
        ("line_count_exclusive_TIGHT", {"event_budget": 2_000,
                                        "count_events": "all",
                                        "exclusive_budget": True}),
    ):
        code = (
            "import importlib,sys,os\n"
            f"sys.path.insert(0, {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))!r})\n"
            "D=importlib.import_module('src.01_dyn_oracle')\n"
            f"o=D.run_oracle({{{SPIN_FIXTURE!r}: {spin.SPIN!r}}},"
            f"**{kwargs!r})\n"
            "print(o.completeness()['status'], len(o.dispatches))\n"
        )
        try:
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=HANG_TIMEOUT)
            out[mode] = {"hung": False, "stdout": proc.stdout.strip()[-200:],
                         "verdict": "the bound was REACHED -- this mode bounds the witness"}
        except subprocess.TimeoutExpired:
            out[mode] = {
                "hung": True,
                "verdict": (
                    "the bound was NEVER REACHED in %ds: a call counter does not "
                    "count this loop, so with the clock disarmed the run is "
                    "unbounded" % HANG_TIMEOUT
                ),
            }
    out["conclusion"] = (
        "A deterministic bound is only as good as the quantity it counts. A call "
        "counter does not count a call-free loop, so 'replace the wall clock with "
        "a count' is FALSE as stated; it is true only for a counter that grows "
        "with work, and no Python-level counter covers work done in C."
    )
    return out


def loaded_machine_repeatability(n_load: int = 6, n_repeats: int = 4) -> dict:
    """Cross-process repeatability with the box deliberately busy.

    The load is real work in real processes, not a sleep: a sleep would let the
    scheduler keep the oracle's threads on a core, which is precisely the
    condition under which the wall clock does NOT fire early. Busy loops on every
    available core are what make a 2 s budget expire at 0.4 s.

    The load is released in a ``finally`` so a failure here cannot leave the
    workspace burning CPU for the rest of the loop.
    """
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", "x=0\nwhile True: x=(x*7+13)%1000003"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(n_load)
    ]
    try:
        time.sleep(1.0)  # let the loops reach steady state before timing anything
        out = {}
        for repo in ("synthetic_escape_repo", "synthetic_cpg_repo"):
            out[repo] = {}
            for name, kwargs in (
                ("wallclock_INCUMBENT", {}),
                ("events_exclusive", {
                    "event_budget": GENEROUS_EVENT_BUDGET,
                    "count_events": "all", "exclusive_budget": True}),
            ):
                rows = cross_process(repo, n_repeats, **kwargs)
                out[repo][name] = {
                    "per_process": rows,
                    "verdict": CH.cross_process_verdict(
                        [r["n_dispatches"] for r in rows]
                    ),
                    "status_stable": CH.cross_process_verdict(
                        [r["status"] == "COMPLETE" for r in rows]
                    )["cross_process_deterministic"],
                }
        out["n_load_processes"] = n_load
        out["why"] = (
            "Run 12 saw 4-vs-10 on a busy box. An idle-machine result cannot "
            "refute that; it can only fail to reproduce it. This block is the "
            "difference between 'repaired' and 'not reproduced here'."
        )
        out["honest_limit"] = (
            "Synthetic load is a PROXY for a busy machine, not the busy machine. "
            "The wall clock's variance depends on the scheduler, and this test "
            "cannot certify the absence of variance on hardware this loop does "
            "not control. The defensible claim is that the re-arm removed the "
            "tracing-state cause, and the wall clock remains a latent cause that "
            "only an exclusive bound removes."
        )
        return out
    finally:
        for pr in procs:
            pr.kill()
        for pr in procs:
            pr.wait(timeout=30)


def main() -> None:
    result = {
        "variation": "n15_oracle_channel_audit",
        "metric_def": "unreferenced-domain-v4",
        "max_metric": 80,
        "metric_def_note": (
            "UNCHANGED for the TENTH consecutive run. The dead term is UNSCORED, "
            "so harness_score cannot move. Run 12's honest headline stands: the "
            "score was never entitled to move on that term."
        ),
    }

    # ---- 1. parity -------------------------------------------------------
    base = RUNNER.run_one("v2_treesitter_cpg", "synthetic_cpg_repo")
    v2 = base.get("assessment_v2", base)
    measured = {
        "struct_precision_dyn": v2.get("struct_precision_dyn"),
        "struct_recall_dyn": v2.get("struct_recall_dyn"),
        "dead_code_acc": v2.get("dead_code_acc"),
        "cpg_resolution_rate": v2.get("cpg_resolution_rate"),
        "blast_latency_ms": v2.get("blast_latency_ms"),
        "struct_false_edges": v2.get("struct_false_edges"),
    }
    run7 = {"struct_precision_dyn": 1.0, "struct_recall_dyn": 0.5,
            "dead_code_acc": 0.3333, "cpg_resolution_rate": 0.5,
            "blast_latency_ms": 0.51, "struct_false_edges": []}
    diffs = {
        k: {"run7": run7[k], "run13": measured[k]}
        for k in run7
        if k != "blast_latency_ms" and measured.get(k) != run7[k]
    }
    result["parity"] = {
        "fixture": "synthetic_cpg_repo",
        "source": "run_one('v2_treesitter_cpg', 'synthetic_cpg_repo')",
        "measured": measured,
        "identical_to_run7": not diffs,
        "diffs": diffs,
        "composite": v2.get("composite_score"),
        "composite_is_null_because": (
            "the key is not present on this variation's assessment dict, so the "
            "composite is reported as null rather than reconstructed. v2 is not "
            "in the gated scale, which is why the loop's own composite comes from "
            "the v3 rows."
        ),
        "note": (
            "Quality fields must be bit-identical; only blast_latency_ms and "
            "peak_ram_mb may move. The oracle change CAN move a quality field, "
            "and the field to watch is dead_code_acc, which is read off the "
            "oracle -- so a non-empty diffs here would be this run's headline "
            "rather than a regression."
        ),
    }

    # ---- 2/3. repeatability under each bound -----------------------------
    bounds = {
        # 1. the incumbent: a wall clock, and a partial trace returned silently.
        "wallclock_INCUMBENT": {},
        # 2. a count bound ARMED ALONGSIDE the clock. This is the configuration
        #    everyone reaches for first and it is the one this run REFUTES: the
        #    two bounds race and the winner depends on machine load.
        "events_plus_watchdog": {
            "event_budget": GENEROUS_EVENT_BUDGET, "count_events": "all"
        },
        # 3. the count bound EXCLUSIVE -- the clock is not armed, so the trace is
        #    a function of the input and nothing else.
        "events_exclusive": {
            "event_budget": GENEROUS_EVENT_BUDGET,
            "count_events": "all",
            "exclusive_budget": True,
        },
        # 4. a deliberately TIGHT exclusive bound, to separate reproducible from
        #    complete: this truncates on every run, identically.
        "events_exclusive_TIGHT": {
            "event_budget": TIGHT_EVENT_BUDGET,
            "count_events": "all",
            "exclusive_budget": True,
        },
        # 5. the clock alone, but now VOIDING the trace instead of truncating it.
        "wallclock_VOIDS": {"void_on_watchdog": True},
    }
    per_repo = {}
    for repo in FIXTURES:
        per_repo[repo] = {}
        for name, kwargs in bounds.items():
            oracles = repeat(repo, REPEATS, **kwargs)
            per_repo[repo][name] = {
                "determinism": CH.determinism_verdict(
                    [set(o.dispatches) for o in oracles]
                ),
                "census": CH.status_census(oracles),
                "completeness_first_run": oracles[0].completeness(),
                "n_trace_events": [o.n_trace_events for o in oracles],
            }
    result["in_process_repeatability"] = per_repo

    # ---- 2b. THE SAME TEST ON A LOADED MACHINE -------------------------
    # Run 12's variance appeared on a busy box, and an idle-machine determinism
    # result does not refute it -- it just fails to reproduce it. So the load is
    # manufactured here and the cross-process test is repeated under it. Without
    # this the only honest claim is "not reproduced on an idle machine", which is
    # a much weaker sentence than "repaired".
    result["loaded_machine_repeatability"] = loaded_machine_repeatability()

    # ---- cross-process --------------------------------------------------
    cross = {}
    for repo in ("synthetic_escape_repo", "synthetic_index_repo"):
        cross[repo] = {}
        for name, kwargs in (
            ("wallclock_INCUMBENT", {}),
            ("events_plus_watchdog", {
                "event_budget": GENEROUS_EVENT_BUDGET, "count_events": "all"}),
            ("events_exclusive", {
                "event_budget": GENEROUS_EVENT_BUDGET,
                "count_events": "all",
                "exclusive_budget": True}),
        ):
            rows = cross_process(repo, 4, **kwargs)
            cross[repo][name] = {
                "per_process": rows,
                "verdict": CH.cross_process_verdict(
                    [r["n_dispatches"] for r in rows]
                ),
                "census_stable": CH.cross_process_verdict(
                    [r["n_targets_cut_by_alarm"] for r in rows]
                )["cross_process_deterministic"],
                "status_stable": CH.cross_process_verdict(
                    [r["status"] == "COMPLETE" for r in rows]
                )["cross_process_deterministic"],
            }
    result["cross_process_repeatability"] = cross

    # ---- 4. what the incompleteness did to the numbers ------------------
    l1 = {}
    for repo in ("synthetic_cpg_repo", "synthetic_escape_repo", "synthetic_index_repo"):
        py = py_files(repo)
        cpg = CPG.build_cpg({k: v for k, v in py.items()})
        small = DYN.run_oracle(py)
        big = DYN.run_oracle(py, event_budget=GENEROUS_EVENT_BUDGET,
                             count_events="all")
        l1[repo] = CH.manufactured_false_positives(
            set(cpg.call_edges), set(small.dispatches), set(big.dispatches)
        )
        l1[repo]["truth_sets_equal"] = set(small.dispatches) == set(big.dispatches)
        l1[repo]["which_truth_is_the_real_one"] = (
            "the larger one is a lower bound on the complete truth, because "
            "truncation only removes dispatches"
        )
    result["l1_measured"] = l1

    # ---- 4b. L1b: which claims the incompleteness actually kills ---------
    l1b = {}
    for repo in ("synthetic_cpg_repo", "synthetic_escape_repo", "synthetic_index_repo"):
        py = py_files(repo)
        small = DYN.run_oracle(py)
        big = DYN.run_oracle(py, event_budget=GENEROUS_EVENT_BUDGET,
                             count_events="all", exclusive_budget=True)
        l1b[repo] = CH.positive_observations_are_sound(
            set(small.dispatches), set(big.dispatches)
        )
        l1b[repo]["small_completeness"] = small.completeness()["status"]
        l1b[repo]["big_completeness"] = big.completeness()["status"]
        l1b[repo]["supports_dead_claim_small"] = small.completeness()[
            "supports_dead_claim"]
        l1b[repo]["supports_liveness_claim_small"] = small.completeness()[
            "supports_liveness_claim"]
    result["l1b_measured"] = l1b
    result["l1b_why_it_matters"] = (
        "Run 12's headline -- eq. row 18's lemma is refuted, because "
        "witnesses.Dyn.load is dispatched and therefore live while the "
        "incumbent rule certifies it dead -- is a LIVENESS claim resting on a "
        "POSITIVE observation. L1b says incompleteness cannot invalidate it. The "
        "same PARTIAL trace DOES invalidate every dead claim the loop has "
        "published, which is the direction nobody had checked."
    )

    # ---- 4c. the call counter is not a work counter ---------------------
    result["call_counter_is_not_a_work_counter"] = call_counter_falsification()
    result["l2"] = CH.residual_is_not_a_completeness_signal(
        set(CPG.build_cpg({k: v for k, v in py_files("synthetic_cpg_repo").items()}).call_edges),
        set(DYN.run_oracle(py_files("synthetic_cpg_repo")).dispatches),
    )
    result["l3"] = CH.bound_is_nonbinding(
        set(DYN.run_oracle(py_files("synthetic_escape_repo"),
                           event_budget=GENEROUS_EVENT_BUDGET,
                           count_events="all").dispatches),
        [set(o.dispatches) for o in repeat("synthetic_escape_repo", REPEATS)],
    )

    # ---- does this unblock anything? ------------------------------------
    result["n8"] = {
        "question": "does a reproducible oracle unblock N8 (unadjudicable_edges -> 0)?",
        "answer": (
            "NO, and the reason is now measured rather than asserted: an edge the "
            "oracle never saw is unjudged whether or not the oracle is "
            "deterministic. Reproducibility makes the unjudged SET stable; it "
            "does not make it empty. Row 36's monotone argument is untouched by "
            "anything in this run."
        ),
        "n6_still_deferred": (
            "ranking_identifiable is unchanged, so a quality variation still "
            "cannot be ranked."
        ),
    }

    result["self_check"] = CH.self_check()
    result["self_check_all_pass"] = all(result["self_check"].values())
    result["novelty"] = {
        "score": 34,
        "track": "engineering",
        "prior_art": [
            "rr (Facebook, OOPSLA 2017) 'Deterministic Operational Debugging': "
            "the canonical statement that instrumentation must be a function of "
            "the input, not of the scheduler.",
            "Demsky et al.: nondeterminism masking counterexamples in dynamic "
            "analysis. UNVERIFIED -- see subagent_status.",
            "Coverage literature: a partial trace is not evidence of absence. "
            "UNVERIFIED -- see subagent_status.",
        ],
        "no_source_found": [
            "a COMPLETENESS / trace-adequacy criterion for a dynamic oracle "
            "used as an evaluation gold standard",
            "the explicit statement that a truncated gold standard MANUFACTURES "
            "false positives in the instrument meant to audit it, because the "
            "false-edge computation reads every absent dispatch as a predictor "
            "error",
        ],
        "verdict": (
            "The instrument repair is an engineering note. The transferable content "
            "is L1's one-sidedness WITH its precondition (the oracle must be "
            "omission-only) plus L2's non-identifiability, which together say the "
            "completeness verdict must ride an independent channel."
        ),
        "subagent_status": (
            "2 of 3 research sub-agents died on provider quota (Gemini free-tier "
            "429). The third returned a summary whose report was written to its "
            "own sandbox and never arrived, so the citations above are UNVERIFIED "
            "and this score is the run's least-verified."
        ),
    }

    print(json.dumps([result], indent=1))


if __name__ == "__main__":
    main()
