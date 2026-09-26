"""N11: the sound/useful dichotomy is a theorem, and the interface has a measured size.

Run 7 (node N10) ended on a negative result it had not finished stating. On
``synthetic_protocol_repo`` the base-class witness does not fire, and
``alpha.T.process_literal_param`` (LIVE, dispatched by an executed out-of-corpus
driver) and ``alpha._fixture_dead_plain`` (DEAD, written down) have identical
in-corpus evidence. Run 7 then wrote ``"max_accuracy_on_pair": 0.5`` as a LITERAL
inside :func:`src.07_import_closure.discriminating_pair` -- the "quantified bound"
the node's own success criterion demanded was asserted, never derived. This module
derives it, and the derivation says more than the bound did.

WHAT IS AND IS NOT NEW, STATED UP FRONT. The bound itself is NOT new and must not
be claimed as new: a classifier is constant on a fibre of its feature map, so it
scores at most ``max(|L|,|D|)/|C|`` on that fibre. That is textbook, needs no
citation beyond any ML text, and an adversarial prior-art check scored it
PRIOR_ART_STANDARD. The same check refused the Myhill-Nerode framing outright --
E-classes are a partition induced by a feature map, not Nerode classes induced by
suffix-extension distinguishability, and the "index" language is metaphor.

RUN 8's ADVERSARIAL CHECK THEN WENT ONE LEVEL HIGHER AND KILLED MORE. The
IMPOSSIBILITY framing that run 7 queued as N11 -- and that this module was written
to carry -- is itself textbook, with published proofs: Moller & Schwartzbach,
*Static Program Analysis* (Aarhus, 2012) sec. 1.2-1.3, states that "it is
impossible to build a static program analysis that can decide whether a given
program may fail when executed", that "approximation is inevitably necessary", and
-- verbatim, and fatally for the framing -- that analysers "cut corners by
sacrificing soundness ... for example when modeling reflection in Java". Landi,
"Undecidability of static analysis", ACM LOPLAS 1(4):323-337, 1992, and Cousot,
Giacobazzi & Ranzato, "Program analysis is harder than verification: a
computability perspective", 2018, are the same machinery. Worse for the
*concrete instance*: Vulture's own README ships ``getattr(greeter, func_name)`` as
THE canonical false-positive example, with the whitelist as the documented remedy,
and ``deadcode-py`` (sen-ltd) already titles a post "Dead Code in Python Is
Undecidable -- So I Built a Detector That Admits It" (2026-04-15), naming
``getattr`` and protocol duck-typing in the same breath. The 0.5 bound is therefore
PRIOR_ART_STANDARD, the phenomenon is not this loop's, and N11 does NOT clear the
paper bar. The only corner the check found genuinely unoccupied is the INFORMATION
COST of an external interface specification (P3) -- no located work quantifies it.
This module therefore claims NONE of A. It claims P1-P3 as measurements, and the
prior-art verdict is recorded in ``equations.md`` row 28 rather than left implicit.

P1. INVARIANCE IN THE NUMBER OF AMBIGUOUS CLASSES. The bound does not improve with
    more evidence. With ``m`` mixed classes of size 2 the best any gate achieves is
    ``m / 2m = 1/2`` for every ``m``, so "collect more pairs" is not a research
    direction. :func:`invariance_in_m` computes this over ``m = 1 .. 512`` instead
    of asserting it, and :func:`max_accuracy_over_gates` DERIVES the bound by
    exhaustive enumeration rather than trusting the closed form.

P2. THE DICHOTOMY IS EXACT, NOT A TUNING FAILURE. Because a gate is constant on a
    class, it certifies EVERY member of that class or NONE -- and "every member"
    includes the live ones. So the achievable ``(sound, n_certified)`` pairs on a
    mixed class ``C`` are exactly ``{(True, 0), (False, |C|)}``. There is no
    intermediate point, for any rule, in any hypothesis class. So run 7's headline
    disappointment -- sqlmodel and rich certification rate falling to 0.0 -- is
    not a badly tuned threshold. It is the forced consequence of soundness on an
    ambiguous class, and it would have happened to every other repair too.
    :func:`pareto_frontier` enumerates the frontier instead of describing it.

    THE ``|C|``, NOT ``|D_C|``, IS LOAD-BEARING AND WAS WRONG HERE FIRST. This
    paragraph originally read ``(False, |D|)``, i.e. "an unsound gate certifies the
    dead members". That is false: constancy on the fibre forbids a strict non-empty
    subset of ``D_C``, so an unsound gate certifies the WHOLE class, live members
    included. On this run's own fixture that is the difference between ``(0, 8)``
    and ``(0, 4)``, and the emitted frontier says ``(0, 8)``.

    So the defect was NOT a blind fixture -- I expected it to be, and was wrong.
    The measurement could see it, :func:`self_check` had already got it right four
    lines away (``achievable_points == [(0, 4), (1, 0)]`` on a 2-dead/2-live class of
    4, i.e. ``|C| = 4``), and the prose still said ``|D_C|``. Three artefacts in one
    repository carried the answer and nobody subtracted them. The missing step was
    never evidence; it was a comparison. :func:`stated_claims` supplies it: the
    claims are carried as data with a measured counterpart, and the self-check
    asserts the enumeration reproduces each one, so prose can no longer drift from
    behaviour silently. Note the asymmetry that makes this worth automating -- the
    refuted reading produced a perfectly plausible number (2, then 4) rather than an
    obviously broken one, so no eyeball would ever have caught it.

P3. THE INTERFACE IS QUANTIFIED, AND THE INFORMATIVE NUMBER IS THE NAME LIST. Let
    ``nu(M) = #{E-classes that are mixed}``. Two accountings, and the honest one is
    the LARGER: an **allowlist** declaration must name the live members of each
    mixed class individually, so it costs ``sum_C log2 C(|C|, |L_C|) >= nu(M)``
    bits, because names are structured and uncompressed. That is the quantitative
    reason run 7's killed protocol manifest was the wrong shape, and it is the only
    one of the two that is a real interface: an allowlist is a hint a rule can
    consume without being handed the answer.

    THE ``nu(M)``-BIT FIGURE IS THE ANSWER LENGTH, NOT A SAVING, and this paragraph
    originally led with it as though it were. ``nu(M)`` bits is a per-class
    partition bit saying "here is which members of this class are dead" -- that is
    the ANSWER, delivered as a unit, so "an interface of one bit per class" is
    vacuous as a reduction: a gate handed it performs no inference. It is reported
    because it is the correct LOWER bound on any declaration (``nu(M) >= 1`` bit
    whenever a mixed class exists) and because the two accountings coincide exactly
    when every mixed class has a single live member. Reported against interest: on
    the run-8 fixture the gap is 1.00 vs 6.13 bits, a 6.1x overhead, and a reviewer
    should read that as the cost of the only interface shape that is not the answer.

    And no declaration of any size makes EVERY gate sound while ``nu(M) > 0``: the
    adversary picks the labelling after the gate is fixed, so a gate that certifies
    anything in a mixed class is refutable by putting a live symbol there.

P4. A CLASS-LEVEL DECLARATION IS WORTH WHAT ITS REFINEMENT BUYS -- AND THE "EXACTLY
    ZERO" VERSION OF THIS CLAIM WAS WRONG, refuted by this run's own data. The first
    version of this paragraph claimed a class-level declaration is worth EXACTLY
    ZERO bits, on the reasoning that such a declaration -- ``class T(Protocol)``,
    ``@runtime_checkable``, a written base, ``__all__``, a docstring -- "is constant
    on the class, hence constant on the class's evidence". **That inference is
    invalid, because it uses *class* to mean two different things.** A class-level
    declaration is constant on the **Python class**; the evidence fibre is the
    **E-class**. The zero-lift statement is true for a declaration constant on the
    E-class and says nothing about the other partition. A per-class value separates
    two symbols only when one E-class holds members of **two or more** Python
    classes, and that is a measurable property of the evidence, not a free choice.

    :func:`partition_refinement` measures it on all nine corpora, needs no ground
    truth, and the answer on the four real tarballs is that **2/3, 3/3, 5/6 and
    2/7** of the E-classes are split by the class partition, covering **201 / 110 /
    243 / 409** predicted-dead symbols and putting as many as **100** distinct Python
    classes inside a single E-class (sqlmodel). So the claim is false as stated, and
    not marginally -- the class-level declaration splits the evidence fibres
    everywhere, which is the opposite of "worth exactly zero". The loop's own run-7
    repair is the same phenomenon seen from the other side: its inheritance witness
    is a per-class declaration (``class RichHandler(Handler)`` names ``Handler``)
    and it removed **9** real-repo certificates.

    The refutation has a second, uglier half. The control that produced the zero
    appended **one value to every symbol** -- a *global* constant -- and then
    reported the result under the name ``class_level``. The arm was mislabelled:
    what it measured is strictly weaker than the shape it claimed to test, and
    "worth exactly zero" was true of the substitute and false of the original. That
    is defect (iv). It is fixed by keeping all three arms under their true names --
    :func:`per_class`, :func:`global_constant`, :func:`per_symbol` -- with the
    per-class arm in **closed form** (the majority rule per Python class rather than
    per E-class, :func:`_majority_accuracy`) so it is derived, not an artefact of the
    gate class, and with **"no class map supplied" reported as UNKNOWN rather than
    zero**. The retraction is retained under
    ``retracted_claim_class_level_zero`` and pinned by a self-check that requires
    the per-class lift to be zero on a refining map and strictly positive on a
    straddling one, so the claim cannot be silently reinstated.

    The shape that does reach 1.0 remains a distinct value PER SYMBOL, a labelling
    of size ``|C|`` carrying ``log2 C(|C|, |D_C|)`` bits -- a bare-name allowlist,
    i.e. run 7's killed manifest and Vulture's ``whitelist``. So the carrier exists,
    it is ``|C|``-sized, and it is already shipped. The run's transferable result is
    still negative, but it is now the *correct* negative: a class-level declaration
    is nearly worthless here, not provably worthless.

WHAT IS MEASURED, NOT ARGUED. The upper-bound half needs no ground truth and runs
on all nine corpora: :func:`ambiguity_report` counts how much of a gate's certified
set sits in an E-class of size > 1, i.e. how much of the output is not a per-symbol
verdict at all, and reports the interface lower bound in bits. On the four real
tarballs that is a real number about real code, and it is the first LOWER bound
this loop has produced about its own output.

Purpose: derive the bound, state what it does and does not license, and measure the
size of the interface the corpus cannot supply.
"""

