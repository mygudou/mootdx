from mootdx.consts import MARKET_BJ
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

    def get_history_minute_time_data(self, **kwargs):
        self.calls.append(('minutes', kwargs))
        return []

    def get_history_transaction_data(self, *args):
        self.calls.append(('transactions', args))
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


def test_quotes_uses_raw_command_so_bse_quotes_are_not_blocked():
    client = StdQuotes.__new__(StdQuotes)
    client._call_command = lambda command, symbols: [
        {'market': MARKET_BJ, 'code': '920493', 'price': 10.0},
    ]

    result = client.quotes('920493')

    assert result.to_dict('records') == [{'market': MARKET_BJ, 'code': '920493', 'price': 10.0}]


def test_minutes_accepts_explicit_market_override_for_indices():
    client = StdQuotes.__new__(StdQuotes)
    client.client = _FakeClient()

    client.minutes(symbol='000001', date='20260430', market=MARKET_SH)

    assert client.client.calls == [
        ('minutes', {'market': MARKET_SH, 'code': '000001', 'date': '20260430'}),
    ]


def test_minutes_allows_bse_market():
    client = StdQuotes.__new__(StdQuotes)
    client.client = _FakeClient()

    client.minutes(symbol='920493', date='20260430')

    assert client.client.calls == [
        ('minutes', {'market': MARKET_BJ, 'code': '920493', 'date': '20260430'}),
    ]


def test_transactions_allows_bse_market():
    client = StdQuotes.__new__(StdQuotes)
    client.client = _FakeClient()

    client.transactions(symbol='920493', start=1, offset=2, date='20260430')

    assert client.client.calls == [('transactions', (MARKET_BJ, '920493', 1, 2, 20260430))]


def test_company_info_content_reads_large_text_in_chunks():
    client = StdQuotes.__new__(StdQuotes)
    client.company_info_chunk_size = 5
    calls = []

    def call_command(command, market, code, filename, start, length):
        calls.append((start, length))
        return {
            10: 'abcde',
            15: 'wxyz',
        }[start]

    client._call_command = call_command

    result = client._company_info_content(MARKET_SH, '000858', '000858.txt', 10, 9)

    assert result == 'abcdewxyz'
    assert calls == [(10, 5), (15, 4)]
