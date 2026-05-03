from shutil import copyfile
from struct import calcsize
from struct import pack

from mootdx.reader import Reader
from mootdx.reader import StdReader
from mootdx.contrib.compat import MooTdxDailyBarReader


def test_reader_find_path_uses_ss_suffix_for_sh_market():
    reader = StdReader.__new__(StdReader)
    reader.tdxdir = 'tests/fixtures'

    market, symbol, suffix = reader.find_path(symbol='000300.SS', suffix='day', debug=True)

    assert market == 'sh'
    assert symbol == 'sh000300'
    assert suffix == ['day']


def test_reader_daily_supports_bse_vipdoc(tmp_path):
    source = 'tests/fixtures/vipdoc/sh/lday/sh688001.day'
    target = tmp_path / 'vipdoc' / 'bj' / 'lday' / 'bj920493.day'
    target.parent.mkdir(parents=True)
    copyfile(source, target)

    reader = Reader.factory(market='std', tdxdir=str(tmp_path))
    result = reader.daily(symbol='920493')

    assert not result.empty


def test_reader_uses_convertible_bond_volume_unit_for_sh_bonds():
    assert MooTdxDailyBarReader.SECURITY_COEFFICIENT['SH_BOND'] == [0.001, 0.1]


def test_reader_financial_reads_latest_local_cw_file(tmp_path):
    cwdir = tmp_path / 'vipdoc' / 'cw'
    cwdir.mkdir(parents=True)
    path = cwdir / 'gpsh0001.dat'
    header_format = '<3h1H3L'
    item_format = '<6s1c1L'
    header_size = calcsize(header_format)
    item_size = calcsize(item_format)
    first_offset = header_size + item_size

    path.write_bytes(
        pack(header_format, 0, 0, 0, 1, 0, 0, 0)
        + pack(item_format, b'600036', b'1', first_offset)
        + pack('<264f', *([3.0] + [0.0] * 263))
    )

    reader = Reader.factory(market='std', tdxdir=str(tmp_path))
    result = reader.financial(market='sh')

    assert result.loc['600036', 'col1'] == 3.0
