import pytest

from mootdx.reader import Reader
from tests.conftest import is_empty


@pytest.fixture()
def reader():
    return Reader.factory(market='std', tdxdir='tests/fixtures')


@pytest.mark.parametrize(
    'symbol,adjust,empty', [
        ('127021', '', False),
        ('000000', '', True),
        ('sh881478', '', False),
        ('881478', '', False),
        ('688001', 'qfq', False),
        ('000001', 'qfq', False),
        ('127021', 'qfq', False),
    ])
def test_daily(reader, symbol, adjust, empty):
    result = reader.daily(symbol=symbol, adjust=adjust)
    assert is_empty(result) is empty


@pytest.mark.parametrize(
    'symbol,adjust,empty', [
        ('688001', 'qfq', False),
        ('000001', 'qfq', False),
        ('127021', 'qfq', False),
    ])
def test_daily_qfq(reader, symbol, adjust, empty):
    result = reader.daily(symbol=symbol, adjust=adjust)
    assert is_empty(result) is empty


@pytest.mark.parametrize(
    'symbol,adjust,empty', [
        ('688001', '02', False),
        ('000001', 'hfq', False),
        ('127021', 'hfq', False),
    ])
def test_daily_hfq(reader, symbol, adjust, empty):
    result = reader.daily(symbol=symbol, adjust=adjust)
    assert is_empty(result) is empty


@pytest.mark.parametrize('symbol', ['688001', '688001.5', '688001.loc1'])
def test_minute(reader, symbol):
    for suffix in ('1', '5'):
        result = reader.minute(symbol=symbol, suffix=suffix)
        assert not result.empty


def test_blocks_reads_common_tdx_alias(reader):
    result = reader.blocks(name='gn', group=True)

    assert result.empty is False
    assert {'blockname', 'stock_count', 'code_list'}.issubset(result.columns)


def test_block_files_lists_available_hq_cache_blocks(reader):
    result = reader.block_files()

    assert 'block_gn.dat' in result.filename.tolist()
    assert 'gn' in result.name.tolist()


def test_stock_list_reads_tnf_security_names(reader):
    result = reader.stock_list(market='sz')
    row = result[result.code == '000001'].iloc[0]

    assert row.to_dict() == {'market': 'sz', 'code': '000001', 'name': '平安银行'}


def test_stock_search_reads_tnf_by_code(reader):
    result = reader.stock_search('600036', market='sh', exact=True)

    assert result[['market', 'code', 'name']].to_dict('records') == [
        {'market': 'sh', 'code': '600036', 'name': '招商银行'},
    ]


def test_stock_search_reads_tnf_by_name(reader):
    result = reader.stock_search('招商银行', market='sh')

    assert {'market': 'sh', 'code': '600036', 'name': '招商银行'} in (
        result[['market', 'code', 'name']].to_dict('records')
    )
