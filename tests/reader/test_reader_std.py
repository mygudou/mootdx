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


def test_contracts_reads_local_future_rules(reader):
    result = reader.contracts(kind='future')
    row = result[result.code == 'IF'].iloc[0]

    assert row[['code', 'name', 'exchange', 'contract_unit', 'price_tick', 'unit']].to_dict() == {
        'code': 'IF',
        'name': '沪深',
        'exchange': 'CZ',
        'contract_unit': '300',
        'price_tick': '0.2000',
        'unit': '元',
    }


def test_contracts_reads_local_option_rules(reader):
    result = reader.contracts(kind='option')
    row = result[result.code == 'C'].iloc[0]

    assert row[['code', 'name', 'exchange', 'contract_unit', 'price_tick', 'unit']].to_dict() == {
        'code': 'C',
        'name': '玉米',
        'exchange': 'OD',
        'contract_unit': '10',
        'price_tick': '0.5000',
        'unit': '吨',
    }


def test_hq_cache_reads_local_concept_catalog(reader):
    result = reader.hq_cache('concept')
    row = result.iloc[0]

    assert row.to_dict() == {
        'category': '1',
        'name': '有机硅',
        'full_name': '有机硅概念',
        'flag': '0',
    }


def test_hq_cache_reads_local_industry_catalog(reader):
    result = reader.hq_cache('industry')
    row = result[result.code == '000001'].iloc[0]

    assert row[['market', 'code', 'tdx_industry', 'sw_industry']].to_dict() == {
        'market': '0',
        'code': '000001',
        'tdx_industry': 'T1001',
        'sw_industry': 'X500102',
    }


def test_hq_cache_reads_local_adr_catalog(reader):
    result = reader.hq_cache('adr')
    row = result.iloc[0]

    assert row.to_dict() == {
        'name': '阿里巴巴-SW',
        'hk_code': '09988',
        'adr_code': 'BABA',
        'ratio': '8',
    }


def test_hq_cache_reads_local_code_group_catalog(reader):
    result = reader.hq_cache('code_group')
    row = result.iloc[0]

    assert row.to_dict() == {
        'group': 'QZ',
        'category': 'CY',
        'market': '0',
        'code': '000158',
    }


def test_hq_cache_reads_local_new_share_catalog(reader):
    result = reader.hq_cache('ipo')
    row = result.iloc[0]

    assert row[['market', 'code', 'apply_date', 'name', 'apply_limit2']].to_dict() == {
        'market': '0',
        'code': '301153',
        'apply_date': '20220506',
        'name': '中科江南',
        'apply_limit2': '0.65',
    }


def test_hq_config_reads_local_ini_style_config(reader):
    result = reader.hq_config('hqrule')
    row = result[(result.section == 'RULE') & (result.key == 'SHGTDayMax')].iloc[0]

    assert row.to_dict() == {
        'section': 'RULE',
        'key': 'SHGTDayMax',
        'value': '520',
    }


def test_hq_config_keeps_percent_encoded_values(reader):
    result = reader.hq_config('neednote')

    assert result[result.value.str.contains('%E6', regex=False)].empty is False


def test_option_codes_reads_local_sh_sz_option_files(reader):
    result = reader.option_codes(market='all')

    assert len(result) == 458
    assert result.iloc[0][['market', 'update_date', 'code', 'symbol', 'name']].to_dict() == {
        'market': 'sh',
        'update_date': '20220311',
        'code': '10003531',
        'symbol': '510050C3A02900',
        'name': '50ETF购3月2863A',
    }
    assert result[result.code == '90000735'].iloc[0][['market', 'name']].to_dict() == {
        'market': 'sz',
        'name': '沪深300ETF购3月4339A',
    }


def test_neeq_codes_reads_local_code_table(reader):
    result = reader.neeq_codes()
    row = result.iloc[0]

    assert row[['code', 'total_share', 'float_share', 'list_date', 'pinyin']].to_dict() == {
        'code': '400002',
        'total_share': '32450000',
        'float_share': '32450000',
        'list_date': '20010716',
        'pinyin': 'NBCN',
    }


def test_quote_cache_reads_local_tcu_snapshot(reader):
    result = reader.quote_cache(market='sh')
    row = result[result.code == '600036'].iloc[0]

    assert row[['market', 'code', 'name']].to_dict() == {
        'market': 'sh',
        'code': '600036',
        'name': '招商银行',
    }
    assert row.price == pytest.approx(38.83)
    assert row.open == pytest.approx(38.86)
    assert row.high == pytest.approx(39.16)
    assert row.low == pytest.approx(37.60)
    assert row.last_close == pytest.approx(38.41)
    assert row.vol == 150004
    assert row.amount == pytest.approx(5605383168.0)
    assert row.bid1 == pytest.approx(38.41)
    assert row.bid_vol1 == 79
    assert row.ask1 == pytest.approx(38.42)
    assert row.ask_vol1 == 1117


def test_tcu_alias_reads_local_quote_cache(reader):
    result = reader.tcu(market='sz')
    row = result.iloc[0]

    assert row[['market', 'code', 'name']].to_dict() == {
        'market': 'sz',
        'code': '395001',
        'name': '主板Ａ股',
    }
    assert row.price == pytest.approx(1484.0)
