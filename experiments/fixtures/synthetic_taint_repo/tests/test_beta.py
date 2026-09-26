from beta import _beta_live_from_test
def test_live():
    assert _beta_live_from_test() == 4
