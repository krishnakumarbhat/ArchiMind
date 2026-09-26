"""Sustained load + memory soak rig for ArchiMind.

Hammers cheap read paths (index, golden, blast-radius, status, invalid-analyze)
at a target request rate, tracking per-endpoint latency percentiles, error rate,
and server RSS over time. Write paths (/api/analyze valid) are excluded by design:
they spawn worker subprocesses + LLM calls and are covered by integration tests.

Usage:
    python3 scripts/soak_test.py --rpm 100 --duration-min 150 --server-pid 1234
    python3 scripts/soak_test.py --rpm 600 --duration-min 5   # burst probe
"""
import argparse
import json
import logging
import os
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("soak")

SYMBOLS = ["Session", "Request", "Flask", "SQLModel", "get", "post", "NoSuchSymbol_xyz"]
GOLDENS = ["flask", "requests", "sqlmodel"]


def build_plan(base: str):
    """Deterministic rotating endpoint mix (no write-side effects)."""
    plan = [
        ("GET", base + "/", None),
        ("GET", base + "/api/golden", None),
        ("GET", base + "/api/status", None),
        ("POST", base + "/api/analyze", {"repo_url": "not-a-url"}),  # 400 validation path
    ]
    for i, g in enumerate(GOLDENS):
        plan.append(("GET", f"{base}/api/blast-radius?symbol={SYMBOLS[i]}&golden={g}", None))
    plan.append(("GET", base + "/api/blast-radius?symbol=NoSuchSymbol_xyz&golden=flask", None))
    return plan


def fire(method: str, url: str, payload, timeout: int = 25):
    """One request; return (status, latency_ms, n_bytes)."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
        return resp.status, (time.time() - t0) * 1000, len(body)
    except urllib.error.HTTPError as exc:
        return exc.code, (time.time() - t0) * 1000, 0
    except Exception as exc:
        logger.warning("request failed %s %s: %s", method, url, str(exc)[:100])
        return -1, (time.time() - t0) * 1000, 0


def rss_mb(pid: int) -> float:
    """Server RSS in MB; -1 when the process is gone."""
    try:
        out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)], text=True).strip()
        return int(out) / 1024.0
    except Exception:
        return -1.0


def percentile(values, pct: float) -> float:
    """Nearest-rank percentile over a latency sample."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(len(ordered) * pct / 100.0 + 0.5)))
    return ordered[rank - 1]


def main() -> int:
    """Run the paced soak and stream per-minute summaries to the log file."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5123")
    ap.add_argument("--rpm", type=float, default=100.0)
    ap.add_argument("--duration-min", type=float, default=150.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--server-pid", type=int, default=0)
    ap.add_argument("--out", default="experiments/soak.log")
    args = ap.parse_args()

    plan = build_plan(args.base)
    interval = 60.0 / args.rpm
    deadline = time.time() + args.duration_min * 60.0
    lock = threading.Lock()
    lat: list = []
    errors = 0
    total = 0
    live_total, live_errors = [0], [0]
    status_hist: dict = {}
    rss_peak = 0.0
    rss_series: list = []
    stop = threading.Event()
    idx = {"n": 0}

    def minute_reporter():
        while not stop.wait(60):
            rss = rss_mb(args.server_pid) if args.server_pid else -1.0
            rss_series.append(rss)
            logger.info("soak reqs=%d err=%d rss=%.1fMB", live_total[0], live_errors[0], rss)

    reporter = threading.Thread(target=minute_reporter, daemon=True)
    reporter.start()

    def record(code: int, ms: float) -> None:
        with lock:
            live_total[0] += 1
            lat.append(ms)
            status_hist[code] = status_hist.get(code, 0) + 1
            if code == -1 or code >= 500:
                live_errors[0] += 1

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        inflight = []

        def sweep(block: bool = False) -> None:
            done, inflight[:] = ([f for f in inflight if f.done()], [f for f in inflight if not f.done()])
            for f in done:
                code, ms, _ = f.result()
                record(code, ms)
            if block and inflight:
                code, ms, _ = inflight.pop(0).result()
                record(code, ms)

        nxt = time.time()
        while time.time() < deadline:
            with lock:
                i = idx["n"]
                idx["n"] += 1
            method, url, payload = plan[i % len(plan)]
            inflight.append(pool.submit(fire, method, url, payload))
            sweep()
            while len(inflight) > 200:  # ponytail: backpressure cap, not a result buffer
                sweep(block=True)
            nxt += interval
            delay = nxt - time.time()
            if delay > 0:
                time.sleep(delay)
        for f in inflight:
            code, ms, _ = f.result()
            record(code, ms)
    stop.set()
    total, errors = live_total[0], live_errors[0]

    final_rss = rss_mb(args.server_pid) if args.server_pid else -1.0
    if final_rss > 0:
        rss_series.append(final_rss)

    ok_lat = [x for x in lat]
    summary = {
        "rpm_target": args.rpm,
        "duration_min": args.duration_min,
        "requests": total,
        "errors": errors,
        "error_rate": round(errors / max(1, total), 4),
        "status_codes": status_hist,
        "latency_ms": {
            "p50": round(percentile(ok_lat, 50), 1),
            "p95": round(percentile(ok_lat, 95), 1),
            "p99": round(percentile(ok_lat, 99), 1),
            "max": round(max(ok_lat) if ok_lat else 0, 1),
            "mean": round(statistics.mean(ok_lat) if ok_lat else 0, 1),
        },
        "server_rss_peak_mb": round(max(rss_series) if rss_series else rss_peak, 1),
        "verdict": "PASS" if (errors / max(1, total)) < 0.01 else "FAIL",
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    logger.info("SOAK DONE: %s", json.dumps(summary))
    print(json.dumps(summary, indent=2))
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