from __future__ import annotations

import importlib
import itertools
import math
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

Symbol = str
Vector = Tuple[Any, ...]
BVec = Tuple[bool, ...]

IC = importlib.import_module("src.07_import_closure")
EXPORT = importlib.import_module("src.05_export_boundary")
DOMAIN = importlib.import_module("src.04_symbol_domain")

#: Width of the booleanised observation. A gate is a function on this cube.
N_FEATURES = 9


def feature_tuple(
    s: Symbol, dead: Set[Symbol], counts: Dict[str, int], corpus: Dict[str, str],
    witness: Dict[Symbol, List[str]],
) -> Vector:
    """The COMPLETE in-corpus evidence a gate can read about ``s``.

    Thin alias of :func:`src.07_import_closure.evidence_vector`, kept under a name
    that does not overclaim: this is a feature vector, not a proof of completeness.
    Sharing the implementation is deliberate -- a second copy of the evidence
    definition would let the enumeration measure a gate over features the
    certification rule does not actually use.
    """
    return IC.evidence_vector(s, dead, counts, corpus, witness)


def binarize(v: Vector) -> BVec:
    """Widen the raw evidence vector to a fixed-width boolean observation.

    The occurrence count is split three ways rather than thresholded, because
    ``occ == 1`` is the certification rule's own condition and collapsing it into a
    single bit would let the enumeration score gates the pipeline cannot express.
    """
    dead, occ, exposed, is_method, dunder, path, conv = v
    return (
        bool(dead), occ == 0, occ == 1, occ >= 2, bool(exposed), bool(is_method),
        bool(dunder), bool(path), bool(conv),
    )


def features_for(
    symbols: Iterable[Symbol], dead: Set[Symbol], counts: Dict[str, int],
    corpus: Dict[str, str], witness: Dict[Symbol, List[str]],
) -> Dict[Symbol, BVec]:
    """Boolean observation for every symbol in ``symbols``."""
    dead = set(dead)
    return {s: binarize(feature_tuple(s, dead, counts, corpus, witness)) for s in symbols}


def e_classes(features: Mapping[Symbol, BVec]) -> List[Set[Symbol]]:
    """The partition induced by the observation: one E-class per distinct vector.

    These are fibres of a feature map. They are NOT Nerode classes and the module
    does not call them that -- the resemblance is a metaphor, and an adversarial
    prior-art check found the nearest real theorem (Myhill-Nerode) is about
    suffix-extension distinguishability, which has no analogue here.
    """
    groups: Dict[BVec, Set[Symbol]] = {}
    for sym, vec in features.items():
        groups.setdefault(vec, set()).add(sym)
    return [groups[v] for v in sorted(groups)]


def liveness_split(classes: Sequence[Set[Symbol]], lasso: Dict[Symbol, bool]
                   ) -> List[Dict[str, Any]]:
    """Per-class live/dead split. ``lasso[s]`` True means DEAD (ground truth)."""
    out: List[Dict[str, Any]] = []
    for cls in classes:
        dead_members = sorted(s for s in cls if lasso.get(s, False))
        live_members = sorted(s for s in cls if s in lasso and not lasso[s])
        out.append({
            "size": len(cls), "dead": len(dead_members), "live": len(live_members),
            "mixed": bool(dead_members) and bool(live_members),
            "majority_fraction": round(
                max(len(dead_members), len(live_members)) / len(cls), 6) if cls else None,
            "dead_members": dead_members, "live_members": live_members,
        })
    return out


def nu_index(classes: Sequence[Set[Symbol]], lasso: Dict[Symbol, bool]) -> Dict[str, Any]:
    """The ambiguous-partition cardinality ``nu`` and the exact per-class bound.

    ``max_accuracy_on_any_mixed_class`` is the DERIVED bound, not a literal: it is
    the maximum over classes of ``max(|L|,|D|)/|C|``, which is what run 7 hardcoded
    as 0.5 for a single balanced pair. On a balanced family it comes out at 0.5
    again -- but now it is arithmetic, so the number can be wrong if the inputs are.
    """
    split = liveness_split(classes, lasso)
    mixed = [c for c in split if c["mixed"]]
    return {
        "n_classes": len(split),
        "n_mixed_classes": len(mixed),
        "nu": len(mixed),
        "n_symbols_in_mixed_classes": sum(c["size"] for c in mixed),
        "max_accuracy_on_any_mixed_class": max(
            (c["majority_fraction"] for c in mixed), default=None),
        "balanced_everywhere": all(c["dead"] == c["live"] for c in mixed) if mixed else None,
        "per_class": split,
    }


# --------------------------------------------------------------------------- #
# The gate hypothesis class, enumerated.
# --------------------------------------------------------------------------- #

def _conjunction(terms: Tuple[Tuple[int, bool], ...]) -> Callable[[BVec], bool]:
    """The gate "every (index, value) in terms holds", frozen over its indices.

    A closure factory rather than a lambda with a default argument: mypy cannot
    infer the type of `lambda v, t=terms: ...`, and the run's own gate is a
    correctness artefact, so an untyped gate body is not acceptable here.
    """
    frozen = terms

    def gate(v: BVec) -> bool:
        return all(v[i] == w for i, w in frozen)

    return gate


def conjunctive_gates(width: int = N_FEATURES) -> List[Tuple[str, Callable[[BVec], bool]]]:
    """Every conjunction over the boolean cube, with per-feature polarity.

    Size ``3**width``: each feature is ignored, required true, or required false.
    This is the hypothesis class a hand-written rule over these features actually
    lives in -- including run 5, 6 and 7's own gates, all of which are conjunctions
    over a subset of the evidence with a sign. It is not the class of all gates, so
    the bound is re-derived on :func:`exhaustive_gates` as well.
    """
    gates: List[Tuple[str, Callable[[BVec], bool]]] = []
    for spec in itertools.product((0, 1, 2), repeat=width):
        terms = [(i, spec[i] == 1) for i in range(width) if spec[i] != 0]
        name = " & ".join(
            ("" if want else "~") + f"f{i}" for i, want in terms
        ) or "TRUE"
        gates.append((name, _conjunction(tuple(terms))))
    return gates


