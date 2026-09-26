"""Repo-local UNREFERENCED-symbol certification: a precondition-free dead-code gate.

Purpose: run 4 (equations.md row 15) built trace-free certification by asking the
    resolver what it could not resolve, and had to REFUSE the whole repository
    whenever a single ``<complex>`` call site existed -- a call whose callee has
    no extractable name (``factory()()``, ``reg["handler"]()``). That refusal
    fires on 3 of 4 real Python repos, so the one sound dead-code output the
    harness produced was unavailable on real code.

    This module replaces the global precondition with a strictly weaker, purely
    local one. THE OBSERVATION: a ``<complex>`` site is un-nameable, but it is
    not un-referenceable. To call ``s`` the runtime must first obtain a
    *reference* to ``s``, and every mechanism that can do that in Python names
    ``s`` somewhere in the source: an identifier occurrence (a call, an import,
    a bare mention, a closure capture) or a string literal (``getattr(m, "s")``,
    ``globals()["s"]``). So if ``leaf(s)`` occurs NOWHERE in the corpus except at
    ``s``'s own definition, then no expression anywhere -- nameable or not --
    can produce a callable bound to ``s``, and no call site can dispatch to it.

    FORMALLY. Let ``occ[n]`` = number of occurrences of the token ``n`` in the
    tokenised corpus C (identifiers and identifier-shaped string literals), and
    let ``defs[s] = 1`` be ``s``'s own definition occurrence. Define

        certified = { s in dead : occ[leaf(s)] == 1 }

    SOUNDNESS (zero false positives, relative to the corpus boundary).
    Suppose ``s`` is certified and some call site dispatches to ``s`` at
    runtime. The callee expression evaluated to a callable bound to ``s``, so
    the runtime held a reference to ``s``. Every reference to a module-level
    name in CPython is created by an IMPORT, an ASSIGNMENT, an attribute store,
    a container store, or a ``globals``/``getattr`` lookup -- each of which
    mentions ``leaf(s)`` as an identifier or as a string literal somewhere in
    C. That contradicts ``occ[leaf(s)] == 1``. Hence no call site dispatches to
    ``s``, so ``s`` is not live, so certifying it dead is never a false
    positive. QED, with no execution and no ``<complex>`` precondition.

    RELATION TO RUN 4's GATE (measured, and NOT the superset claim it looks
    like). Run 4 certified ``s`` when ``leaf(s)`` matched no opaque site. On
    ``synthetic_taint_repo``, where the true dead set is written down, run 4's
    UNGATED filter certifies 4 symbols of which **2 are false positives**: one
    reached only through ``globals()["..."]`` and one imported only from
    ``tests/``. So run 4's "zero false positives" was true only because the
    global ``<complex>`` precondition suppressed the whole term on that fixture;
    it is a conditional claim that was stated unconditionally, and the
    name filter on its own is unsound in two independent ways. This rule is
    therefore NOT a superset of run 4's -- it is a strict SUBSET that is sound
    without a precondition, and it certifies where run 4 refuses. It pays for
    that with recall: a dead symbol whose name is mentioned anywhere, including
    in a test, a string, or an unrelated symbol of the same name, is not
    certified. Same name-collision direction run 4 measured (equations.md
    row 16): precision is preserved, recall is not.

    TWO CHECKED PRECONDITIONS, both of which can refuse.
      * ``corpus_complete`` -- the occurrence counts must cover EVERY ``.py``
        file in the artefact. A file dropped by a size cap, a file count cap, a
        directory skip (tests/, docs/, vendor/) or a tokenisation failure is a
        file whose references are invisible, which would make an occurrence
        count of 1 a false certificate. Tests are therefore tokenised for
        REFERENCES even though the CPG is never built over them.
      * ``<unparsed>`` -- a source that fails to tokenise is an unknown
        reference set, so it refuses.

    CEILING (named, not solved). Two escapes defeat the string-literal half and
    are undecidable statically: a name assembled at runtime
    (``getattr(m, "_a" + "bc")``) and a public symbol of the library's own API,
    which is called by consumers outside this repository. The verdict is
    therefore "unreferenced within this corpus at this revision", NOT "dead in
    the world". A consumer outside the corpus is a boundary condition on the
    claim, not a hole in the proof.
"""
from __future__ import annotations

