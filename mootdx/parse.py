import struct
from pathlib import Path

import pandas as pd
from tdxpy.reader import BlockReader

from mootdx.consts import TYPE_FLATS
from mootdx.consts import TYPE_GROUP
from mootdx.logger import logger


BLOCK_ALIASES = {
    'fg': 'block_fg.dat',
    'gn': 'block_gn.dat',
    'zs': 'block_zs.dat',
    'sb': 'sbblock.dat',
    'sp': 'spblock.dat',
    'hk': 'hkblock.dat',
    'jj': 'jjblock.dat',
    'mg': 'mgblock.dat',
    'uk': 'ukblock.dat',
}

CONTRACT_FILES = {
    'future': 'code2name.ini',
    'futures': 'code2name.ini',
    'option': 'code2name_qq.ini',
    'options': 'code2name_qq.ini',
}

CONTRACT_COLUMNS = [
    'code',
    'name',
    'exchange',
    'category',
    'main_contract',
    'main_contract_date',
    'contract_unit',
    'price_tick',
    'limit_up',
    'limit_down',
    'fee',
    'fee_unit',
    'unit',
    'rule_code',
    'rule_value',
    'description',
]

HQ_CACHE_ALIASES = {
    'concept': 'tdxbk.cfg',
    'concepts': 'tdxbk.cfg',
    'bk': 'tdxbk.cfg',
    'industry': 'tdxhy.cfg',
    'industries': 'tdxhy.cfg',
    'hy': 'tdxhy.cfg',
    'index': 'tdxzs.cfg',
    'indices': 'tdxzs.cfg',
    'zs': 'tdxzs.cfg',
    'index3': 'tdxzs3.cfg',
    'zs3': 'tdxzs3.cfg',
    'neeq_index': 'tdxsbzs.cfg',
    'sbzs': 'tdxsbzs.cfg',
    'hk_index': 'tdxdszs.cfg',
    'adr': 'tdxadr.cfg',
    'bse_more': 'tdxbjmore.cfg',
    'bj_more': 'tdxbjmore.cfg',
    'us_stock': 'tdxmgag.cfg',
    'mgag': 'tdxmgag.cfg',
}

HQ_CACHE_COLUMNS = {
    'tdxbk.cfg': ['category', 'name', 'full_name', 'flag'],
    'tdxhy.cfg': ['market', 'code', 'tdx_industry', 'reserved1', 'reserved2', 'sw_industry'],
    'tdxzs.cfg': ['name', 'code', 'category', 'type', 'market', 'alias'],
    'tdxzs3.cfg': ['name', 'code', 'category', 'type', 'market', 'alias'],
    'tdxdszs.cfg': ['name', 'code', 'market', 'category', 'type', 'alias'],
    'tdxsbzs.cfg': ['code', 'name'],
    'tdxadr.cfg': ['name', 'hk_code', 'adr_code', 'ratio'],
    'tdxbjmore.cfg': ['market', 'code', 'market_id', 'name', 'reserved'],
    'tdxmgag.cfg': ['code', 'name', 'industry', 'concept', 'reserved'],
}

TNF_HEADER_SIZE = 50
TNF_RECORD_SIZE = 314
TCU_RECORD_SIZE = 150

TCU_COLUMNS = [
    'market',
    'code',
    'name',
    'active1',
    'price',
    'open',
    'high',
    'low',
    'last_close',
    'vol',
    'amount_raw',
    'cur_vol',
    'raw9',
    'amount',
    's_vol',
    'b_vol',
    'raw13',
    'raw14',
    'bid1',
    'bid2',
    'bid3',
    'bid4',
    'bid5',
    'bid_vol1',
    'bid_vol2',
    'bid_vol3',
    'bid_vol4',
    'bid_vol5',
    'ask1',
    'ask2',
    'ask3',
    'ask4',
    'ask5',
    'ask_vol1',
    'ask_vol2',
    'ask_vol3',
    'ask_vol4',
    'ask_vol5',
    'raw35',
    'raw36',
    'raw_tail',
]


def _decode_cstr(data):
    return data.split(b'\x00', 1)[0].decode('gbk', 'ignore').strip()


def _read_gbk_csv(path, columns):
    rows = []
    maxsplit = len(columns) - 1

    for line in Path(path).read_text(encoding='gbk', errors='ignore').splitlines():
        if not line.strip():
            continue

        parts = [item.strip() for item in line.split(',', maxsplit)]
        parts.extend([''] * (len(columns) - len(parts)))
        rows.append(dict(zip(columns, parts[:len(columns)])))

    return pd.DataFrame(rows, columns=columns)