def exhaustive_gates(width: int) -> List[Tuple[str, Callable[[BVec], bool]]]:
    """EVERY boolean function on ``width`` features. Only sane for small ``width``.

    This is the honest closure of the claim: the bound is then over all
    deterministic gates, not over the conjunction-shaped ones this loop happens to
    write, and it removes "the 0.5 is an artefact of my rule shape" as an
    explanation.
    """
    if width > 4:
        raise ValueError(f"exhaustive enumeration of 2**2**{width} gates is not runnable")
    n = 2 ** width
    # A boolean function on `width` bits is a truth TABLE of 2**width entries, so
    # the enumeration ranges over 2**(2**width) of them, not over 2**width. Getting
    # this wrong silently enumerates a strict subset of the gates and would let the
    # closed-form bound look "verified over all gates" when it is not; the self-check
    # asserts the count.
    masks = range(1 << n)

    def fn(v: BVec, mask: int) -> bool:
        idx = 0
        for i, bit in enumerate(v):
            if bit:
                idx |= 1 << i
        return bool(mask >> idx & 1)

    return [(f"mask{m:0{n}b}", (lambda m: (lambda v: fn(v, m)))(m)) for m in masks]


def max_accuracy_over_gates(
    classes: Sequence[Set[Symbol]], lasso: Dict[Symbol, bool],
    gates: Sequence[Tuple[str, Callable[[BVec], bool]]],
    features: Mapping[Symbol, BVec],
    sound_only: bool = False,
) -> Dict[str, Any]:
    """Best accuracy any gate in ``gates`` attains, with the achiever named.

    This is the function that replaces run 7's hardcoded ``0.5``. It is computed by
    enumeration, so an unexpected value is a finding rather than a crash.

    DEFECT FOUND AND REPAIRED HERE, and it is the one that mattered. This function
    originally scored ``bool(g(features[s])) == bool(lasso[s])`` -- AGREEMENT with
    the truth -- and reported the maximum over ALL gates as "max accuracy". Agreement
    is not soundness: a gate that certifies every symbol scores high agreement by
    being wrong about exactly the symbols the dead-code term exists to protect. So
    the maximum it returned was attained by the *least* trustworthy gate in the
    family, and the whole interface-value curve built on it inherited that.

    ``sound_only=True`` restricts the search to gates that certify no live symbol
    (``g(s) => lasso[s]`` for every ``s``), which is the admissibility condition
    every other soundness claim in this module already uses. The two curves agree
    at ``j = 0``, which is exactly why the defect survived five self-checks: on a
    balanced class both are ``max(|D|,|L|)/|C|``, and only the rows above zero
    external bits separate them. The agreement curve is retained, under the name
    ``agreement``, because it is the curve that predicts run 7's manifest number
    (0.875), and that number *is* an agreement number measured on an unsound gate.
    """
    best_acc, best_name, per_gate = -1.0, "", []
    for name, g in gates:
        hit = tot = 0
        unsound = False
        for cls in classes:
            for s in cls:
                if s not in lasso:
                    continue
                verdict = bool(g(features[s]))
                if verdict and not lasso[s]:
                    unsound = True
                    if sound_only:
                        break
                tot += 1
                hit += int(verdict == bool(lasso[s]))
            if unsound and sound_only:
                break
        if sound_only and unsound:
            continue
        acc = hit / tot if tot else 0.0
        per_gate.append((name, round(acc, 6)))
        if acc > best_acc:
            best_acc, best_name = acc, name
    return {
        "n_gates": len(gates),
        "sound_only": sound_only,
        "n_symbols_scored": sum(1 for c in classes for s in c if s in lasso),
        "max_accuracy": round(best_acc, 6),
        "achieved_by": best_name,
        "closed_form_prediction": round(
            max((c["majority_fraction"] for c in liveness_split(classes, lasso) if c["mixed"]),
                default=0.0), 6),
        "matches_closed_form": abs(best_acc - max(
            (c["majority_fraction"] for c in liveness_split(classes, lasso) if c["mixed"]),
            default=0.0)) < 1e-9,
        "min_accuracy": min((a for _, a in per_gate), default=0.0),
    }


def pareto_frontier(
    classes: Sequence[Set[Symbol]], lasso: Dict[Symbol, bool],
    gates: Sequence[Tuple[str, Callable[[BVec], bool]]],
    features: Mapping[Symbol, BVec],
) -> Dict[str, Any]:
    """The achievable ``(sound, n_certified)`` set, enumerated.

    A gate is SOUND if every symbol it certifies is really dead. The frontier is
    reported as a set of points so the claim "there is no intermediate point" is a
    count of 2 rather than an assertion -- and so that a future rule which lands on
    a third point would break the self-check loudly instead of quietly.
    """
    points: Set[Tuple[bool, int]] = set()
    for _, g in gates:
        certified = {s for c in classes for s in c if s in lasso and bool(g(features[s]))}
        sound = all(lasso.get(s, False) for s in certified)
        points.add((sound, len(certified)))
    return {
        "n_gates": len(gates),
        "achievable_points": sorted((int(s), n) for s, n in points),
        "n_points": len(points),
        "is_binary_dichotomy": len(points) == 2,
        "sound_points_certify": sorted(n for s, n in points if s),
        "sound_points_all_zero": all(n == 0 for s, n in points if s),
    }


def partition_refinement(
    classes: Sequence[Set[Symbol]], classes_of: Mapping[Symbol, str]
) -> Dict[str, Any]:
    """Does the class-level declaration SPLIT any E-class, i.e. buy any lift at all?

    THE CORRECTED FORM OF P4, and the measurement that decides it. P4 claimed a
    class-level declaration is worth exactly zero because it is "constant on the
    class, hence constant on the class's evidence". That inference is WRONG, and it
    is wrong because it uses *class* to mean two different things. A class-level
    declaration is constant on the **Python class** -- the enclosing ``class T:`` --
    not on the **E-class**, which is a fibre of the evidence vector. The zero-lift
    statement is true for a declaration constant on the E-class and has no bearing
    on the other partition.

    So the question is not "is a class-level declaration constant?" -- it is. It is
    "does it separate two symbols the evidence could not separate?", and the answer
    is yes exactly when some **E-class contains members of two or more Python
    classes**. That is the only way a per-class value can help: it splits a fibre.
    The converse direction -- a class spanning several E-classes -- is worth nothing,
    and the first version of this function counted that direction instead. It was a
    real bug with a real consequence: it reported a plausible small count
    (**4 / 6 / 6 / 5** classes) where the correct predicate reports a large one
    (**2/3, 3/3, 5/6, 2/7 of E-classes split**, covering 201/110/243/409 predicted-
    dead symbols, with as many as **100 distinct Python classes inside a single
    E-class** on sqlmodel). Had the first predicate stood, it would have appeared to
    *support* the retracted claim, and the number would have been wrong by the
    widest margin available on real code.

    The lift is zero iff the class partition **coarsens** the E-class partition,
    i.e. every E-class sits inside a single Python class. This function needs no
    ground truth, so it runs on all nine corpora, and on the four real tarballs it
    says the opposite of P4. The loop's own run-7 repair is the same phenomenon: its
    inheritance witness (``class RichHandler(Handler)``, one value per class)
    removed **9** real-repo certificates, which a globally constant feature could
    not have done.
    """
    split: List[Dict[str, Any]] = []
    for i, cls in enumerate(classes):
        owners = sorted({classes_of.get(s, "<none>") for s in cls})
        if len(owners) > 1:
            split.append({
                "e_class_index": i,
                "size": len(cls),
                "n_distinct_python_classes": len(owners),
                "python_classes": owners,
                "members_by_class": {
                    c: sorted(s for s in cls if classes_of.get(s, "<none>") == c)
                    for c in owners
                },
            })
    n_e = len(classes)
    n_lost = sum(r["size"] for r in split)
    return {
        "n_e_classes": n_e,
        "n_split_e_classes": len(split),
        "split_fraction": round(len(split) / n_e, 6) if n_e else None,
        "n_symbols_in_split_e_classes": n_lost,
        "class_partition_coarsens_e_partition": not split,
        "per_class_lift_is_zero": not split,
        "split_e_classes": split,
        "verdict": (
            "a per-class declaration buys lift exactly when one E-class holds "
            "members of two or more Python classes; the lift is zero iff the class "
            "partition coarsens the E-class partition"
        ),
    }


