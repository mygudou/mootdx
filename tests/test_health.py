"""mootdx.health：四维探针 + 三态比价 + servertime 只当线索（不联网，全部打桩）。"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from mootdx import health


class _FakeApi:
    """可编程的 TdxHq_API 替身。"""

    connect_ok = True
    quotes = [{'code': '000001', 'price': 11.57}, {'code': '600519', 'price': 1258.62}, {'code': '510300', 'price': 4.43}]
    bars = [{'close': 1.0}]

    def __init__(self, **kwargs):
        pass

    def connect(self, host, port, time_out):
        return self.connect_ok

    def get_security_quotes(self, items):
        return list(self.quotes)

    def get_security_bars(self, *args):
        return list(self.bars)

    def disconnect(self):
        pass


@pytest.fixture
def fake_api(monkeypatch):
    monkeypatch.setattr(health, '_new_api', lambda: _FakeApi())
    _FakeApi.connect_ok = True
    _FakeApi.quotes = [{'code': '000001', 'price': 11.57}, {'code': '600519', 'price': 1258.62}, {'code': '510300', 'price': 4.43}]
    _FakeApi.bars = [{'close': 1.0}]
    return _FakeApi


def test_probe_passes_without_reference(fake_api):
    r = health.probe_host('10.0.0.1', 7709)
    assert r.ok and r.stage == 'ok' and r.price_check == 'skipped' and r.ms is not None


def test_probe_stages_fail_closed(fake_api):
    fake_api.connect_ok = False
    assert health.probe_host('10.0.0.1').stage == 'connect'
    fake_api.connect_ok = True
    fake_api.quotes = []
    r = health.probe_host('10.0.0.1')
    assert not r.ok and r.stage == 'quotes' and 'empty' in r.detail
    fake_api.quotes = _FakeApi.quotes = [{'code': '000001', 'price': 11.57}, {'code': '600519', 'price': 1258.62}]
    fake_api.bars = []
    r = health.probe_host('10.0.0.1')
    assert not r.ok and r.stage == 'bars'


def test_probe_price_check_is_three_state(fake_api):
    ref_ok = lambda codes: {'000001': 11.57, '600519': 1258.62, '510300': 4.43}
    ref_bad = lambda codes: {'000001': 11.30, '600519': 1240.0, '510300': 4.10}
    ref_none = lambda codes: {}
    assert health.probe_host('h', reference_prices=ref_ok).price_check == 'agree'
    bad = health.probe_host('h', reference_prices=ref_bad)
    assert not bad.ok and bad.stage == 'price' and bad.price_check == 'disagree'
    unv = health.probe_host('h', reference_prices=ref_none)
    assert unv.ok and unv.price_check == 'unverified'  # 无法判断 ≠ 价格错

    def boom(codes):
        raise RuntimeError('sina down')

    r = health.probe_host('h', reference_prices=boom)
    assert r.ok and r.price_check == 'unverified' and 'reference unavailable' in r.detail


def test_price_agreement_rules():
    ref = {'000001': 11.57, '600519': 1258.62, '510300': 4.20}
    assert health.price_agreement({'000001': 11.57, '600519': 1258.62, '510300': 4.20}, ref)[0] is True
    assert health.price_agreement({'000001': 11.59, '600519': 1256.6, '510300': 4.20}, ref)[0] is True
    assert health.price_agreement({'000001': 11.30, '600519': 1240.0, '510300': 4.20}, ref)[0] is False
    assert health.price_agreement({'000001': 11.57}, ref)[0] is None
    assert health.price_agreement({'000001': 11.57, '600519': 1258.62}, {})[0] is None


def test_servertime_is_only_a_hint():
    sh = lambda h, m, d='2026-09-30': datetime.fromisoformat(f'{d}T{h:02d}:{m:02d}:00').replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    f = health.servertime_looks_stale
    assert f(['14:43:28.434'], sh(14, 56))[0] is True
    assert f(['14:55:30.000'], sh(14, 56))[0] is False
    assert f(['14:52:27.260'], sh(15, 5))[0] is True
    assert f(['15:00:03.000'], sh(15, 5))[0] is False
    assert f(['15:00:03.000'], sh(10, 0, '2026-10-03'))[0] is False  # 周六
    assert f(['11:20:00.000'], sh(12, 0))[0] is True
    assert f(['15:00:03.000'], sh(9, 0))[0] is False
    assert f(['', None], sh(14, 0))[0] is False


def test_probe_hosts_dedupes_and_sorts(fake_api, monkeypatch):
    seen = []

    def fake_probe(addr, port=7709, **kw):
        seen.append((addr, port))
        r = health.HostProbe(addr, port)
        r.ok = addr != '10.0.0.3'
        r.ms = {'10.0.0.1': 200.0, '10.0.0.2': 50.0}.get(addr)
        return r

    monkeypatch.setattr(health, 'probe_host', fake_probe)
    out = health.probe_hosts([('10.0.0.1', 7709), ('10.0.0.2', 7709), ('10.0.0.1', 7709), ('10.0.0.3', 7709)])
    assert len(seen) == 3
    assert [r.addr for r in out] == ['10.0.0.2', '10.0.0.1', '10.0.0.3']


def test_new_hq_api_carries_the_handshake_shim():
    from mootdx.contrib.tdxpy_compat import new_hq_api
    from tdxpy.hq import TdxHq_API

    api = new_hq_api()
    assert isinstance(api, TdxHq_API)
    assert getattr(TdxHq_API, '_handshake_compat_no_cmd3', False) is True
