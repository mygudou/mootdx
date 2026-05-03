from shutil import copyfile

from mootdx.reader import Reader
from mootdx.reader import StdReader


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
