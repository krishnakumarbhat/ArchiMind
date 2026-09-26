def dispatch(reg):
    _wire()
    return reg['handler']()
def _wire():
    return globals()['_alpha_via_string']()
def _alpha_via_string():
    return 2
def _alpha_dead():
    return 1
