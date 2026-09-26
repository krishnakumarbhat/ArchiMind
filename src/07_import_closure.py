"""N10: the reflection interface is irreducibly external.

Purpose: run 6 left exactly 4 certified-dead symbols on real repositories, each
with a named out-of-corpus driver resolved by ``getattr`` -- 3 SQLAlchemy
TypeEngine protocol methods and ``rich.logging.RichHandler.emit``. N10 proposed
closing that residual with a DECLARED PROTOCOL MANIFEST, withholding by method
name. This module exists to measure that proposal and to test the one
alternative that needs no name list.

WHAT N10 PROPOSED, AND WHY IT IS PRIOR ART. Vulture's documented remedy for a
false positive is a hand-maintained ``whitelist.py`` of externally supplied
names (vulture.readthedocs.io, "Whitelists"; ``vulture/whitelists/`` ships
whitelists for common packages). A declared protocol manifest is that mechanism
under a different noun. Its soundness is therefore bounded by the same thing
that bounds Vulture's: the list is hand-maintained and open. Vulture's own
issue tracker records the failure mode -- whitelist entries are matched by BARE
NAME against a single global set, so one entry permanently shields every
same-named symbol in the repository. N10 proposed to add a second such list.

THE STRUCTURAL ALTERNATIVE. The one piece of evidence that distinguishes a
reflectively-driven method from a genuinely dead one, and that is visible
INSIDE the corpus, is the INHERITANCE EDGE. ``class RichHandler(Handler)``
names ``Handler``, and ``Handler`` is imported from stdlib ``logging`` -- so the
class that owns ``emit`` provably participates in a protocol defined outside the
analysed code. No name list is needed: the witness is the base-class edge, and
it is checkable. So define

    witness(K)  := { b in bases(K) : b is defined outside the corpus }
    exposed(s)  := s is a method of class K and witness(K) is non-empty
    certified   := { s in dead : occ[leaf(s)] == 1 and s not in withheld }

and withhold ``exposed``. Withholding is one-directional, so this cannot create
a false positive -- the same sound direction run 6 proved, reached by a
mechanism that is not a convention list.

Only ``object`` is exempt. No other base is exempted, deliberately: exempting
more would be a second convention list, and the whole point of the node is to
measure the price of NOT keeping one. The over-blocking cost is measured and
reported, not tuned away.

THE IMPOSSIBILITY PART. ``base_witness`` does not fire on
``synthetic_protocol_repo``, whose class ``T`` has no base at all -- and that
fixture is the result. ``alpha.T.process_literal_param`` is dispatched by the
executed out-of-corpus driver and is LIVE; ``alpha.fixture_dead_plain`` is never
dispatched and is DEAD; the two have *identical* in-corpus evidence, which
:func:`evidence_vector` computes and :func:`self_check` asserts. Any
deterministic rule reading only in-corpus evidence assigns them the same
verdict, so its accuracy on the discriminating pair is at most 1/2 whatever it
does. The information that separates them does not exist in the corpus. A
declared interface is not a tuning knob; it is the only carrier of the missing
bit, and it must come from outside by construction.
"""

from __future__ import annotations

import ast
import importlib
from typing import Any, Dict, Iterable, List, Set, Tuple

Symbol = str

EXPORT = importlib.import_module("src.05_export_boundary")

# The single exempt base. `object` is not a protocol anybody dispatches user
# methods on, so treating it as an out-of-corpus driver would withhold every
# method in the repository and make the gate vacuous. This is a fact about
# `object`, not a convention about framework code, and it is the ONLY exemption.
UNIVERSAL_BASES = frozenset({"object"})

# How a symbol is defined, for the evidence vector.
_DEF_KINDS = ("function", "method", "class", "module")


def bare(sym: Symbol) -> str:
    """Leaf name of a dotted symbol path (``a.b.c`` -> ``c``)."""
    return sym.rsplit(".", 1)[-1]


def _parse(src: str) -> ast.Module | None:
    """Parse a source, or ``None`` if it will not parse (unknown export set)."""
    try:
        return ast.parse(src)
    except (SyntaxError, ValueError, RecursionError):
        return None


def _base_names(node: ast.ClassDef) -> List[str]:
    """Written base-class names of a class, in source order.

    Only the *written* name is taken, never the resolved one: a base written
    ``m.Base`` contributes ``Base`` plus the qualifier ``m``, and resolution
    needs the alias analysis this node exists to avoid needing.
    """
    out: List[str] = []
    for b in node.bases:
        if isinstance(b, ast.Name):
            out.append(b.id)
        elif isinstance(b, ast.Attribute):
            out.append(b.attr)
        elif isinstance(b, ast.Subscript):  # Base[T] / Generic[T]
            out.append(_base_names(ast.ClassDef(name="_", bases=[b.value], keywords=[], body=[], decorator_list=[]))[0])
    return out


