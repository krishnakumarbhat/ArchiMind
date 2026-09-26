"""Every mechanism by which a REAL edge's callee name is absent from the caller.

Purpose
-------
Node N13 proposes a *non-executing* adjudicator for predicted call-graph edges: an
edge ``(caller, callee)`` is definitively FALSE if the callee's leaf name occurs
nowhere in the caller's own source tokens (NAME tokens and identifier-shaped STRING
tokens). Run 11 calls this the SPELLING CONDITION. It is supposed to shrink
``unadjudicable_edges`` on untrusted third-party code, where the dynamic oracle
cannot run.

The condition is refutable by ONE real edge whose callee name is not spelled. This
fixture is the refutation, written down: each witness is one escape mechanism, and
the loop's own ``sys.settrace`` oracle produces the executed truth.

Inputs
------
None. Importable with no dependencies beyond the standard library, and every witness
is reachable with the oracle's zero-argument dummy harness (all inputs are
module-level singletons, so no witness needs an argument).

Outputs
-------
One module-level callable per escape mechanism, named ``w<N>_*``. Nothing raises on
import or on a zero-argument call; each witness is a total function of its module
state so the oracle records dispatches rather than exceptions.

Mechanism index (the ground truth this file exists to pin down):

===== =========================== =================================================
W     mechanism                    escape is expected because
===== =========================== =================================================
W1    constructor dispatch         the caller spells ``Cls``; CPython invokes
                                   ``Cls.__init__`` directly
W2    context manager              ``with`` inserts ``__enter__``/``__exit__``
W3    iteration protocol           ``for`` inserts ``__iter__``/``__next__``
W4    ``__call__`` on an instance  the callee is the *type's* ``__call__``
W5    ``__getattr__``              attribute access on a missing name
W6    runtime-generated caller     ``@dataclass`` synthesises ``__init__`` in
                                   ``exec``'d code, so the caller has NO source
W7    name synthesised at runtime  the string is assembled, so the name is
                                   never a token
W8    operator overload            ``<`` becomes a ``__lt__`` call
W9    descriptor protocol          ``__set_name__`` at class creation,
                                   ``__get__`` on attribute read
===== =========================== =================================================
"""

import dataclasses
from typing import Any, Iterator

# --- W1: constructor dispatch -------------------------------------------------
# The caller's body spells `Plug`, never `__init__`. The CPG records the edge
# against `Plug.__init__` (see `src/00_cpg_static.py` self-check, line 433), so
# this is the escape that fires inside the loop's OWN instrument.


class Plug:
    def __init__(self) -> None:
        self.tag = "plug"

    def label(self) -> str:
        return self.tag


def w1_constructor() -> str:
    return Plug().label()


# --- W2: context manager -------------------------------------------------------


class Ctx:
    def __enter__(self) -> int:
        return 2

    def __exit__(self, *exc: Any) -> bool:
        return False


def w2_context() -> int:
    with Ctx() as value:
        return value


# --- W3: iteration protocol ----------------------------------------------------
# `__iter__` returns `self` so that `__next__` is dispatched on a PYTHON frame.
# Returning a list iterator would hand the edge to a C object and the caller's
# attribution would become ambiguous, which is a different question.


class Seq:
    def __iter__(self) -> Iterator[int]:
        return self

    def __next__(self) -> int:
        return 3


def w3_iteration() -> int:
    total = 0
    for item in Seq():
        total = total + item
    return total


# --- W4: __call__ on an instance ----------------------------------------------


class CallableObj:
    def __call__(self) -> int:
        return 4


_CALLABLE = CallableObj()


def w4_call() -> int:
    return _CALLABLE()


# --- W5: __getattr__ ------------------------------------------------------------


class Proxy:
    def __getattr__(self, name: str) -> int:
        return 5


_PROXY = Proxy()


def w5_getattr() -> int:
    return _PROXY.anything_at_all


# --- W6: runtime-generated caller ---------------------------------------------
# `@dataclass` synthesises `Rec.__init__` by exec'ing a template, so the real
# caller of `Rec.__post_init__` has no source text in this file at all. This is
# the escape that makes the condition UNEVALUABLE rather than merely false.


@dataclasses.dataclass
class Rec:
    field: int = 0

    def __post_init__(self) -> None:
        self.helper()

    def helper(self) -> int:
        return 6

    def use(self) -> int:
        return self.field


_REC = Rec()


def w6_generated_caller() -> int:
    return _REC.use()


# --- W7: name synthesised at runtime -------------------------------------------
# `load` is assembled from "lo" and "ad", so the name is never a token.


class Dyn:
    def load(self) -> int:
        return 7


_DYN = Dyn()


def w7_computed_name() -> int:
    return getattr(_DYN, "".join(["lo", "ad"]))()


# --- W8: operator overload ------------------------------------------------------


class Num:
    def __lt__(self, other: Any) -> bool:
        return True


_NUM = Num()


def w8_operator() -> bool:
    return _NUM < 1


# --- W9: descriptor protocol ----------------------------------------------------
# `__set_name__` is invoked by `type.__new__` while the class body executes, so its
# caller is the module, not a function; `__get__` is invoked by attribute access.


class Desc:
    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, obj: Any, owner: type = None) -> int:
        return 8


class Holder:
    slot = Desc()


def w9_descriptor() -> int:
    return Holder.slot


# --- negative control: a function the corpus really never dispatches -------------
# Written down so the fixture has a symbol on the dead side as well as nine live
# escape mechanisms. No witness calls it.


def never_called() -> int:
    return 99
