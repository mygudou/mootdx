from abc import ABC
from pathlib import Path

from tdxpy.reader import TdxExHqDailyBarReader
from tdxpy.reader import TdxLCMinBarReader
from tdxpy.reader import TdxMinBarReader

from mootdx.contrib.compat import MooTdxDailyBarReader
from mootdx.utils import get_stock_market
from mootdx.utils import normalize_stock_code
from mootdx.utils import to_data


class Reader(object):
    @staticmethod
    def factory(market='std', **kwargs):
        """
        Reader 工厂方法

        :param market: std 标准市场, ext 扩展市场
        :param kwargs: 可变参数
        :return:
        """

        if market == 'ext':
            return ExtReader(**kwargs)

        return StdReader(**kwargs)


class ReaderBase(ABC):
    # 默认通达信安装目录
    tdxdir = 'C:/new_tdx'

    def __init__(self, tdxdir=None):
        """
        构造函数

        :param tdxdir: 通达信安装目录
        """

        if not Path(tdxdir).is_dir():
            raise Exception('tdxdir 目录不存在')

        self.tdxdir = tdxdir

    def find_path(self, symbol=None, subdir='lday', suffix=None, **kwargs):
        """
        自动匹配文件路径，辅助函数

        :param symbol:
        :param subdir:
        :param suffix:
        :return: pd.dataFrame or None
        """

        raw_symbol = str(symbol or '')
        code = normalize_stock_code(raw_symbol)

        # 判断市场, 带#扩展市场
        if '#' in raw_symbol:
            market = 'ds'
        # 通达信特有的板块指数88****开头的日线数据放在 sh 文件夹下
        elif code.startswith('88'):
            market = 'sh'
        else:
            # 判断是sh还是sz
            market = get_stock_market(raw_symbol, True)

        # 判断前缀(市场是sh和sz重置前缀)
        if market.lower() in ['sh', 'sz', 'bj']:
            symbol = market + code
        else:
            symbol = raw_symbol

        # 判断后缀
        suffix = suffix if isinstance(suffix, list) else [suffix]

        # 调试使用
        if kwargs.get('debug'):
            return market, symbol, suffix

        # 遍历扩展名
        for ex_ in suffix:
            ex_ = ex_.strip('.')
            vipdoc = Path(self.tdxdir) / 'vipdoc' / market / subdir / f'{symbol}.{ex_}'

            if Path(vipdoc).exists():
                return vipdoc

        return None