def _read_gbk_pipe(path, columns=None):
    rows = []

    for line in Path(path).read_text(encoding='gbk', errors='ignore').splitlines():
        if not line.strip():
            continue

        rows.append([item.strip() for item in line.split('|')])

    if not rows:
        return pd.DataFrame(columns=columns)

    width = max(len(row) for row in rows)
    for row in rows:
        row.extend([''] * (width - len(row)))

    if columns is None:
        columns = [f'col{i}' for i in range(width)]
    elif len(columns) < width:
        columns = columns + [f'col{i}' for i in range(len(columns), width)]

    return pd.DataFrame(rows, columns=columns[:width])


def _unpack_tcu_record(record):
    words = [record[i * 4:i * 4 + 4] for i in range(37)]
    uints = [struct.unpack('<I', item)[0] for item in words]
    floats = [struct.unpack('<f', item)[0] for item in words]
    tail = struct.unpack('<H', record[148:150])[0]

    return {
        'active1': uints[0],
        'price': floats[1],
        'open': floats[2],
        'high': floats[3],
        'low': floats[4],
        'last_close': floats[5],
        'vol': uints[6],
        'amount_raw': uints[7],
        'cur_vol': uints[8],
        'raw9': uints[9],
        'amount': floats[10],
        's_vol': uints[11],
        'b_vol': uints[12],
        'raw13': floats[13],
        'raw14': floats[14],
        'bid1': floats[15],
        'bid2': floats[16],
        'bid3': floats[17],
        'bid4': floats[18],
        'bid5': floats[19],
        'bid_vol1': uints[20],
        'bid_vol2': uints[21],
        'bid_vol3': uints[22],
        'bid_vol4': uints[23],
        'bid_vol5': uints[24],
        'ask1': floats[25],
        'ask2': floats[26],
        'ask3': floats[27],
        'ask4': floats[28],
        'ask5': floats[29],
        'ask_vol1': uints[30],
        'ask_vol2': uints[31],
        'ask_vol3': uints[32],
        'ask_vol4': uints[33],
        'ask_vol5': uints[34],
        'raw35': uints[35],
        'raw36': uints[36],
        'raw_tail': tail,
    }