import io
import keyword
import tokenize
from typing import Dict, Iterable, Set

Symbol = str

UNPARSED = "<unparsed>"


def bare(sym: Symbol) -> str:
    """Leaf name of a module-qualified symbol (``a.b.C.m`` -> ``m``)."""
    return sym.rsplit(".", 1)[-1]


def _literal_identifier(lit: str) -> str | None:
    """Recover an identifier from a string literal, or ``None``.

    ``getattr(m, "close")`` and ``globals()["close"]`` both put the name in the
    program as a STRING, never as an identifier, so counting identifiers alone
    would miss exactly the dynamic references this rule must not miss.
    """
    try:
        val = eval(lit, {"__builtins__": {}}, {})  # noqa: S307 - literal-only AST
    except Exception:
        return None
    if isinstance(val, str) and val.isidentifier() and not keyword.iskeyword(val):
        return val
    return None


def token_name_counts(sources: Iterable[str]) -> Dict[str, int]:
    """Occurrence count per identifier in a tokenised corpus.

    Counts NAME tokens (which include attribute names, import names and bare
    mentions) and identifier-shaped string literals. A source that cannot be
    tokenised contributes the ``<unparsed>`` sentinel rather than a partial
    count, because a partial count silently certifies things it never saw.

    ponytail: whole-file tokenise, no incremental scanner. ~30k lines/sec and
    the corpus is capped at 400 files, so the fast path would be a second code
    path to keep honest for no measurable win.
    """
    counts: Dict[str, int] = {}
    for src in sources:
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
            counts[UNPARSED] = counts.get(UNPARSED, 0) + 1
            continue
        for tok in toks:
            if tok.type == tokenize.NAME:
                counts[tok.string] = counts.get(tok.string, 0) + 1
            elif tok.type == tokenize.STRING:
                name = _literal_identifier(tok.string)
                if name is not None:
                    counts[name] = counts.get(name, 0) + 1
    return counts


def corpus_complete(n_in_artefact: int, n_tokenised: int, counts: Dict[str, int]) -> bool:
    """Soundness precondition: did we see every file, and did they all tokenise?

    ``n_in_artefact`` counts every ``.py`` file in the tarball including the
    directories the CPG skips. If it exceeds ``n_tokenised`` a file was dropped
    and its references are invisible; if ``<unparsed>`` is present a file's
    reference set is unknown. Either way an occurrence count of 1 is not
    evidence of anything, so the term refuses.
    """
    return n_in_artefact == n_tokenised and UNPARSED not in counts


def certify_unreferenced(dead: Set[Symbol], counts: Dict[str, int]) -> Set[Symbol]:
    """Predicted-dead symbols whose leaf name occurs exactly once in the corpus.

    That single occurrence is the symbol's own definition, so the name is
    unreferenced and no call site can dispatch to it.
    """
    return {s for s in dead if counts.get(bare(s), 0) == 1}


def name_mentioned_elsewhere(dead: Set[Symbol], counts: Dict[str, int]) -> Set[Symbol]:
    """Predicted-dead symbols blocked by a name occurrence elsewhere.

    Reported so the cost of the rule is visible: these are the symbols a
    perfect dead-code detector would find and this gate abstains on, split by
    whether the blocking mention is an identifier or only a string literal.
    """
    return {s for s in dead if counts.get(bare(s), 0) > 1}


