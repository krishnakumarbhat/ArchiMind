"""N11 fixture: one ambiguous class of eight, adjudicated by EXECUTION.

The point of this fixture is that the ambiguity is not a single lucky pair. Run 7's
discriminating pair had two members, and a two-member result invites the objection
that it is a small-sample artefact. Here one class holds FOUR dispatched methods and
FOUR undispatched ones, and all eight have the same in-corpus evidence by
construction: same class, no written base, no ``__all__``, no driver-owned path, no
name convention, and each leaf mentioned exactly once in the corpus.

The liveness labels are not written down by hand. ``framework.py`` lives outside the
corpus, reaches the object only through ``getattr`` over a protocol tuple it spells
itself, and each method returns a unique sentinel -- so the set of sentinels coming
back IS the set of methods actually dispatched. Truth is an execution result.

The four dead methods are named to collide with nothing and dispatched by nothing.
The driver deliberately names only the four live ones, which is also the point at
which an OPEN protocol manifest fails: a name the tuple omits is still reachable by
a real framework.
"""

PROTOCOL = (
    "process_bind_param",
    "process_result_value",
    "coerce_compared_value",
    "process_literal_param",
)


def drive(obj):
    """Dispatch to whatever the protocol tuple names. No knowledge of the class."""
    reached = []
    for name in PROTOCOL:
        fn = getattr(obj, name, None)
        if fn is None:
            continue
        reached.append(fn(None))
    return reached
