"""Run 13 witness: a loop that does unbounded work while making NO calls.

Purpose: falsify N15's own fix. The fix replaces the oracle's wall-clock bound
    with a count of trace events, on the argument that a count is a function of
    the program while a clock is a function of the machine. That argument is only
    as good as the quantity counted. This function increments a call counter
    exactly twice -- once for the module and once for ``range(10**9)`` -- and then
    spins through a billion iterations whose body is one integer addition and one
    ``STORE_FAST``, neither of which is a call.

    Under ``count_events="call"`` with the clock disarmed the ceiling is therefore
    NEVER reached and the process does not terminate. That is the falsification:
    "replace the wall clock with a count" is FALSE as stated. It holds for a
    counter that grows with WORK -- ``count_events="all"`` counts line events,
    which do -- but no Python-level counter covers work performed inside a C call,
    so the residual is stated rather than hidden.

Loaded as a fixture source by ``scripts/run_n15_measurement.py`` under a hard
subprocess timeout. The expected observation is a HANG; a clean exit would refute
the claim this file exists to support.
"""

SPIN = """def spin():
    total = 0
    for i in range(1000000000):
        total += i
    return total
"""
