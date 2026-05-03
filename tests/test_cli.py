from mootdx.__main__ import _frequency_from_action


def test_frequency_from_action_maps_common_tdx_periods():
    assert _frequency_from_action('daily') == 9
    assert _frequency_from_action('day') == 9
    assert _frequency_from_action('minute') == 8
    assert _frequency_from_action('1min') == 8
    assert _frequency_from_action('fzline') == 0
    assert _frequency_from_action('5min') == 0