class StdReader(ReaderBase):
    """股票市场"""

    def daily(self, symbol=None, **kwargs):
        """
        获取日线数据

        :param symbol: 证券代码
        :return: pd.dataFrame or None
        """
        code = normalize_stock_code(symbol)
        reader = MooTdxDailyBarReader()
        vipdoc = self.find_path(symbol=symbol, subdir='lday', suffix='day')

        result = reader.get_df(str(vipdoc)) if vipdoc else None
        return to_data(result, symbol=code, **kwargs)

    def minute(self, symbol=None, suffix=1, **kwargs):  # noqa
        """
        获取1, 5分钟线

        :param suffix: 文件前缀
        :param symbol: 证券代码
        :return: pd.dataFrame or None
        """
        subdir = 'fzline' if str(suffix) == '5' else 'minline'
        suffix = ['lc5', '5'] if str(suffix) == '5' else ['lc1', '1']
        symbol = self.find_path(symbol, subdir=subdir, suffix=suffix)

        if symbol is not None:
            reader = TdxMinBarReader() if 'lc' not in symbol.suffix else TdxLCMinBarReader()
            return reader.get_df(str(symbol))

        return None

    def fzline(self, symbol=None):
        """
        分钟线数据

        :param symbol: 自定义板块股票列表, 类型 list
        :return: pd.dataFrame or Bool
        """
        return self.minute(symbol, suffix=5)

    def block_new(self, name: str = None, symbol: list = None, group=False, **kwargs):
        """
        自定义板块数据操作

        :param name: 自定义板块名称
        :param symbol: 自定义板块股票列表, 类型 list
        :param group:
        :return: pd.dataFrame or Bool
        """
        from mootdx.tools.customize import Customize

        reader = Customize(tdxdir=self.tdxdir)

        if symbol:
            return reader.create(name=name, symbol=symbol, **kwargs)

        return reader.search(name=name, group=group)

    def stock_list(self, market='all'):
        """
        读取本地通达信证券基础信息

        :param market: sh/sz/all，或市场列表
        :return: pd.DataFrame
        """

        from mootdx.parse import BaseParse

        return BaseParse(self.tdxdir).stock_list(market=market)

    def stock_search(self, keyword, market='all', exact=False):
        """
        搜索本地通达信证券基础信息

        :param keyword: 代码或名称关键字
        :param market: sh/sz/all，或市场列表
        :param exact: 是否精确匹配代码或名称
        :return: pd.DataFrame
        """

        from mootdx.parse import BaseParse

        return BaseParse(self.tdxdir).stock_search(keyword=keyword, market=market, exact=exact)

    def contracts(self, kind='future'):
        """
        读取本地通达信扩展市场合约规则

        :param kind: future/futures 或 option/options，也可以直接传文件名
        :return: pd.DataFrame
        """

        from mootdx.parse import BaseParse

        return BaseParse(self.tdxdir).contracts(kind=kind)

    def watchlist(self, filename='zxg.blk'):
        """
        读取通达信自选股列表

        :param filename: 自选股 blk 文件名，默认 zxg.blk
        :return: pd.DataFrame
        """

        from mootdx.tools.customize import Customize

        return Customize(tdxdir=self.tdxdir).watchlist(filename=filename)

    def financial(self, filename=None, market='sh'):
        """
        读取本地 vipdoc/cw 财务文件

        :param filename: 财务文件路径；为空时读取 vipdoc/cw 下对应市场最新 gpsh/gpsz 文件
        :param market: sh 或 sz
        :return: pd.DataFrame
        """

        from mootdx.utils import gpcw

        if filename is None:
            cwdir = Path(self.tdxdir, 'vipdoc', 'cw')
            prefix = f'gp{market.lower()}'
            files = sorted(cwdir.glob(f'{prefix}*.dat'))

            if not files:
                return None

            filename = files[-1]

        return gpcw(filename)

    def cw(self, filename=None, market='sh'):
        return self.financial(filename=filename, market=market)

    def block(self, symbol='', group=False, **kwargs):
        """
        获取板块数据

        :param symbol:  板块文件
        :param group:   分组解析
        :return: pd.dataFrame or None
        """
        # from mootdx.block import BlockParse
        from mootdx.parse import BaseParse

        return BaseParse(self.tdxdir).parse(symbol, group=group, **kwargs)

    def blocks(self, name='gn', group=False):
        """
        读取通达信 T0002/hq_cache 板块文件

        :param name: gn/fg/zs/sb/sp/hk/jj/mg/uk，或完整文件名
        :param group: 是否分组返回
        :return: pd.DataFrame
        """

        from mootdx.parse import BaseParse

        return BaseParse(self.tdxdir).blocks(name=name, group=group)

    def block_files(self):
        """
        列出本地可解析板块文件

        :return: pd.DataFrame
        """

        from mootdx.parse import BaseParse

        return BaseParse(self.tdxdir).block_files()


class ExtReader(ReaderBase):
    """扩展市场读取"""

    def __init__(self, tdxdir=None):
        super(ExtReader, self).__init__(tdxdir)
        self.reader = TdxExHqDailyBarReader()

    def daily(self, symbol=None):
        """
        获取扩展市场日线数据

        :return: pd.dataFrame or None
        """

        vipdoc = self.find_path(symbol=symbol, subdir='lday', suffix='day')
        return self.reader.get_df(str(vipdoc)) if vipdoc else None

    def minute(self, symbol=None):
        """
        获取扩展市场分钟线数据

        :return: pd.dataFrame or None
        """

        if not symbol:
            return None

        vipdoc = self.find_path(symbol=symbol, subdir='minline', suffix=['lc1', '1'])
        return self.reader.get_df(str(vipdoc)) if vipdoc else None

    def fzline(self, symbol=None):
        """
        获取日线数据

        :return: pd.dataFrame or None
        """

        vipdoc = self.find_path(symbol=symbol, subdir='fzline', suffix='lc5')
        return self.reader.get_df(str(vipdoc)) if symbol else None