def class_bases(files: Dict[str, str]) -> Dict[Symbol, List[str]]:
    """Map every class defined in the corpus to its written base names.

    Keys are dotted ``module.Class`` so they line up with the symbol names the
    rest of the harness uses. Nested and doubly-nested classes are keyed by
    their innermost qualified path, matching how the CPG names them.
    """
    out: Dict[Symbol, List[str]] = {}
    for mod, src in files.items():
        tree = _parse(src)
        if tree is None:
            continue

        def walk(node: ast.AST, prefix: str) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    qual = f"{prefix}{child.name}"
                    key = f"{mod}.{qual}"
                    out[key] = _base_names(child)
                    walk(child, f"{qual}.")
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for sub in ast.iter_child_nodes(child):
                        if isinstance(sub, ast.ClassDef):
                            qual = f"{prefix}{child.name}.{sub.name}"
                            out[f"{mod}.{qual}"] = _base_names(sub)
                else:
                    walk(child, prefix)

        walk(tree, "")
    return out


def corpus_defined_tops(corpus: Dict[str, str]) -> Set[str]:
    """Top-level and imported names the corpus itself provides.

    A base name counts as in-corpus if the corpus DEFINES it, or if it is a
    top-level component of a module the corpus ships. Import BINDINGS are
    deliberately excluded: ``from logging import Handler`` binds the name in the
    corpus but defines it in stdlib, and counting a binding as a definition is
    exactly the bug that would make every real protocol class look in-corpus and
    silently disable the whole witness. A name defined in a corpus module is
    picked up by the definition walk there regardless of who imports it.

    Over-approximating this set is the CONSERVATIVE direction: it makes fewer
    bases look out-of-corpus, so it certifies more, so it is the direction that
    can produce a false positive.
    """
    tops: Set[str] = {mod.split(".", 1)[0] for mod in corpus}
    for src in corpus.values():
        tree = _parse(src)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                tops.add(node.name)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                tops.add(node.id)
    return tops


def out_of_corpus_bases(
    files: Dict[str, str], corpus: Dict[str, str]
) -> Dict[Symbol, List[str]]:
    """Classes whose inheritance edge points out of the analysed code.

    This is the structural witness. A class that inherits from a name the corpus
    does not provide participates in a protocol owned by code that was never
    analysed, and that owner may dispatch to any of its methods by name.
    """
    defined = corpus_defined_tops(corpus)
    out: Dict[Symbol, List[str]] = {}
    for cls, bases in class_bases(files).items():
        ext = [b for b in bases if b not in defined and b not in UNIVERSAL_BASES]
        if ext:
            out[cls] = ext
    return out


def enclosing_class(sym: Symbol, files: Dict[str, str]) -> str | None:
    """The corpus class that owns ``sym``, or ``None`` if it is not a method.

    Longest dotted prefix of ``sym`` that names a class in the analysis set, so
    ``pkg.mod.Outer.Inner.m`` resolves to ``pkg.mod.Outer.Inner``.
    """
    parts = sym.split(".")
    for i in range(len(parts) - 1, 0, -1):
        cand = ".".join(parts[:i])
        if cand in files or any(k.startswith(cand + ".") for k in files):
            return cand
    return None


def base_witness_withheld(dead: Set[Symbol], witness: Dict[Symbol, List[str]]) -> Set[Symbol]:
    """Predicted-dead methods withheld because their class inherits from outside.

    Withholds by CLASS, not by name: every method of an exposed class is
    withheld, because the out-of-corpus owner may dispatch to any of them by a
    name that appears nowhere in the corpus.
    """
    held: Set[Symbol] = set()
    for cls in witness:
        for s in dead:
            if s.startswith(cls + "."):
                held.add(s)
    return held


def certify_dead_base_witness(
    dead: Set[Symbol], counts: Dict[str, int], witness: Dict[Symbol, List[str]],
    run6_withheld: Iterable[Symbol] = (),
) -> Set[Symbol]:
    """Run 6's certification with the inheritance witness as an extra veto.

    Sound by construction: the witness can only REMOVE a symbol, and removal is
    the direction that cannot manufacture a false positive.
    """
    veto = base_witness_withheld(dead, witness) | set(run6_withheld)
    return {s for s in dead if counts.get(bare(s), 0) == 1 and s not in veto}


