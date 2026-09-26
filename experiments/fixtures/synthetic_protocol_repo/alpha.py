class T:
    def process_bind_param(self, value):
        return "alpha.T.process_bind_param"
    def process_result_value(self, value):
        return "alpha.T.process_result_value"
    def coerce_compared_value(self, value):
        return "alpha.T.coerce_compared_value"
    def process_literal_param(self, value):
        return "alpha.T.process_literal_param"
def _fixture_dead_plain():
    return 1
