from mootdx.consts import MARKET_SH
from mootdx.quotes import StdQuotes


class _FakeClient:
    def __init__(self):
        self.calls = []

    def get_security_bars(self, *args):
        self.calls.append(('bars', args))
        return []

    def get_index_bars(self, *args):
        self.calls.append(('index', args))
        return []


def test_bars_strips_exchange_suffix_before_calling_tdx():
    client = StdQuotes.__new__(StdQuotes)
    client.client = _FakeClient()

    client.bars(symbol='000300.SS', frequency=9, start=1, offset=2)

    assert client.client.calls == [('bars', (9, MARKET_SH, '000300', 1, 2))]


def test_index_strips_exchange_suffix_and_uses_suffix_market():
    client = StdQuotes.__new__(StdQuotes)
    client.client = _FakeClient()

    client.index(symbol='000300.SS', frequency=9, start=1, offset=2)

    assert client.client.calls == [('index', (9, MARKET_SH, '000300', 1, 2))]