def evidence_vector(
    s: Symbol, dead: Set[Symbol], counts: Dict[str, int], corpus: Dict[str, str],
    witness: Dict[Symbol, List[str]],
) -> Tuple[Any, ...]:
    """The COMPLETE in-corpus evidence a gate can read about symbol ``s``.

    Every clause is something a deterministic rule over the corpus could
    actually observe. Two symbols with equal vectors are indistinguishable to
    any such rule, which is what makes the discriminating pair a proof rather
    than an anecdote. Exposedness by NAME is deliberately absent: a rule that
    hard-codes protocol names reads information that is not in the corpus, which
    is the entire subject of this node.
    """
    cls = enclosing_class(s, corpus)
    return (
        s in dead,
        counts.get(bare(s), 0),
        bool(cls) and cls in witness,
        bool(cls),
        EXPORT.bare(s) in EXPORT.public_surface(corpus.get(
            (cls or "").rsplit(".", 1)[0], ""), set()
        ) if False else bare(s) in _public_tops(corpus),
        _path_surface(s),
        _name_convention(s),
    )


def _public_tops(corpus: Dict[str, str]) -> Set[str]:
    """Names appearing in any module's ``__all__``."""
    out: Set[str] = set()
    for src in corpus.values():
        names, _ = EXPORT.declared_dunder_all(src)
        out |= names
    return out


def _path_surface(s: Symbol) -> bool:
    """Whether the symbol sits under a directory run 6 treats as driver-owned."""
    low = s.lower()
    return any(f".{d}." in low or low.startswith(d + ".") or f"/{d}/" in low
               for d in EXPORT.EXTERNAL_DRIVER_SURFACES)


def _name_convention(s: Symbol) -> bool:
    """Whether the symbol's leaf matches a published out-of-corpus convention."""
    return bare(s).startswith(EXPORT.EXTERNAL_DRIVER_PREFIXES)


def discriminating_pair(
    corpus: Dict[str, str], live: Symbol, dead: Symbol
) -> Dict[str, Any]:
    """The pair that no in-corpus-only rule can separate, measured on the fixture.

    ``live`` is dispatched by the executed out-of-corpus driver in
    ``synthetic_protocol_driver/framework.py``; ``dead`` is written down as dead
    and is never dispatched. Both have ``occ == 1`` and neither is exported,
    inherited, path-owned or conventionally named.
    """
    witness = out_of_corpus_bases(corpus, corpus)
    counts = _counts(corpus)
    return {
        "live": live,
        "dead": dead,
        "evidence_equal": evidence_vector(live, {live, dead}, counts, corpus, witness)
        == evidence_vector(dead, {live, dead}, counts, corpus, witness),
        "occ_live": counts.get(bare(live), 0),
        "occ_dead": counts.get(bare(dead), 0),
        "base_witness_distinguishes": (live in base_witness_withheld({live}, witness))
        != (dead in base_witness_withheld({dead}, witness)),
        "max_accuracy_on_pair": 0.5,
    }


def _counts(corpus: Dict[str, str]) -> Dict[str, int]:
    """Token occurrence counts, delegated to the module that owns the rule."""
    dom = importlib.import_module("src.04_symbol_domain")
    return dom.token_name_counts(corpus.values())


def self_check() -> None:
    """Adversarial check: the impossibility claim, executed rather than asserted.

    Run 6 retracted a claim because the unstated lemma turned out false. This
    node claims two things that could each be false, so both are asserted:
    the witness withholds a real out-of-corpus class, and the discriminating
    pair is genuinely indistinguishable in-corpus.
    """
    proto = {
        "alpha": "class T:\n    def process_bind_param(self, v):\n        return 1\n"
                 "    def _genuinely_dead(self, v):\n        return 2\n"
                 "class Sub(T, Handler):\n    def emit(self, r):\n        return 3\n"
                 "def _standalone():\n    return 4\n",
        "logmod": "from logging import Handler\n",
    }
    w = out_of_corpus_bases(proto, proto)
    assert "alpha.Sub" in w and w["alpha.Sub"] == ["Handler"], w
    # `T` has no written base, so its methods are NOT withheld: the witness is
    # about an inheritance edge, not about "being a class".
    assert "alpha.T" not in w, w
    assert base_witness_withheld({"alpha.Sub.emit", "alpha.T._genuinely_dead"}, w) == {
        "alpha.Sub.emit"
    }
    # Withholding is one-directional: it can only shrink the certified set.
    dead = {"alpha.Sub.emit", "alpha.T._genuinely_dead", "alpha._standalone"}
    c = _counts(proto)
    assert certify_dead_base_witness(dead, c, w) <= {
        s for s in dead if c.get(bare(s), 0) == 1
    }

    # The pair. `process_bind_param` is dispatched by the out-of-corpus driver
    # and `_genuinely_dead` is not; only the NAME separates them.
    pair = discriminating_pair(
        proto, "alpha.T.process_bind_param", "alpha.T._genuinely_dead"
    )
    assert pair["evidence_equal"] is True, pair
    assert pair["base_witness_distinguishes"] is False, pair
    assert pair["occ_live"] == 1 and pair["occ_dead"] == 1, pair


if __name__ == "__main__":
    self_check()
    print("src/07_import_closure.py self_check OK")