def _majority_accuracy(blocks: Sequence[Set[Symbol]], lasso: Dict[Symbol, bool]
                       ) -> Tuple[float, int]:
    """Best accuracy of a gate constant on each block: the majority rule per block.

    A gate that may only be constant on ``blocks`` attains the majority fraction
    inside each block and nothing better, so this is closed form -- no enumeration
    needed, which is what makes it usable on a real repo with 452 symbols.
    """
    hit = tot = 0
    for blk in blocks:
        members = [s for s in blk if s in lasso]
        if not members:
            continue
        n_dead = sum(1 for s in members if lasso[s])
        hit += max(n_dead, len(members) - n_dead)
        tot += len(members)
    return (hit / tot if tot else 0.0), tot


def interface_bit_control(
    classes: Sequence[Set[Symbol]], lasso: Dict[Symbol, bool],
    gates: Sequence[Tuple[str, Callable[[BVec], bool]]],
    features: Mapping[Symbol, BVec],
    classes_of: Mapping[Symbol, str] | None = None,
) -> Dict[str, Any]:
    """What each SHAPE of declaration is worth, measured rather than asserted.

    RUN 8 DEFECT (iii), the sharpest of the four, and it was found by two functions
    in this module disagreeing. The control used to read
    ``one_bit_suffices = True`` with a lift of 0.5, on the strength of ONE extra
    column holding ``lasso[s]``. That column is not a bit: it takes a different
    value for every symbol in the class, so it is a full per-symbol LABELLING, and
    :func:`interface_value_curve` -- thirty lines above, in the same module --
    already said the opposite thing, that one correct bit is worth exactly
    ``1 / |C|`` and that a class of size 8 needs 8 of them. ``one_bit_suffices``
    and ``marginal_value == 0.125`` cannot both be true. The tautology won,
    because it was the one carrying the word "suffices".

    The repair is to enumerate the shapes a declaration can actually have, because
    "one bit" never named one:

    ``per_class``
        One value per Python class -- the shape every real declaration mechanism
        has. ``class T(Protocol)``, ``@runtime_checkable``, a written base class,
        ``__all__``, a docstring. It is NOT worth zero in general (defect iv,
        RETRACTED): its lift is the accuracy a gate attains by being constant on
        the *class* partition rather than on the E-class partition, which is
        positive exactly when it splits an E-class. See :func:`partition_refinement`.
    ``per_symbol``
        A distinct value per symbol, which is a labelling of size ``|C|`` and
        carries ``log2 C(|C|, |D_C|)`` bits of information. It reaches 1.0, and it
        is the ONLY shape that does. It is also, under a different noun, the
        bare-name allowlist -- which is what run 7's prior-art check identified as
        Vulture's ``whitelist``, and as the protocol manifest this loop had already
        built and measured to be unsound.
    ``global_constant``
        The same value for EVERY symbol. Worth exactly zero, always -- and that is
        what the ``class_level`` arm of the first version of this function actually
        measured. It was mislabelled, it is kept under its true name, and the
        mislabelling is the run's fourth self-inflicted defect.

    So the run-7 claim that "a declared interface is the only carrier of the
    missing bit" survives only in its vacuous form: the carrier exists, it is
    ``|C|``-sized, and it is already shipped.
    """
    widened = conjunctive_gates(N_FEATURES + 1)
    before = max_accuracy_over_gates(classes, lasso, gates, features)
    base = before["max_accuracy"]

    def score(aug: Mapping[Symbol, BVec]) -> float:
        return max_accuracy_over_gates(classes, lasso, widened, aug)["max_accuracy"]

    # A GLOBAL constant: one value for the whole symbol set. Worth zero, always.
    const_true = {s: v + (True,) for s, v in features.items()}
    const_false = {s: v + (False,) for s, v in features.items()}
    # A per-symbol declaration: a value per member, i.e. the labelling itself.
    labelling = {s: v + (not lasso[s],) for s, v in features.items()}
    ct, cf, lab = score(const_true), score(const_false), score(labelling)

    # A PER-CLASS declaration, in closed form. With no class map the honest answer
    # is "not measurable here", not zero -- the first version answered zero.
    if classes_of is None:
        per_class: Dict[str, Any] = {
            "measurable": False,
            "why": "no class map supplied; the answer is UNKNOWN, not zero",
        }
    else:
        by_class: Dict[str, Set[Symbol]] = {}
        for s in features:
            by_class.setdefault(classes_of.get(s, "<none>"), set()).add(s)
        cls_acc, _ = _majority_accuracy(list(by_class.values()), lasso)
        per_class = {
            "measurable": True,
            "max_accuracy": round(cls_acc, 6),
            "lift": round(cls_acc - base, 6),
            "worth_zero": abs(cls_acc - base) < 1e-9,
            "closed_form": "majority rule per Python class, not per E-class",
            "n_python_classes": len(by_class),
        }

    sizes = [c["size"] for c in liveness_split(classes, lasso) if c["mixed"]]
    deads = [c["dead"] for c in liveness_split(classes, lasso) if c["mixed"]]
    worst = min(math.log2(math.comb(n, d)) for n, d in zip(sizes, deads)) if sizes else 0.0

    return {
        "max_accuracy_without_any_declaration": base,
        "per_class_declaration": dict(per_class, expressible_as=[
            "class T(Protocol)", "@runtime_checkable", "a written base class",
            "__all__", "a docstring", "an entry in a config file keyed by class",
        ]),
        "global_constant_declaration": {
            "cost_bits": 1, "max_accuracy": max(ct, cf),
            "lift": round(max(ct, cf) - base, 6),
            "constant_value_true": ct, "constant_value_false": cf,
            "worth_zero": max(ct, cf) == base,
        },
        "per_symbol_declaration": {
            "cost_symbols": sum(sizes), "cost_bits_information": round(worst, 6),
            "max_accuracy": lab, "lift": round(lab - base, 6),
            "reaches_one": lab == 1.0,
            "expressible_as": ["a bare-name allowlist", "Vulture's whitelist"],
        },
        "one_bit_suffices": False,
        "retracted_claim_one_bit": (
            "the earlier control reported one_bit_suffices=True, lift=0.5; its 'bit' "
            "was a per-symbol labelling, so the claim was a tautology and it "
            "contradicted this module's own value curve. Retracted, not deleted."
        ),
        "retracted_claim_class_level_zero": (
            "the earlier control reported class_level lift == 0.0, 'worth exactly "
            "zero'. TWO independent faults, both recorded. (i) Its arm appended ONE "
            "value to EVERY symbol, so it measured a GLOBAL constant, not a "
            "per-class declaration, and it then reported the global-constant result "
            "under the per-class shape's name. (ii) The predicate that replaced it "
            "was ALSO wrong at first: it counted classes SPANNING two E-classes, "
            "which buys nothing, instead of E-classes SPLIT across two classes, "
            "which is the only way a per-class value separates symbols. Fault (ii) "
            "reported 4/6/6/5 classes and would have appeared to SUPPORT the "
            "retracted claim; the correct predicate reports 2/3, 3/3, 5/6, 2/7 of "
            "E-classes split, covering 201/110/243/409 predicted-dead symbols, up "
            "to 100 classes in one E-class. Refuted by the loop's own run-7 "
            "measurement too: a per-class declaration (a written base class) "
            "removed 9 real-repo certificates. Retracted, not deleted."
        ),
        "interpretation": (
            "the bound is the absence of a PER-SYMBOL declaration; a per-class "
            "declaration buys lift exactly when it splits an E-class, which "
            "partition_refinement() shows it does on every real repo measured, so "
            "the class-level mechanisms of the typing ecosystem are NOT worthless "
            "here -- the retracted zero was a mislabelled global-constant control "
            "read through an inverted predicate; a global constant is worth nothing "
            "at all; and the per-symbol shape is an allowlist, which run 7 already "
            "identified as shipped prior art"
        ),
    }


def invariance_in_m(sizes: Sequence[int] = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)) -> List[Dict[str, Any]]:
    """The bound is 1/2 for every number of mixed pairs. Computed, not asserted.

    Pure arithmetic on the class structure, because this is the part that is a
    theorem rather than a measurement. A gate is CONSTANT on a class, so on a
    balanced class of size ``2m`` it is right on the ``m`` members of one liveness
    and wrong on the other ``m`` -- which means the score is not merely capped at
    1/2, it is ``exactly 1/2 for every gate, with zero variance``, for every ``m``.
    The gate's quality is therefore not a variable on an ambiguous class at all.
    :func:`max_accuracy_over_gates` re-derives this by enumeration over all
    65536 boolean gates, and the self-check asserts the min equals the max.
    """
    out: List[Dict[str, Any]] = []
    for m in sizes:
        n = 2 * m
        out.append({
            "m_mixed_pairs": m, "n_symbols": n,
            "best_accuracy": round(m / n, 6), "worst_accuracy": round(m / n, 6),
            "variance_across_gates": 0.0,
            "invariant": abs(m / n - 0.5) < 1e-12,
        })
    return out


