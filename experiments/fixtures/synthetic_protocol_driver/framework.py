"""Stand-in for a framework that dispatches to user objects by name."""
PROTOCOL = (
    "process_bind_param",
    "process_result_value",
    "coerce_compared_value",
    "process_literal_param",
)
def drive(obj):
    reached = []
    for name in PROTOCOL:
        fn = getattr(obj, name, None)
        if fn is None:
            continue
        reached.append(fn(None))
    return reached
