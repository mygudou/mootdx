"""
Regression tests for BaseFinancial.__init__ config-resolution path.

Bug 3: When BESTIP.GP is an empty string (key present but value falsy),
       the old code `config.get('BESTIP').get('GP', default)` returned ''
       because the key existed.  The fix uses `... or default` so the
       empty-string value is treated as absent and the SERVER.GP fallback
       is used instead.
"""

from unittest.mock import MagicMock, patch

from mootdx.financial.base import BaseFinancial


def _make_config(bestip_gp='', server_gp_ip='120.76.152.87', server_gp_port=7709):
    """Return a mock config.get() that mirrors the real structure."""

    def _config_get(key):
        mock = MagicMock()
        if key == 'BESTIP':
            mock.get.return_value = bestip_gp
        elif key == 'SERVER':
            server_mock = MagicMock()
            server_mock.get.return_value = [['默认', server_gp_ip, server_gp_port]]
            return server_mock
        return mock

    return _config_get


def test_bestip_falls_back_to_server_gp_when_bestip_gp_is_empty_string():
    """Bug 3 regression: empty BESTIP.GP must use SERVER.GP as fallback."""
    with patch('mootdx.financial.base.config') as mock_config:
        mock_config.setup.return_value = None
        mock_config.get.side_effect = _make_config(bestip_gp='')

        obj = BaseFinancial.__new__(BaseFinancial)
        BaseFinancial.__init__(obj)

    assert obj.bestip == ['120.76.152.87', 7709], (
        f"Expected SERVER.GP fallback, got {obj.bestip!r}"
    )


def test_bestip_uses_configured_value_when_bestip_gp_is_set():
    """When BESTIP.GP is a valid (ip, port) tuple/list, it must be used as-is."""
    expected = ('10.0.0.1', 7709)

    with patch('mootdx.financial.base.config') as mock_config:
        mock_config.setup.return_value = None
        mock_config.get.side_effect = _make_config(bestip_gp=expected)

        obj = BaseFinancial.__new__(BaseFinancial)
        BaseFinancial.__init__(obj)

    assert obj.bestip == expected, f"Expected configured IP, got {obj.bestip!r}"


def test_bestip_falls_back_to_hardcoded_gp_on_value_error():
    """If SERVER.GP is also broken, the hardcoded GP fallback is used."""
    def bad_config_get(key):
        mock = MagicMock()
        if key == 'BESTIP':
            mock.get.return_value = ''
        elif key == 'SERVER':
            server_mock = MagicMock()
            server_mock.get.side_effect = ValueError('no GP servers configured')
            return server_mock
        return mock

    with patch('mootdx.financial.base.config') as mock_config:
        mock_config.setup.return_value = None
        mock_config.get.side_effect = bad_config_get

        obj = BaseFinancial.__new__(BaseFinancial)
        BaseFinancial.__init__(obj)

    # Must be a valid (ip, port)-like value, not an empty string
    assert obj.bestip, f"Expected a non-empty bestip, got {obj.bestip!r}"
    assert obj.bestip != '', "bestip must not be empty string after ValueError"
