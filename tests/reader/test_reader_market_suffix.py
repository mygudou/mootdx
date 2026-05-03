from mootdx.reader import StdReader


def test_reader_find_path_uses_ss_suffix_for_sh_market():
    reader = StdReader.__new__(StdReader)
    reader.tdxdir = 'tests/fixtures'

    market, symbol, suffix = reader.find_path(symbol='000300.SS', suffix='day', debug=True)

    assert market == 'sh'
    assert symbol == 'sh000300'
    assert suffix == ['day']
