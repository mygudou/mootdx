import pandas

from mootdx.consts import MARKET_BJ
from mootdx.consts import MARKET_SH
from mootdx.consts import MARKET_SZ
from mootdx.quotes import GetHistoryTransactionDataWithNum
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


def test_quotes_accepts_preparsed_market_code_pairs():
    client = StdQuotes.__new__(StdQuotes)
    calls = []

    def call_command(command, symbols):
        calls.append(symbols)
        return [{'market': MARKET_SH, 'code': '600036', 'price': 1.0}]

    client._call_command = call_command

    result = client.quotes([(MARKET_SH, '600036')])

    assert calls == [[[MARKET_SH, '600036']]]
    assert result.to_dict('records') == [{'market': MARKET_SH, 'code': '600036', 'price': 1.0}]


def test_quotes_batch_splits_large_requests():
    client = StdQuotes.__new__(StdQuotes)
    calls = []

    def call_command(command, symbols):
        calls.append(symbols)
        return [{'market': market, 'code': code, 'price': 1.0} for market, code in symbols]

    client._call_command = call_command

    result = client.quotes_batch(['600036', '000001', '920493'], batch_size=2)

    assert calls == [
        [[MARKET_SH, '600036'], [MARKET_SZ, '000001']],
        [[MARKET_BJ, '920493']],
    ]
    assert result.code.tolist() == ['600036', '000001', '920493']


def test_quotes_all_uses_stock_lists_and_batches_quotes():
    client = StdQuotes.__new__(StdQuotes)
    calls = []

    def stocks(market):
        return pandas.DataFrame({'code': ['000001'] if market == MARKET_SZ else ['600036']})

    def quotes_batch(symbol, batch_size=80, **kwargs):
        calls.append((symbol, batch_size))
        return pandas.DataFrame(symbol, columns=['market', 'code'])

    client.stocks = stocks
    client.quotes_batch = quotes_batch

    result = StdQuotes.quotes_all(client, batch_size=10)

    assert calls == [([[MARKET_SZ, '000001'], [MARKET_SH, '600036']], 10)]
    assert result.to_dict('records') == [
        {'market': MARKET_SZ, 'code': '000001'},
        {'market': MARKET_SH, 'code': '600036'},
    ]


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
    calls = []
    client._call_command = lambda command, *args: calls.append((command, args)) or []

    client.transactions(symbol='920493', start=1, offset=2, date='20260430')

    assert calls == [(GetHistoryTransactionDataWithNum, (MARKET_BJ, '920493', 1, 2, 20260430))]


def test_transactions_can_use_legacy_protocol_without_num():
    client = StdQuotes.__new__(StdQuotes)
    client.client = _FakeClient()

    client.transactions(symbol='920493', start=1, offset=2, date='20260430', with_num=False)

    assert client.client.calls == [('transactions', (MARKET_BJ, '920493', 1, 2, 20260430))]


def test_transactions_all_pages_until_short_chunk():
    client = StdQuotes.__new__(StdQuotes)
    calls = []

    def transactions(**kwargs):
        calls.append(kwargs['start'])
        if kwargs['start'] == 0:
            return pandas.DataFrame([{'time': '14:59'}])
        if kwargs['start'] == 1:
            return pandas.DataFrame([{'time': '14:58'}])
        return pandas.DataFrame()

    client.transactions = transactions

    result = StdQuotes.transactions_all(client, symbol='000001', date='20260430', offset=1)

    assert calls == [0, 1, 2]
    assert result.time.tolist() == ['14:58', '14:59']


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


# --- Regression tests for Bug 1: ValueError tolerance in batch APIs ---

def test_quotes_batch_tolerates_valueerror_from_tdxpy():
    """Bug 1 regression: per-symbol ValueError from tdxpy must not crash quotes_batch."""
    client = StdQuotes.__new__(StdQuotes)

    def call_command_raises(command, symbols):
        raise ValueError("invalid literal for int() with base 10: ''")

    client._call_command = call_command_raises

    result = client.quotes_batch(['600519', '000001'])

    assert result.empty, "Expected empty DataFrame when all batches raise ValueError"


def test_quotes_all_tolerates_valueerror_from_tdxpy():
    """Bug 1 regression: ValueError in inner quotes() must not crash quotes_all."""
    client = StdQuotes.__new__(StdQuotes)

    def stocks(market):
        return pandas.DataFrame({'code': ['000001'] if market == MARKET_SZ else ['600519']})

    def call_command_raises(command, symbols):
        raise ValueError("invalid literal for int() with base 10: ''")

    client.stocks = stocks
    client._call_command = call_command_raises

    result = client.quotes_all()

    assert result.empty, "Expected empty DataFrame when all batches raise ValueError"


# --- Regression tests for Bug 2: symbols= kwarg alias ---

def test_quotes_batch_accepts_symbols_kwarg():
    """Bug 2 regression: quotes_batch(symbols=[...]) must work, not silently return empty."""
    client = StdQuotes.__new__(StdQuotes)

    def call_command(command, symbols):
        return [{'market': market, 'code': code, 'price': 1.0} for market, code in symbols]

    client._call_command = call_command

    result = client.quotes_batch(symbols=['600519', '000001'])

    assert not result.empty, "Expected non-empty DataFrame when symbols= kwarg is used"
    assert set(result.code.tolist()) == {'600519', '000001'}


def test_quotes_batch_symbol_kwarg_still_works():
    """Bug 2 backward compat: quotes_batch(symbol=[...]) must still work."""
    client = StdQuotes.__new__(StdQuotes)

    def call_command(command, symbols):
        return [{'market': market, 'code': code, 'price': 1.0} for market, code in symbols]

    client._call_command = call_command

    result = client.quotes_batch(symbol=['600519', '000001'])

    assert not result.empty, "Expected non-empty DataFrame when legacy symbol= kwarg is used"
    assert set(result.code.tolist()) == {'600519', '000001'}


def test_quotes_batch_symbols_takes_priority_over_symbol():
    """Bug 2: when both symbol= and symbols= are provided, symbols= wins."""
    client = StdQuotes.__new__(StdQuotes)

    def call_command(command, symbols):
        return [{'market': market, 'code': code, 'price': 1.0} for market, code in symbols]

    client._call_command = call_command

    result = client.quotes_batch(symbol=['000001'], symbols=['600519'])

    assert result.code.tolist() == ['600519'], "symbols= should take priority over symbol="
