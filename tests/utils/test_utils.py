import unittest
from unittest import mock

import pytest

from mootdx import config
from mootdx.consts import MARKET_BJ
from mootdx.consts import MARKET_SH
from mootdx.consts import MARKET_SZ
from mootdx.utils import get_config_path
from mootdx.utils import get_stock_market
from mootdx.utils import get_stock_markets
from mootdx.utils import md5sum
from mootdx.utils import normalize_stock_code
from mootdx.utils import to_data

data = [
    ('600036', MARKET_SH),
    ('000001', MARKET_SZ),
    ('430090', MARKET_BJ),
    ('872925', MARKET_BJ),
    ('920493', MARKET_BJ),
    ('bj920493', MARKET_BJ),
    ('BJ920493', MARKET_BJ),
    ('920493.BJ', MARKET_BJ),
    ('000300.SS', MARKET_SH),
    ('000300.SH', MARKET_SH),
    ('000001.SZ', MARKET_SZ),
    ('900901', MARKET_SH),
]


@pytest.mark.parametrize('symbol,market', data)
def test_stock_market(symbol, market):
    assert get_stock_market(symbol) == market


def test_normalize_stock_code_strips_supported_exchange_prefixes():
    assert normalize_stock_code('sh600036') == '600036'
    assert normalize_stock_code('SZ000001') == '000001'
    assert normalize_stock_code('bj920493') == '920493'
    assert normalize_stock_code('000300.SS') == '000300'
    assert normalize_stock_code('920493.BJ') == '920493'


def test_get_stock_markets_uses_bse_market_for_920_codes():
    assert get_stock_markets(['920493', 'bj920493', '920493.BJ']) == [
        [MARKET_BJ, '920493'],
        [MARKET_BJ, '920493'],
        [MARKET_BJ, '920493'],
    ]


def test_get_stock_markets_uses_suffix_before_code_prefix():
    assert get_stock_markets(['000300.SS', '000001.SZ']) == [
        [MARKET_SH, '000300'],
        [MARKET_SZ, '000001'],
    ]


def test_get_server_ignores_empty_bestip(monkeypatch):
    monkeypatch.setitem(config.settings, 'BESTIP', {'HQ': ''})
    monkeypatch.setitem(config.settings, 'SERVER', {'HQ': [('默认行情', '1.1.1.1', 7709)]})

    assert config.get_server('HQ', default=('1.1.1.1', 7709)) == ('1.1.1.1', 7709)


def test_get_servers_prefers_maintained_builtin_servers_before_stale_config(monkeypatch):
    monkeypatch.setitem(config.settings, 'BESTIP', {'HQ': ''})
    monkeypatch.setitem(config.settings, 'SERVER', {'HQ': [('旧行情', '1.1.1.1', 7709)]})

    assert config.get_servers('HQ')[0] == ('180.153.18.170', 7709)


def test_set_bestip_preserves_other_markets(monkeypatch):
    monkeypatch.setitem(config.settings, 'BESTIP', {'HQ': '', 'EX': ('2.2.2.2', 7720)})

    config.set_bestip('HQ', ('1.1.1.1', 7709))

    assert config.settings['BESTIP'] == {
        'HQ': ('1.1.1.1', 7709),
        'EX': ('2.2.2.2', 7720),
    }


class TestMd5sum(unittest.TestCase):
    def test_md5sum_error(self):
        self.assertIsNone(md5sum('/ad/sd/sd'))

    def test_md5sum_success(self):
        self.assertIsNotNone(md5sum('./README.md'))


class TestToData(unittest.TestCase):
    def test_to_data_list(self):
        self.assertTrue(not to_data([{'aa': 'aa'}]).empty)

    def test_to_data_dict(self):
        self.assertTrue(not to_data({'abc': 123}).empty)

    def test_to_data_empty(self):
        self.assertTrue(to_data(None).empty)
        self.assertTrue(to_data({}).empty)
        self.assertTrue(to_data([]).empty)
        self.assertTrue(to_data('aaa').empty)
        self.assertTrue(to_data(123).empty)

    def test_to_data_drops_invalid_datetime_rows(self):
        result = to_data([
            {'datetime': '2026-04-30 15:00:00', 'close': 1},
            {'datetime': '0-00-00 15:00', 'close': 2},
        ])

        self.assertEqual(result.close.tolist(), [1])


class TestConfigPath(unittest.TestCase):
    @mock.patch('platform.system')
    def test_platform_windows(self, platform_system):
        platform_system.return_value = 'Windows'
        config = get_config_path(config='config.json')
        self.assertTrue('.mootdx' in config, config)

    @mock.patch('platform.system')
    def test_platform_linux(self, platform_system):
        platform_system.return_value = 'Linux'
        config = get_config_path(config='config.json')
        self.assertTrue('.mootdx' in config, config)

    @mock.patch('platform.system')
    def test_platform_Darwin(self, platform_system):
        platform_system.return_value = 'Darwin'
        config = get_config_path(config='config.json')
        self.assertTrue('.mootdx' in config, config)


if __name__ == '__main__':
    unittest.main()
