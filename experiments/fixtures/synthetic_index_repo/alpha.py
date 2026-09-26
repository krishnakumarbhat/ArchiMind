class T:
    """No base, no __all__, occ == 1 throughout."""

    def process_bind_param(self, value):
        return "alpha.T.process_bind_param"

    def process_result_value(self, value):
        return "alpha.T.process_result_value"

    def coerce_compared_value(self, value):
        return "alpha.T.coerce_compared_value"

    def process_literal_param(self, value):
        return "alpha.T.process_literal_param"

    def _dead_never_dispatched_one(self, value):
        return "alpha.T._dead_never_dispatched_one"

    def _dead_never_dispatched_two(self, value):
        return "alpha.T._dead_never_dispatched_two"

    def _dead_never_dispatched_three(self, value):
        return "alpha.T._dead_never_dispatched_three"

    def _dead_never_dispatched_four(self, value):
        return "alpha.T._dead_never_dispatched_four"