def recount_identifiers_only(sources: Iterable[str]) -> Dict[str, int]:
    """Occurrence count per IDENTIFIER, ignoring string literals.

    Comparing this against :func:`token_name_counts` attributes each blocked
    symbol to a real caller (``ident[name] > 1``) or to the dynamic-reference
    clause of the soundness proof alone (``ident[name] == 1 < counts[name]``,
    i.e. only a string literal mentions it). Reported unscored -- it is a
    limitation, not a quality signal.
    """
    counts: Dict[str, int] = {}
    for src in sources:
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
            counts[UNPARSED] = counts.get(UNPARSED, 0) + 1
            continue
        for tok in toks:
            if tok.type == tokenize.NAME:
                counts[tok.string] = counts.get(tok.string, 0) + 1
    return counts


def blocked_by_string_only(
    dead: Set[Symbol], counts: Dict[str, int], ident: Dict[str, int]
) -> Set[Symbol]:
    """Blocked symbols that NO identifier mentions -- only a string literal does.

    These are exactly the cases the string-literal clause of the soundness proof
    is doing the work for. If this set is large the rule is mostly refusing for
    dynamic-reference reasons rather than for lack of callers, which is worth
    knowing before trusting the certification count.
    """
    return {
        s
        for s in dead
        if counts.get(bare(s), 0) > 1 and ident.get(bare(s), 0) == 1
    }


def self_check() -> None:
    """Assert-based self-check for the certification rule and both preconditions."""
    src = {
        "m.py": (
            "import os\n"
            "def only_ref_itself():\n    return 1\n"
            "def called_from_here():\n    return only_ref_itself()\n"
            "def recursive():\n    return recursive()\n"
            "def only_in_a_string():\n    return 2\n"
            "def wire():\n    return globals()['only_in_a_string']()\n"
            "def complex_site(reg):\n    return reg['handler']()\n"
        ),
        "syntax_error.py": "def oops(:\n",
    }
    counts = token_name_counts(src.values())
    dead = {
        "m.only_ref_itself",
        "m.called_from_here",
        "m.recursive",
        "m.only_in_a_string",
        "m.complex_site",
    }
    got = certify_unreferenced(dead, counts)
    # Occurs once (its own def) -> certified. This is the case run 4 REFUSED on
    # any repo containing the <complex> site below, and it is the whole point.
    assert got == {"m.called_from_here", "m.complex_site"}, got
    # A real caller blocks it.
    assert "m.only_ref_itself" in name_mentioned_elsewhere(dead, counts)
    # Self-recursion blocks it: two occurrences, one of which is a real call.
    assert "m.recursive" in name_mentioned_elsewhere(dead, counts)
    # A STRING literal reference blocks it -- getattr/globals escape closed.
    assert "m.only_in_a_string" in name_mentioned_elsewhere(dead, counts)
    # The <complex> site does NOT block anything: the rule has no such
    # precondition. Asserted so a future "restore run 4's gate" edit fails here.
    assert "m.complex_site" in got
    # Precondition: an untokenisable file refuses.
    assert UNPARSED in counts
    assert not corpus_complete(2, 2, counts)
    # ...and with the bad file dropped, still refuses (1 of 2 files seen).
    clean = {k: v for k, v in src.items() if k != "syntax_error.py"}
    clean_counts = token_name_counts(clean.values())
    assert UNPARSED not in clean_counts
    assert corpus_complete(2, 1, clean_counts) is False
    assert corpus_complete(2, 2, clean_counts) is True
    # Identifier-only recount separates the string-only names.
    ident = recount_identifiers_only(clean.values())
    assert "only_in_a_string" in ident, "the def is an identifier occurrence"
    assert "handler" not in ident, "only a string literal names handler"
    assert blocked_by_string_only(dead, counts, ident) == {"m.only_in_a_string"}
    print(
        "04_symbol_domain self-check OK",
        {"certified": sorted(got), "blocked": sorted(dead - got)},
    )


if __name__ == "__main__":
    self_check()