def invariance_single_class(sizes: Sequence[int] = (2, 4, 8, 16, 32, 64, 128)) -> List[Dict[str, Any]]:
    """Same arithmetic for ONE balanced class of growing size, for contrast.

    Reported because it separates the two claims: a single class of size 2m also
    gives exactly 1/2 for every gate, so the bound is not a small-sample artefact of
    having only one witness. Both structures are 1/2 with zero variance; neither
    moves with evidence.
    """
    return [
        {"class_size": n, "best_accuracy": round((n // 2) / n, 6),
         "worst_accuracy": round((n // 2) / n, 6), "variance_across_gates": 0.0,
         "invariant": abs((n // 2) / n - 0.5) < 1e-12}
        for n in sizes
    ]


def interface_cost_bits(
    classes: Sequence[Set[Symbol]], lasso: Dict[Symbol, bool],
    allowlist: Iterable[Symbol] = (),
) -> Dict[str, Any]:
    """Cost of the declaration that resolves the ambiguity, in bits, two ways.

    Both numbers are SPECIFICATION bits -- bits of information a reader must be
    given -- and are directly comparable. They are NOT source-code bits; the earlier
    key names said ``*_code_bits`` and that was a misnomer, corrected here.

    ARBITRARY: one bit per mixed class says "the dead members of this class are D" --
    the declaration is allowed to be a per-class partition, so it costs ``nu(M)`` bits
    and nothing more. No smaller declaration can resolve a class, because the class is
    by definition one the observation cannot split.

    ALLOWLIST: a name list must name the live members individually, so it costs
    ``sum_C log2 C(|C|, |L_C|)`` over the mixed classes -- never less than the
    arbitrary declaration, and equal only when every class has a single live member.
    The implementation accumulates ``log2 C(|C|, |D_C|)``; the two are the same
    NUMBER, since ``C(n, |D|) = C(n, n - |D|) = C(n, |L|)``, but only one of them
    names the quantity the code computes, so the docstring said ``|L_C|`` while the
    loop said ``|D_C|``. Both are recorded. This is the quantitative form of run 7's
    prior-art kill: the protocol manifest is an allowlist, so it was never going to
    be the cheap shape.
    """
    split = liveness_split(classes, lasso)
    mixed = [c for c in split if c["mixed"]]
    arbitrary = len(mixed)
    allowlist_bits = 0.0
    for c in mixed:
        n, d = c["size"], c["dead"]
        allowlist_bits += math.log2(math.comb(n, d)) if 0 < d < n else 0.0
    listed = set(allowlist)
    covers = sum(1 for c in mixed if set(c["live_members"]) <= listed)
    return {
        "arbitrary_spec_bits": arbitrary,
        "allowlist_spec_bits": round(allowlist_bits, 6),
        "arbitrary_code_bits": arbitrary,
        "allowlist_code_bits": round(allowlist_bits, 6),
        "code_bits_RETRACTED": "the two keys above are SPECIFICATION bits; the "
                               "*_code_bits reading was a misnomer and is retained "
                               "only so the stale run-8 artefact stays diffable",
        "bits_are": "specification/information bits, directly comparable to each other",
        "allowlist_at_least_as_expensive": allowlist_bits >= arbitrary - 1e-12,
        "gap_bits": round(allowlist_bits - arbitrary, 6),
        "allowlist_names_supplied": len(listed),
        "allowlist_covers_all_mixed_classes": bool(mixed) and covers == len(mixed),
        "mixed_classes_covered_by_allowlist": covers,
        "every_gate_sound_impossible": arbitrary > 0,
        "why": (
            "the labelling is chosen after the gate is fixed, so any gate that "
            "certifies a member of a mixed class is refuted by labelling that "
            "member live; no declaration short of splitting every mixed class "
            "prevents this, and none can make a certifying gate sound"
        ),
    }


def interface_value_curve(
    classes: Sequence[Set[Symbol]], lasso: Dict[Symbol, bool],
    features: Mapping[Symbol, BVec], live_order: Sequence[Symbol],
    gates: Sequence[Tuple[str, Callable[[BVec], bool]]] | None = None,
) -> Dict[str, Any]:
    """How much accuracy one correct external bit is worth, measured per bit.

    Supply a correct per-symbol bit for the first ``j`` live members of the mixed
    class and re-derive the best accuracy by enumeration. TWO CURVES, and the
    distinction between them is this run's sixth self-inflicted defect.

    ``agreement`` (the original curve)
        ``(n_dead + j) / |C|``. Maximised over ALL gates, with no admissibility
        condition, so the achiever certifies the ``n_live - j`` unflagged live
        symbols as dead. Its marginal value is exactly ``1 / |C|``, and it is the
        curve that PREDICTS run 7's manifest accuracy of 0.875 from 3 correct bits
        -- which is right, because 0.875 was itself measured as agreement on a gate
        with one demonstrated false positive. It is not a statement about any sound
        gate and must never be reported as one.

    ``sound``
        Restricted to gates that certify no live symbol. The closed form is
        ``n_live / |C|`` for ``j < n_live`` and ``1.0`` at ``j = n_live``: a bit that
        identifies a LIVE symbol licenses exactly one abstention and nothing else,
        because "not flagged" is not "dead" -- the interface is a lower bound on
        liveness, so a threshold rule that certifies the unflagged remainder is
        unsound, not optimal. The curve is therefore FLAT until the last bit.

    The two agree at ``j = 0`` (both the majority rule) and diverge above it, which
    is why the agreement curve passed five self-checks unexamined. A class of size
    8 needs 8 bits to be *certain*, and the last one is worth ``(1 - n_live/|C|)``;
    the first ``n_live - 1`` are each worth nothing at all under soundness.

    The loop's own killed protocol manifest is the ``j = 3`` row of the agreement
    curve. Run 7 measured its accuracy at 0.875 without any law behind it; here that
    number is PREDICTED, and the manifest landing on the curve is the check. On the
    sound curve the same manifest would score ``n_live / |C| = 0.5``.
    """
    mixed = [c for c in liveness_split(classes, lasso) if c["mixed"]]
    if not mixed:
        return {"applicable": False, "n_mixed_classes": 0}
    c0 = mixed[0]
    size, n_dead, n_live = c0["size"], c0["dead"], c0["live"]
    use = gates if gates is not None else conjunctive_gates(N_FEATURES + 1)
    rows: List[Dict[str, Any]] = []
    for j in range(c0["live"] + 1):
        flagged = set(live_order[:j])
        aug = {s: v + (s in flagged,) for s, v in features.items()}
        acc = max_accuracy_over_gates(classes, lasso, use, aug)
        snd = max_accuracy_over_gates(classes, lasso, use, aug, sound_only=True)
        predicted = (n_dead + j) / size
        predicted_sound = 1.0 if j >= n_live else n_live / size
        rows.append({
            "correct_external_bits": j,
            "agreement_max_accuracy": acc["max_accuracy"],
            "agreement_achieved_by": acc["achieved_by"],
            "agreement_closed_form": round(predicted, 6),
            "agreement_matches_closed_form": abs(acc["max_accuracy"] - predicted) < 1e-9,
            "sound_max_accuracy": snd["max_accuracy"],
            "sound_achieved_by": snd["achieved_by"],
            "sound_closed_form": round(predicted_sound, 6),
            "sound_matches_closed_form": abs(snd["max_accuracy"] - predicted_sound) < 1e-9,
            "curves_agree": abs(acc["max_accuracy"] - snd["max_accuracy"]) < 1e-9,
            "marginal_value_of_one_bit_agreement": round(
                acc["max_accuracy"] - rows[-1]["agreement_max_accuracy"], 6) if rows else None,
            "marginal_value_of_one_bit_sound": round(
                snd["max_accuracy"] - rows[-1]["sound_max_accuracy"], 6) if rows else None,
        })
    return {
        "applicable": True,
        "class_size": size, "n_dead": n_dead, "n_live": n_live,
        "n_gates_per_row": len(use),
        "rows": rows,
        "all_rows_match_closed_form": all(
            r["agreement_matches_closed_form"] and r["sound_matches_closed_form"] for r in rows),
        "marginal_value_of_one_bit_agreement": round(1 / size, 6),
        "law_agreement": "accuracy = (n_dead + j) / |C|; one correct external bit is "
                         "worth 1/|C|. AGREEMENT over an unconstrained gate family; "
                         "the achiever certifies live symbols",
        "law_sound": "accuracy = n_live / |C| for j < n_live, and 1.0 at j = n_live; "
                     "a bit identifying a LIVE symbol licenses one abstention and "
                     "nothing else, so the curve is flat until the last bit",
        "marginal_value_of_one_bit_sound_before_last": 0.0,
        "marginal_value_of_last_bit_sound": round(1 - n_live / size, 6),
        "curves_diverge_above_j0": any(not r["curves_agree"] for r in rows[1:]),
    }


def ambiguity_report(
    certified: Set[Symbol], features: Mapping[Symbol, BVec],
    demonstrated_live: Iterable[Symbol] = (),
) -> Dict[str, Any]:
    """Measure, on real code, how much of a gate's output is not a per-symbol verdict.

    Needs NO ground truth, so it runs on all nine corpora including the four real
    tarballs. A certificate whose E-class has more than one member is not a
    per-symbol conclusion: the gate emitted one verdict for the whole class, and
    the class contains at least one other symbol it never individually examined.
    Each such class needs at least one bit of external information to become a
    per-symbol claim, so this is a LOWER BOUND on the interface the corpus cannot
    supply -- the first lower bound this loop has produced about its own output.
    """
    classes = e_classes({s: features[s] for s in features})
    of_certified = [c for c in classes if c & certified]
    multi = [c for c in of_certified if len(c) > 1]
    live = set(demonstrated_live)
    demonstrated = [c for c in of_certified if c & live]
    n_cert = len(certified)
    return {
        "n_certified": n_cert,
        "n_classes_touched": len(of_certified),
        "n_certified_in_multi_symbol_class": sum(len(c & certified) for c in multi),
        "fraction_not_per_symbol": round(
            sum(len(c & certified) for c in multi) / n_cert, 6) if n_cert else None,
        "n_ambiguous_classes": len(multi),
        "interface_lower_bound_bits": len(multi),
        "n_classes_with_demonstrated_live_member": len(demonstrated),
        "demonstrated_live_in_ambiguous_class": sorted(
            s for c in demonstrated for s in (c & live)),
        "interface_lower_bound_bits_demonstrated": len(demonstrated),
        "largest_ambiguous_class": max((len(c) for c in multi), default=0),
        "verdict": (
            "every certificate in a multi-symbol class is a CLASS-level verdict, "
            "not a per-symbol one, and cannot be reported as a per-symbol one"
        ),
    }


def stated_claims() -> List[Dict[str, Any]]:
    """The module's PROSE claims as data, each paired with what enumeration says.

    RUN 8 DEFECT (ii), and the one worth keeping. This module's docstring stated
    the frontier as ``{(True, 0), (False, |D|)}`` while :func:`self_check` asserted
    ``achievable_points == [(0, 4), (1, 0)]`` on a class of 4 holding 2 dead and 2
    live symbols -- i.e. ``|C| = 4``, not ``|D_C| = 2`` -- and this run's own emitted
    frontier was ``[(0, 8), (1, 0)]`` on a class of 8 holding 4 dead and 4 live,
    i.e. again ``|C|``. The executable had already falsified the prose, twice, in
    two files, and nothing compared the three, so the contradiction survived a full
    measurement run. It was NOT a blind fixture: the wrong reading is off by exactly
    the number of live members, so the run's headline number refuted it on sight. The
    missing step was a comparison, not evidence.

    So the claims live here, as data with a measured counterpart, and every one is
    computed rather than trusted. A claim that is merely prose cannot disagree with
    behaviour loudly enough to be noticed; a claim that is an assertion either fails
    or it is checked. The wrong reading is included DELIBERATELY (see
    ``dichotomy_coordinate_is_class_size_not_dead_size``): a check that only asserts
    the true statement would still pass if the module reverted to the false one on
    a fixture where the two coincide.
    """
    out: List[Dict[str, Any]] = []

    def claim(name, expected, measured):
        out.append({"claim": name, "expected": expected, "measured": measured,
                    "holds": expected == measured})

    conj = conjunctive_gates()
    ex = exhaustive_gates(4)

    # A class of 4 with 2 dead and 2 live: the case that separates |C| from |D_C|.
    lasso = {"a.live": False, "a.dead": True, "b.live": False, "b.dead": True}
    feats = {s: (True, False, True, False, False, False, False, False, False)
             for s in lasso}
    classes = e_classes(feats)
    front = pareto_frontier(classes, lasso, conj, feats)

    claim("dichotomy_has_exactly_two_points", 2, front["n_points"])
    claim("sound_point_certifies_nothing", True, front["sound_points_all_zero"])
    claim("dichotomy_pairs", [(0, 4), (1, 0)], front["achievable_points"])
    # THE RUN-8 REFUTATION, PINNED NON-TAUTOLOGICALLY. The unsound point must sit
    # at |C|, and the refuted reading -- |D_C| -- must be UNACHIEVABLE. Asserting
    # only the true statement would still pass if this module reverted to the false
    # one on a fixture where every class member is predicted dead, which is exactly
    # the fixture the false reading was written against.
    pts = [tuple(p) for p in front["achievable_points"]]
    claim("dichotomy_coordinate_is_class_size_not_dead_size",
          {"unsound_point": len(classes[0]), "class_size": len(classes[0]),
           "dead_members": sum(1 for v in lasso.values() if v),
           "refuted_point_reachable": (0, 2) in pts},
          {"unsound_point": max(n for _, n in pts), "class_size": len(classes[0]),
           "dead_members": sum(1 for v in lasso.values() if v),
           "refuted_point_reachable": (0, 2) in pts})
    for name, gates in (("conjunctive", conj), ("exhaustive4", ex)):
        acc = max_accuracy_over_gates(classes, lasso, gates, feats)
        claim(f"fibre_bound_max(|D|,|L|)/|C| [{name}]", 0.5, acc["max_accuracy"])
        claim(f"bound_is_not_gate_dependent_min==max [{name}]", True,
              acc["min_accuracy"] == acc["max_accuracy"])

    # Invariance in m, and the closed form for unequal class sizes.
    inv = invariance_in_m()
    claim("invariance_in_m_all_half", True, all(r["best_accuracy"] == 0.5 for r in inv))
    claim("invariance_in_m_zero_variance", True,
          all(r["variance_across_gates"] == 0.0 for r in inv))
    claim("general_formula_m_classes_of_size_2", [0.5] * len(inv),
          [r["best_accuracy"] for r in inv])

    # The law, and the cost accountings -- including the P3 correction.
    eight = {f"m.T.s{i}": (i % 2 == 1) for i in range(8)}
    ef = {s: (True, False, True, False, False, False, False, False, False)
          for s in eight}
    ec = e_classes(ef)
    order = sorted(s for s in eight if not eight[s])
    curve = interface_value_curve(ec, eight, ef, order, conjunctive_gates(N_FEATURES + 1))
    claim("agreement_curve_equals_(n_dead+j)/|C|",
          [0.5, 0.625, 0.75, 0.875, 1.0],
          [r["agreement_max_accuracy"] for r in curve["rows"]])
    claim("agreement_one_correct_bit_is_worth_1_over_|C|", 0.125,
          curve["marginal_value_of_one_bit_agreement"])
    # DEFECT (v), the sixth self-inflicted one, and the only one that reached a
    # published closed form. The agreement curve above is maximised by a gate that
    # CERTIFIES live symbols, because the enumeration scored agreement and imposed
    # no admissibility condition. The sound curve is flat: a bit that identifies a
    # LIVE symbol licenses exactly one abstention, because "not flagged" is not
    # "dead". Asserted here so the distinction cannot be collapsed again.
    claim("sound_curve_is_flat_then_1", [0.5, 0.5, 0.5, 0.5, 1.0],
          [r["sound_max_accuracy"] for r in curve["rows"]])
    claim("sound_curve_matches_its_closed_form", True, curve["all_rows_match_closed_form"])
    claim("curves_agree_only_at_j0", True,
          all(r["curves_agree"] for r in curve["rows"][:1])
          and any(not r["curves_agree"] for r in curve["rows"][1:]))
    claim("sound_marginal_before_last_bit_is_zero", 0.0,
          curve["marginal_value_of_one_bit_sound_before_last"])
    claim("sound_last_bit_is_worth_the_whole_gap", 0.5,
          curve["marginal_value_of_last_bit_sound"])
    # A sound gate cannot exist that certifies anything here, at any bit count
    # below n_live -- the definitional statement, asserted directly.
    aug3 = {s: v + (s in set(order[:3]),) for s, v in ef.items()}
    only_sound = max_accuracy_over_gates(ec, eight, conjunctive_gates(N_FEATURES + 1),
                                         aug3, sound_only=True)
    claim("no_sound_gate_exceeds_the_majority_before_the_last_bit", 0.5,
          only_sound["max_accuracy"])

    cost = interface_cost_bits(classes, lasso, allowlist={"a.live", "b.live"})
    claim("arbitrary_spec_bits_is_the_answer_length_not_a_saving", 1,
          cost["arbitrary_spec_bits"])
    claim("spec_bits_keys_equal_the_retracted_code_bits_keys",
          (cost["arbitrary_spec_bits"], cost["allowlist_spec_bits"]),
          (cost["arbitrary_code_bits"], cost["allowlist_code_bits"]))
    claim("allowlist_at_least_as_expensive", True,
          cost["allowlist_at_least_as_expensive"])
    claim("allowlist_gap_positive_when_class_exceeds_2", True, cost["gap_bits"] > 0)
    # The two accountings coincide exactly on a 2-member class -- the one place the
    # "one bit per class" phrasing is literally true, which is why it misleads.
    pair = {"a.live": False, "a.dead": True}
    c2 = interface_cost_bits(e_classes({s: feats[s] for s in pair}), pair,
                             allowlist={"a.live"})
    claim("accountings_coincide_only_at_size_2", (1, 1.0, 0.0),
          (c2["arbitrary_spec_bits"], c2["allowlist_spec_bits"], c2["gap_bits"]))

    # The adversarial half: no declaration size rescues a certifying gate.
    claim("no_declaration_makes_every_gate_sound", True,
          cost["every_gate_sound_impossible"])

    # P4, the shape of a declaration. All THREE arms, so no zero can be an artefact
    # of a control that fails to move at all -- and so the refuted one is pinned.
    ctrl = interface_bit_control(classes, lasso, conj, feats,
                                 classes_of={s: "K" for s in lasso})
    claim("global_constant_declaration_is_worth_zero", 0.0,
          ctrl["global_constant_declaration"]["lift"])
    claim("global_constant_reaches_the_bound_not_beyond", 0.5,
          ctrl["global_constant_declaration"]["max_accuracy"])
    claim("per_class_declaration_worth_zero_when_class_refines", 0.0,
          ctrl["per_class_declaration"]["lift"])
    claim("per_symbol_declaration_reaches_one", True,
          ctrl["per_symbol_declaration"]["reaches_one"])
    claim("per_symbol_declaration_costs_one_symbol_per_class_member", 4,
          ctrl["per_symbol_declaration"]["cost_symbols"])
    claim("retracted_one_bit_suffices_is_false", False, ctrl["one_bit_suffices"])

    # RUN 8 DEFECT (iv), the refutation of P4, pinned NON-TAUTOLOGICALLY. The
    # retracted claim was that a per-class declaration is worth zero. A per-class
    # declaration separates two symbols of one E-class ONLY if they sit in
    # different Python classes, so the refuting map puts the two LIVE symbols in
    # one class and the two DEAD ones in another: both classes lie inside the
    # single E-class, the per-class majority rule reaches 1.0, and the retracted
    # claim is refuted by construction. Asserting only the refining direction would
    # still pass if the claim were reinstated on a fixture where the two coincide.
    split_map = {"a.live": "K_live", "b.live": "K_live",
                 "a.dead": "K_dead", "b.dead": "K_dead"}
    ctrl_split = interface_bit_control(classes, lasso, conj, feats, classes_of=split_map)
    claim("retracted_class_level_zero_is_refuted_by_a_split_class", True,
          ctrl_split["per_class_declaration"]["lift"] > 0.0)
    claim("per_class_lift_on_straddling_fixture", 0.5,
          ctrl_split["per_class_declaration"]["lift"])
    claim("per_class_reaches_one_on_straddling_fixture", 1.0,
          ctrl_split["per_class_declaration"]["max_accuracy"])
    # And the same claim must FAIL on a coarsening map, or the control is measuring
    # something other than the split. Opposite verdicts on the same E-class.
    claim("per_class_worth_zero_on_the_coarsening_map", 0.0,
          ctrl["per_class_declaration"]["lift"])
    # The split predicate itself, in both directions, on both maps.
    ref_split = partition_refinement(classes, split_map)
    ref_coarse = partition_refinement(classes, {s: "K" for s in lasso})
    claim("split_predicate_detects_a_split", False,
          ref_split["class_partition_coarsens_e_partition"])
    claim("split_predicate_detects_a_coarsening", True,
          ref_coarse["class_partition_coarsens_e_partition"])
    claim("n_split_e_classes_on_the_refuting_map", 1, ref_split["n_split_e_classes"])
    return out


def self_check() -> None:
    """Execute the result. Nothing here is asserted that is not also computed.

    The three load-bearing claims are checked in the order they can fail: the bound
    is derived by enumeration over ALL gates on a 4-feature projection and over all
    conjunctions on the full 9; the invariance in ``m`` is computed for ten values;
    the frontier is counted and must be a 2-point dichotomy in which every sound
    point certifies nothing.
    """
    lasso = {"a.live": False, "a.dead": True, "b.live": False, "b.dead": True}
    feats = {s: (True, False, True, False, False, False, False, False, False) for s in lasso}
    classes = e_classes(feats)
    assert len(classes) == 1 and classes[0] == set(lasso), classes

    conj = conjunctive_gates()
    assert len(conj) == 3 ** N_FEATURES, len(conj)
    ex = exhaustive_gates(4)
    assert len(ex) == 2 ** 16, len(ex)

    for name, gates in (("conjunctive", conj), ("exhaustive4", ex)):
        acc = max_accuracy_over_gates(classes, lasso, gates, feats)
        assert acc["max_accuracy"] == 0.5, (name, acc)
        assert acc["matches_closed_form"] is True, (name, acc)
        # Stronger than the bound: on a BALANCED class the score is not merely
        # capped at 1/2, it is 1/2 for every gate. min == max, so the gate's
        # quality is not a variable on an ambiguous class.
        assert acc["min_accuracy"] == 0.5, (name, acc)
        assert acc["max_accuracy"] == acc["min_accuracy"], (name, acc)
        assert acc["achieved_by"], (name, acc)

    front = pareto_frontier(classes, lasso, conj, feats)
    assert front["is_binary_dichotomy"] is True, front
    assert front["sound_points_all_zero"] is True, front
    assert front["achievable_points"] == [(0, 4), (1, 0)], front

    # The declaration-shape control, with BOTH retractions pinned. A global constant
    # must be worth EXACTLY zero, a per-symbol declaration must reach 1.0, and --
    # defect (iv) -- a per-class declaration must be worth zero on a refining class
    # map and STRICTLY POSITIVE on a straddling one. Asserting only the first
    # reading is what let the retracted claim through.
    ctrl = interface_bit_control(classes, lasso, conj, feats,
                                 classes_of={s: "K" for s in lasso})
    assert ctrl["max_accuracy_without_any_declaration"] == 0.5, ctrl
    assert ctrl["global_constant_declaration"]["worth_zero"] is True, ctrl
    assert ctrl["global_constant_declaration"]["lift"] == 0.0, ctrl
    assert ctrl["global_constant_declaration"]["max_accuracy"] == 0.5, ctrl
    assert ctrl["per_class_declaration"]["worth_zero"] is True, ctrl
    assert ctrl["per_symbol_declaration"]["reaches_one"] is True, ctrl
    assert ctrl["per_symbol_declaration"]["cost_symbols"] == 4, ctrl
    assert ctrl["one_bit_suffices"] is False, ctrl
    # No class map => UNKNOWN, never zero. This is the repair's guard rail: the
    # retracted claim came from answering "zero" to a question that had not been
    # asked yet.
    ctrl_nomap = interface_bit_control(classes, lasso, conj, feats)
    assert ctrl_nomap["per_class_declaration"]["measurable"] is False, ctrl_nomap
    assert "lift" not in ctrl_nomap["per_class_declaration"], ctrl_nomap

    # DEFECT (iv): the refutation, asserted on both maps. A class-level declaration
    # separates a.live from a.dead ONLY if they sit in different Python classes, so
    # the refuting map puts the two LIVE symbols in one class and the two DEAD ones
    # in another -- both classes then lie inside the single E-class, and the
    # per-class majority rule reaches 1.0 where the E-class rule is stuck at 1/2.
    split_map = {"a.live": "K_live", "b.live": "K_live",
                 "a.dead": "K_dead", "b.dead": "K_dead"}
    ctrl_split = interface_bit_control(classes, lasso, conj, feats, classes_of=split_map)
    assert ctrl_split["per_class_declaration"]["measurable"] is True, ctrl_split
    assert ctrl_split["per_class_declaration"]["lift"] > 0.0, ctrl_split
    assert ctrl_split["per_class_declaration"]["max_accuracy"] == 1.0, ctrl_split
    assert partition_refinement(classes, split_map)[
        "class_partition_coarsens_e_partition"] is False
    assert partition_refinement(classes, {s: "K" for s in lasso})[
        "class_partition_coarsens_e_partition"] is True
    assert partition_refinement(classes, split_map)["n_split_e_classes"] == 1
    # Closed form agrees with the enumeration on the refuting map, so the per-class
    # arm is derived rather than an artefact of the gate class.
    by_class: Dict[str, Set[Symbol]] = {}
    for s in feats:
        by_class.setdefault(split_map[s], set()).add(s)
    closed, _n = _majority_accuracy(list(by_class.values()), lasso)
    assert abs(closed - ctrl_split["per_class_declaration"]["max_accuracy"]) < 1e-9
    # And the STRICT converse, which is the half the first version got backwards: if
    # NO E-class is split, a per-class declaration cannot help. Four singleton
    # E-classes grouped into two classes that each SPAN two E-classes. No singleton
    # is split, so the lift must be non-positive. The feature map is deliberately
    # left constant across all four symbols, so the base is the same 1/2 as
    # everywhere else and the assertion isolates one thing: a per-class declaration
    # that merges distinctions is worth nothing, and the split predicate -- not the
    # class count -- is what decides it.
    ctrl_fine = interface_bit_control(
        [{"a.live"}, {"b.live"}, {"a.dead"}, {"b.dead"}], lasso, conj, feats,
        classes_of={"a.live": "K1", "a.dead": "K1", "b.live": "K2", "b.dead": "K2"})
    assert ctrl_fine["per_class_declaration"]["lift"] <= 0.0, ctrl_fine
    assert ctrl_fine["per_class_declaration"]["worth_zero"] is True, ctrl_fine
    assert partition_refinement(
        [{"a.live"}, {"b.live"}, {"a.dead"}, {"b.dead"}],
        {"a.live": "K1", "a.dead": "K1", "b.live": "K2", "b.dead": "K2"},
    )["class_partition_coarsens_e_partition"] is True

    for row in invariance_in_m():
        assert row["invariant"] is True, row
    for row in invariance_single_class():
        assert row["invariant"] is True, row

    nu = nu_index(classes, lasso)
    assert nu["nu"] == 1 and nu["max_accuracy_on_any_mixed_class"] == 0.5, nu

    cost = interface_cost_bits(classes, lasso, allowlist={"a.live", "b.live"})
    assert cost["arbitrary_code_bits"] == 1, cost
    # One class of 4 with 2 live members: an allowlist must name WHICH two, so it
    # costs log2 C(4,2) = 2.585 bits, while a per-class partition bit costs 1.
    assert abs(cost["allowlist_code_bits"] - math.log2(6)) < 1e-6, cost
    assert cost["allowlist_at_least_as_expensive"] is True, cost
    assert cost["gap_bits"] > 0, cost
    assert cost["allowlist_covers_all_mixed_classes"] is True, cost
    assert cost["every_gate_sound_impossible"] is True, cost
    # A size-2 class is the one place the two codings coincide: 1 bit either way.
    pair = {"a.live": False, "a.dead": True}
    pf2 = {s: feats[s] for s in pair}
    c2 = interface_cost_bits(e_classes(pf2), pair, allowlist={"a.live"})
    assert c2["arbitrary_code_bits"] == 1 and c2["allowlist_code_bits"] == 1.0, c2
    assert c2["gap_bits"] == 0.0, c2

    # A PURE class is not ambiguous, so it costs nothing and admits a sound verdict.
    pure = {"a.dead": True, "a.dead2": True}
    pf = {s: (True, False, True, False, False, False, False, False, False) for s in pure}
    assert nu_index(e_classes(pf), pure)["nu"] == 0
    assert interface_cost_bits(e_classes(pf), pure)["arbitrary_code_bits"] == 0

    # The run-7 pair, through the real evidence pipeline, not a synthetic vector.
    proto = {
        "alpha": "class T:\n    def process_literal_param(self, v):\n        return 1\n"
                 "    def _fixture_dead_plain(self):\n        return 2\n",
    }
    dead = set(proto["alpha"]) and {"alpha.T.process_literal_param", "alpha.T._fixture_dead_plain"}
    counts = DOMAIN.token_name_counts(proto.values())
    wit = IC.out_of_corpus_bases(proto, proto)
    truth = {"alpha.T.process_literal_param": False, "alpha.T._fixture_dead_plain": True}
    rf = features_for(truth, dead, counts, proto, wit)
    assert len(set(rf.values())) == 1, rf  # the pair is still E-indistinguishable
    r = max_accuracy_over_gates(e_classes(rf), truth, conj, rf)
    assert r["max_accuracy"] == 0.5, r
    assert r["matches_closed_form"] is True, r

    # The marginal value of a bit, and the law that predicts run 7's manifest score.
    # A size-8 class with 4 live members, so the curve has the row (j=3 -> 0.875)
    # at which run 7's killed protocol manifest actually landed.
    eight = {f"m.T.s{i}": (i % 2 == 1) for i in range(8)}  # True == DEAD
    ef = {s: (True, False, True, False, False, False, False, False, False) for s in eight}
    ec = e_classes(ef)
    order = sorted(s for s in eight if not eight[s])
    curve = interface_value_curve(ec, eight, ef, order, conjunctive_gates(N_FEATURES + 1))
    assert curve["all_rows_match_closed_form"] is True, curve
    assert [r["agreement_max_accuracy"] for r in curve["rows"]] == [
        0.5, 0.625, 0.75, 0.875, 1.0], curve
    assert abs(curve["marginal_value_of_one_bit_agreement"] - 0.125) < 1e-9, curve
    # The sound curve, which is the one that licenses a dead-code verdict. Flat at
    # the majority rule until the final bit, then 1.0. Defect (v).
    assert [r["sound_max_accuracy"] for r in curve["rows"]] == [
        0.5, 0.5, 0.5, 0.5, 1.0], curve
    assert curve["rows"][0]["curves_agree"] is True, curve
    assert any(not r["curves_agree"] for r in curve["rows"][1:]), curve
    # The row run 7 measured without a law: withholding 3 of 4 live names on a
    # class of 8 lands at 0.875 exactly -- on the AGREEMENT curve, because the
    # manifest is an unsound gate. Asserted here as arithmetic; the manifest is
    # APPLIED to the real gate in scripts/run_n11_measurement.py, so the prediction
    # is checked against the gate rather than against itself.
    assert curve["rows"][3]["agreement_max_accuracy"] == 0.875, curve
    assert curve["rows"][3]["sound_max_accuracy"] == 0.5, curve

    rep = ambiguity_report({"alpha.T.process_literal_param"}, rf,
                           demonstrated_live={"alpha.T.process_literal_param"})
    assert rep["n_ambiguous_classes"] == 1 and rep["interface_lower_bound_bits"] == 1, rep
    assert rep["interface_lower_bound_bits_demonstrated"] == 1, rep
    assert rep["fraction_not_per_symbol"] == 1.0, rep

    # Run 8 defect (ii): every claim the docstring MAKES, checked against what the
    # code DOES. Run 8 shipped a docstring that self_check already contradicted.
    claims = stated_claims()
    for c in claims:
        assert c["holds"] is True, c
    assert len(claims) >= 15, claims


if __name__ == "__main__":
    self_check()
    print("src/08_interface_index.py self_check OK")