class BaseParse:
    def __init__(self, tdxdir):  # noqa
        self.tdxdir = tdxdir  # noqa

    def block_files(self):
        """
        列出 T0002/hq_cache 下可解析的通达信板块文件

        :return: pd.DataFrame(columns=['name', 'filename', 'path'])
        """

        hq_cache = Path(self.tdxdir, 'T0002', 'hq_cache')
        rows = []

        for name, filename in BLOCK_ALIASES.items():
            path = hq_cache / filename

            if path.exists():
                rows.append({'name': name, 'filename': filename, 'path': str(path)})

        return pd.DataFrame(rows, columns=['name', 'filename', 'path'])

    def stock_list(self, market='all'):
        """
        读取通达信本地证券基础信息文件 shm.tnf、szm.tnf

        :param market: sh/sz/all，或市场列表
        :return: pd.DataFrame(columns=['market', 'code', 'name'])
        """

        hq_cache = Path(self.tdxdir, 'T0002', 'hq_cache')
        markets = ['sh', 'sz'] if market in [None, 'all'] else market
        markets = markets if isinstance(markets, (list, tuple, set)) else [markets]
        result = []

        for item in markets:
            item = str(item).lower()
            filename = hq_cache / f'{item}m.tnf'

            if not filename.exists():
                continue

            result.append(self.tnf(filename, market=item))

        if not result:
            return pd.DataFrame(columns=['market', 'code', 'name'])

        return pd.concat(result, ignore_index=True)

    def stock_search(self, keyword, market='all', exact=False):
        """
        从通达信本地证券基础信息中搜索代码或名称

        :param keyword: 代码或名称关键字
        :param market: sh/sz/all，或市场列表
        :param exact: 是否精确匹配代码或名称
        :return: pd.DataFrame
        """

        data = self.stock_list(market=market)

        if data.empty:
            return data

        keyword = str(keyword)

        if exact:
            return data[(data.code == keyword) | (data.name == keyword)].reset_index(drop=True)

        matched = data.code.str.contains(keyword, regex=False) | data.name.str.contains(
            keyword,
            regex=False,
        )
        return data[matched].reset_index(drop=True)

    def contracts(self, kind='future'):
        """
        读取通达信本地扩展市场合约规则文件 code2name.ini / code2name_qq.ini

        :param kind: future/futures 或 option/options，也可以直接传文件名
        :return: pd.DataFrame
        """

        filename = CONTRACT_FILES.get(str(kind).lower(), kind)
        path = Path(self.tdxdir, 'T0002', 'hq_cache', filename)

        if not path.exists():
            return pd.DataFrame(columns=CONTRACT_COLUMNS)

        return _read_gbk_csv(path, CONTRACT_COLUMNS)

    def hq_cache(self, name='concept', columns=None):
        """
        读取通达信 T0002/hq_cache 下常见文本配置文件

        :param name: concept/industry/index/adr 等别名，或完整文件名
        :param columns: 自定义列名；为空时对已知文件使用内置列名
        :return: pd.DataFrame
        """

        filename = HQ_CACHE_ALIASES.get(str(name).lower(), name)
        filename = filename if Path(filename).suffix else f'{filename}.cfg'
        path = Path(self.tdxdir, 'T0002', 'hq_cache', filename)

        if columns is None:
            columns = HQ_CACHE_COLUMNS.get(filename)

        if not path.exists():
            return pd.DataFrame(columns=columns)

        return _read_gbk_pipe(path, columns=columns)

    def quote_cache(self, market='all'):
        """
        读取通达信本地 sh.tcu / sz.tcu 行情快照缓存

        :param market: sh/sz/all，或市场列表
        :return: pd.DataFrame
        """

        markets = ['sh', 'sz'] if market in [None, 'all'] else market
        markets = markets if isinstance(markets, (list, tuple, set)) else [markets]
        result = []

        for item in markets:
            item = str(item).lower()
            tcu = Path(self.tdxdir, 'T0002', 'hq_cache', f'{item}.tcu')

            if not tcu.exists():
                continue

            stocks = self.stock_list(market=item)
            data = tcu.read_bytes()
            rows = []
            count = min(len(stocks), len(data) // TCU_RECORD_SIZE)

            for index in range(count):
                start = index * TCU_RECORD_SIZE
                record = data[start:start + TCU_RECORD_SIZE]
                stock = stocks.iloc[index]
                rows.append({
                    'market': stock['market'],
                    'code': stock['code'],
                    'name': stock['name'],
                    **_unpack_tcu_record(record),
                })

            result.append(pd.DataFrame(rows, columns=TCU_COLUMNS))

        if not result:
            return pd.DataFrame(columns=TCU_COLUMNS)

        return pd.concat(result, ignore_index=True)

    def tcu(self, market='all'):
        return self.quote_cache(market=market)

    def tnf(self, filename, market=None):
        """
        解析通达信 shm.tnf / szm.tnf 证券基础信息文件

        :param filename: tnf 文件路径
        :param market: sh/sz，默认从文件名推断
        :return: pd.DataFrame
        """

        path = Path(filename)
        market = market or path.stem[:2].lower()
        data = path.read_bytes()
        rows = []

        for offset in range(TNF_HEADER_SIZE, len(data), TNF_RECORD_SIZE):
            record = data[offset:offset + TNF_RECORD_SIZE]

            if len(record) < 64:
                continue

            code = _decode_cstr(record[0:6])
            name = _decode_cstr(record[23:63])

            if not code or not code.isdigit() or not name:
                continue

            rows.append({'market': market, 'code': code, 'name': name})

        return pd.DataFrame(rows, columns=['market', 'code', 'name']).drop_duplicates(
            ignore_index=True,
        )

    def blocks(self, name='gn', group=False):
        """
        按通达信常见别名读取板块

        :param name: gn/fg/zs/sb/sp/hk/jj/mg/uk，或完整文件名
        :param group: 是否分组返回
        :return: pd.DataFrame
        """

        symbol = BLOCK_ALIASES.get(str(name).lower(), name)
        return self.parse(symbol=symbol, group=group)

    def parse(self, symbol=None, group=False, **kwargs):  # noqa
        """
        获取板块数据

        参考: http://blog.sina.com.cn/s/blog_623d2d280102vt8y.html

        :param symbol:  板块文件
        :param group:   分组解析
        :return: pd.dataFrame or None
        """

        symbol = BLOCK_ALIASES.get(str(symbol).lower(), symbol)
        suffix = Path(symbol).suffix or '.dat'
        symbol = Path(symbol).stem

        vipdoc = (Path('T0002', 'hq_cache'), '')['incon' in symbol]  # noqa
        vipdoc = Path(vipdoc, f'{symbol}{suffix}')  # noqa

        if not Path(self.tdxdir, vipdoc).exists():
            logger.error(f'文件不存在: {vipdoc}')
            return None

        if 'incon' in symbol:  # noqa
            return self.__incon(vipdoc)

        if 'block_' in symbol and suffix == '.dat':
            return BlockReader().get_df(str(Path(self.tdxdir, vipdoc)), (TYPE_FLATS, TYPE_GROUP)[bool(group)])

        return self.cfg(vipdoc)

    def read_text(self, path):
        return Path(self.tdxdir, path).read_text(encoding='gbk').strip()

    def __incon(self, path):  # noqa
        t = self.read_text(path)
        m = [x for x in t.split('######')]
        v = [n.split() for n in m if n.strip()]

        d = {i[0]: [c.split('|') for c in i[1:]] for i in v}
        d = {key: dict([vv for vv in val if len(vv) == 2]) for key, val in d.items()}

        return d

    def cfg(self, path):
        ts = self.read_text(path)
        ls = [ll.split('|') for ll in ts.split()]

        return pd.DataFrame(ls)
