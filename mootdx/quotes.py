import math
import struct
from collections import OrderedDict
from datetime import datetime

import pandas
import pandas as pd
from tdxpy.exceptions import ValidationException
from tdxpy.exhq import TdxExHq_API
from tdxpy.helper import get_price
from tdxpy.helper import get_time
from tdxpy.hq import TdxHq_API
from tdxpy.parser.base import BaseParser
from tdxpy.parser.std.get_company_info_category import GetCompanyInfoCategory
from tdxpy.parser.std.get_company_info_content import GetCompanyInfoContent
from tdxpy.parser.std.get_security_quotes import GetSecurityQuotesCmd
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import retry_if_result
from tenacity import stop_after_attempt
from tenacity import wait_random
from tqdm import tqdm

from mootdx import config
from mootdx.consts import MARKET_SH
from mootdx.consts import MARKET_SZ
from mootdx.consts import return_last_value
from mootdx.exceptions import MootdxValidationException
from mootdx.logger import logger
from mootdx.server import check_server
from mootdx.utils import get_frequency
from mootdx.utils import get_stock_market
from mootdx.utils import normalize_stock_code
from mootdx.utils import to_data


class Quotes(object):
    @staticmethod
    def factory(market='std', **kwargs):
        """
        股票市场 工厂方法

        :param market:  std 股票市场, ext 扩展市场， 默认股票市场
        :param kwargs:  可变参数
        :return: object
        """

        logger.debug(kwargs)

        if market == 'ext':
            return ExtQuotes(**kwargs)

        return StdQuotes(**kwargs)


class GetHistoryTransactionDataWithNum(BaseParser):
    def setParams(self, market, code, start, count, date):
        if isinstance(code, str):
            code = code.encode('utf-8')

        if isinstance(date, (str, bytes)):
            date = int(date)

        pkg = bytearray.fromhex('0c 01 30 02 02 01 12 00 12 00 c6 0f')
        pkg.extend(struct.pack('<IH6sHH', date, market, code, start, count))

        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        pos = 0
        (num,) = struct.unpack('<H', body_buf[:2])

        pos += 2
        pos += 4

        ticks = []
        last_price = 0

        for _ in range(num):
            hour, minute, pos = get_time(body_buf, pos)

            price_raw, pos = get_price(body_buf, pos)
            vol, pos = get_price(body_buf, pos)
            num, pos = get_price(body_buf, pos)
            buy_or_sell, pos = get_price(body_buf, pos)
            _, pos = get_price(body_buf, pos)

            last_price += price_raw

            ticks.append(OrderedDict([
                ('time', f'{hour:02d}:{minute:02d}'),
                ('price', float(last_price) / 100),
                ('vol', vol),
                ('num', num),
                ('buyorsell', buy_or_sell),
            ]))

        return ticks


def valid_server(server):
    import ipaddress

    if isinstance(server, tuple) or isinstance(server, list):
        try:
            address, port = server
            ipaddress.ip_address(address)
            return address, int(port)
        except Exception:
            raise ValueError('Server 格式错误. 例如: server = ("127.0.0.1", 2272)')

    return None


def _get_config_server(index):
    servers = config.get_servers(index)
    if not servers:
        raise ValueError(f'未找到可用服务器: {index}')
    return servers[0]


def _get_config_servers(index):
    servers = config.get_servers(index)
    if not servers:
        raise ValueError(f'未找到可用服务器: {index}')
    return servers


def _remember_server(index, server):
    server and config.set_bestip(index, server)


def _index_market(symbol):
    lower_symbol = str(symbol or '').strip().lower()
    code = normalize_stock_code(symbol)
    if lower_symbol.startswith(('sh', 'sz', 'bj')) or '.' in lower_symbol:
        return get_stock_market(symbol)
    return (MARKET_SZ, MARKET_SH)[code[:2] in ['00', '88', '99']]


def _pop_market(kwargs, symbol, *, index=False):
    market = kwargs.pop('market', None)
    if market is not None:
        return int(market)

    if index:
        return _index_market(symbol)

    return int(get_stock_market(symbol))


def _quote_symbols(symbols):
    if isinstance(symbols, tuple) and len(symbols) == 2 and isinstance(symbols[0], int):
        symbols = [symbols]
    elif not isinstance(symbols, list):
        symbols = [symbols]

    result = []
    for symbol in symbols:
        if isinstance(symbol, (list, tuple)) and len(symbol) == 2 and isinstance(symbol[0], int):
            market, code = symbol
            result.append([int(market), normalize_stock_code(code)])
        else:
            result.append([get_stock_market(symbol, string=False), normalize_stock_code(symbol)])

    return result


class BaseQuotes(object):
    client = None
    bestip = None
    server = None

    verbose = False
    timeout = 15

    def __init__(self, server=None, bestip: bool = False, timeout: int = None, **kwargs) -> None:
        logger.debug('config.setup()')
        config.setup()

        logger.debug(f'server => {server}')
        self.server = valid_server(server)

        logger.debug(f'bestip => {bestip}')
        bestip and check_server(sync=True)

        self.timeout = timeout or 15
        logger.debug(f'timeout => {self.timeout}')

        self.verbose = kwargs.get('verbose', False)
        logger.debug(f'verbose => {self.verbose}')

    def __del__(self):
        logger.debug('call __del__')
        self.close()

    def reconnect(self):
        if self.closed:
            logger.debug('服务器连接已断开，正进行重新连接...')
            self.client.connect(*self.bestip)

    def close(self):
        logger.debug('close')
        hasattr(self.client, 'close') and self.client.close()

    @property
    def closed(self) -> bool:
        if not hasattr(self.client.client, '_closed') or getattr(self.client.client, '_closed'):
            return True

        return False

    def pool(self):
        ...


instance: BaseQuotes


def check_empty(value):
    """
    重试判断函数

    :param value: 要判断的值
    :return:
    """
    _empty = value.all().empty if isinstance(value, pd.DataFrame) else not value

    # 判断状态空，则重连接
    if instance and _empty:
        logger.warning('返回数据空, 重新连接服务器...')
        # instance.client.connect(*instance.server)

    return _empty


class StdQuotes(BaseQuotes):
    """
    股票市场实时行情"""

    company_info_chunk_size = 32000

    def __init__(self, server=None, bestip=False, timeout=15, heartbeat=False, auto_retry=True, raise_exception=False,
                 **kwargs):
        """构造函数

        :param bestip:  最佳 IP
        :param timeout: 超时时间
        :param kwargs:  可变参数
        """

        super().__init__(bestip=bestip, timeout=timeout, server=server, **kwargs)
        _remember_server('HQ', self.server)

        try:
            config.get('SERVER').get('HQ')[0]
        except ValueError as ex:
            logger.warning(ex)
        finally:
            self.server = _get_config_server('HQ')

        last_error = None
        for ip, port in _get_config_servers('HQ'):
            logger.debug(f'server: {(ip, port)}')
            client = TdxHq_API(heartbeat=heartbeat, auto_retry=auto_retry, raise_exception=raise_exception)
            try:
                connected = client.connect(ip, int(port), time_out=timeout)
                if connected is False:
                    raise TimeoutError(f'connect failed: {ip}:{port}')
                self.server = (ip, int(port))
                self.client = client
                _remember_server('HQ', self.server)
                break
            except Exception as ex:
                last_error = ex
                logger.warning(f'行情服务器连接失败: {ip}:{port}, {ex}')
                try:
                    client.close()
                except Exception:
                    pass
        else:
            raise last_error or TimeoutError('行情服务器连接失败')

        global instance
        instance = self

    def traffic(self):
        return self.client.get_traffic_stats()

    def _call_command(self, command, *args):
        cmd = command(self.client.client, lock=self.client.lock)
        cmd.setParams(*args)
        return cmd.call_api()

    def _company_info_category(self, market, code):
        return self._call_command(GetCompanyInfoCategory, market, code)

    def _company_info_content(self, market, code, filename, start, length):
        parts = []
        position = int(start)
        remaining = int(length)

        while remaining > 0:
            chunk_size = min(self.company_info_chunk_size, remaining)
            chunk = self._call_command(GetCompanyInfoContent, market, code, filename, position, chunk_size)

            if not chunk:
                break

            parts.append(chunk)
            chunk_length = len(chunk.encode('gbk', 'ignore'))

            if chunk_length <= 0:
                break

            position += chunk_length
            remaining -= chunk_length

        return ''.join(parts)

    def quotes(self, symbol=None, **kwargs):
        """
        获取实时日行情数据

        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """

        if not symbol:
            return to_data(None)

        try:
            symbol = _quote_symbols(symbol)
            result = self._call_command(GetSecurityQuotesCmd, symbol)
        except ValidationException:
            return to_data(None)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    def quotes_batch(self, symbol=None, symbols=None, batch_size=80, **kwargs):
        """
        批量获取实时行情

        :param symbol: 股票代码列表，或已解析好的 [(market, code)] 列表 (推荐使用 symbols)
        :param symbols: 股票代码列表 (优先于 symbol，新代码请用此参数)
        :param batch_size: 单次请求数量
        :return: pd.DataFrame
        """

        symbol = symbols if symbols is not None else symbol

        if not symbol:
            return to_data(None)

        resolved = _quote_symbols(symbol)
        result = []

        for start in range(0, len(resolved), int(batch_size)):
            batch = resolved[start:start + int(batch_size)]
            try:
                data = self.quotes(symbol=batch, **kwargs)
            except (ValueError, ValidationException) as exc:
                logger.warning('quotes_batch: skip batch due to %s', exc)
                continue
            if not data.empty:
                result.append(data)

        return pandas.concat(result, ignore_index=True) if result else to_data(None)

    def quotes_all(self, market=None, batch_size=80, **kwargs):
        """
        获取沪深市场全部证券的实时行情

        :param market: 市场代码，默认 [0, 1]
        :param batch_size: 单次请求数量
        :return: pd.DataFrame
        """

        markets = [MARKET_SZ, MARKET_SH] if market is None else market
        markets = markets if isinstance(markets, (list, tuple, set)) else [markets]
        symbols = []

        for item in markets:
            stocks = self.stocks(int(item))
            if not stocks.empty:
                symbols.extend([[int(item), code] for code in stocks.code.tolist()])

        return self.quotes_batch(symbol=symbols, batch_size=batch_size, **kwargs)

    def bars(self, symbol='000001', frequency=9, start=0, offset=800, **kwargs):
        """
        获取实时日K线数据

        :param symbol: 股票代码
        :param frequency: 数据频次
        :param start: 开始位置
        :param offset: 每次获取条数
        :return: pd.dataFrame or None
        """
        if isinstance(symbol, (list, tuple, set)):
            result = []
            for code in symbol:
                item = self.bars(symbol=code, frequency=frequency, start=start, offset=offset, **kwargs)
                if not item.empty:
                    item = item.assign(code=normalize_stock_code(code))
                    result.append(item)

            return pandas.concat(result) if result else to_data(None)

        frequency = get_frequency(frequency)
        market = _pop_market(kwargs, symbol)
        code = normalize_stock_code(symbol)

        offset = (offset, 800)[offset > 800]
        result = self.client.get_security_bars(int(frequency), int(market), str(code), int(start), int(offset))

        return to_data(result, symbol=code, client=self, **kwargs)

    def stock_count(self, market=MARKET_SH):
        """
        获取市场股票数量

        :param market: 股票市场代码 sh 上海， sz 深圳
        :return: pd.dataFrame or None
        """
        if market not in [0, 1, 2]:
            raise MootdxValidationException('市场代码错误')

        result = self.client.get_security_count(market=market)

        return result

    def stocks(self, market=MARKET_SH):
        """
        获取股票列表

        :param market: 股票市场
        :return:
        """

        if market not in [0, 1]:
            raise MootdxValidationException('市场代码错误, 目前只支持沪深市场')

        counts = self.stock_count(market=market)
        stocks = None

        if counts > 0:
            for start in tqdm(range(0, counts, 1000), ascii=True):
                result = self.client.get_security_list(market=market, start=start)
                stocks = pandas.concat([stocks, to_data(result)], ignore_index=True) if start > 1 else to_data(result)

        return stocks

    def stock_all(self):
        stocks = None

        for m in [0, 1]:
            stocks = pandas.concat([stocks, self.stocks(m)], ignore_index=True)

        return stocks

    def index_bars(self, symbol='000001', frequency=9, start=0, offset=800, **kwargs):
        """
        获取指数k线

        :param symbol: 股票代码
        :param frequency: 数据频次
        :param start: 开始位置
        :param offset: 获取数量
        :return:
        """

        frequency = get_frequency(frequency)
        offset = (offset, 800)[offset > 800]

        market = _pop_market(kwargs, symbol, index=True)
        code = normalize_stock_code(symbol)
        result = self.client.get_index_bars(int(frequency), int(market), str(code), int(start), int(offset))

        return to_data(result, symbol=code, client=self, **kwargs)

    def minute(self, symbol=None, **kwargs):
        """
        获取实时分时数据

        :param symbol: 股票代码
        :return: pd.DataFrame
        """

        today = datetime.now().strftime('%Y%m%d')
        return self.minutes(symbol=symbol, date=today, **kwargs)

    def minutes(self, symbol=None, date='20191023', **kwargs):
        """
        分时历史数据

        :param symbol:  股票代码
        :param date:    查询日期
        :return: pd.dataFrame or None
        """
        if isinstance(symbol, (list, tuple, set)):
            result = []
            for code in symbol:
                item = self.minutes(symbol=code, date=date, **kwargs)
                if not item.empty:
                    item = item.assign(code=normalize_stock_code(code))
                    result.append(item)

            return pandas.concat(result) if result else to_data(None)

        market = _pop_market(kwargs, symbol)
        code = normalize_stock_code(symbol)

        result = self.client.get_history_minute_time_data(market=market, code=code, date=date)

        return to_data(result, symbol=code, client=self, **kwargs)

    def transaction(self, symbol='', start=0, offset=800, **kwargs):
        """
        查询分笔成交

        :param symbol:  股票代码
        :param start:   起始位置
        :param offset:  结束位置
        :return: pd.dataFrame or None
        """

        market = _pop_market(kwargs, symbol)
        code = normalize_stock_code(symbol)

        result = self.client.get_transaction_data(int(market), code, start, offset)

        return to_data(result, symbol=code, client=self, **kwargs)

    def transactions(self, symbol='', start=0, offset=800, date='20170209', **kwargs):
        """
        查询历史分笔成交

        :param symbol:  股票代码
        :param start:   起始位置
        :param offset:  获取数量
        :param date:    查询日期
        :return: pd.dataFrame or None
        """

        with_num = kwargs.pop('with_num', True)
        market = _pop_market(kwargs, symbol)
        code = normalize_stock_code(symbol)

        if with_num:
            result = self._call_command(GetHistoryTransactionDataWithNum, market, code, start, offset, int(date))
        else:
            result = self.client.get_history_transaction_data(market, code, start, offset, int(date))

        return to_data(result, symbol=code, client=self, **kwargs)

    def transactions_all(self, symbol='', date='20170209', offset=1800, **kwargs):
        """
        查询指定日期尽可能完整的历史分笔成交

        :param symbol:  股票代码
        :param date:    查询日期
        :param offset:  每次获取数量。带成交笔数协议实测单次最多返回 1800 条
        :return: pd.dataFrame or None
        """

        start = int(kwargs.pop('start', 0))
        offset = min(int(offset), 1800)
        chunks = []

        while True:
            data = self.transactions(symbol=symbol, start=start, offset=offset, date=date, **kwargs)

            if data.empty:
                break

            chunks.insert(0, data)
            count = len(data)
            start += count

            if count < offset:
                break

        if not chunks:
            return to_data(None)

        return pandas.concat(chunks, ignore_index=True)

    def F10C(self, symbol=''):  # noqa
        """
        查询公司信息目录

        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """

        market = int(get_stock_market(symbol))
        code = normalize_stock_code(symbol)
        result = self._company_info_category(market, code)

        return result

    def F10(self, symbol='', name=''):  # noqa
        """
        读取公司信息详情

        :param name: 公司 F10 标题
        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """

        result = {}
        market = int(get_stock_market(symbol, string=False))
        code = normalize_stock_code(symbol)
        category = self._company_info_category(market, code)

        if not category:
            return None

        if name:
            for x in category:
                if x['name'] == name:
                    return self._company_info_content(
                        market=market,
                        code=code,
                        filename=x['filename'],
                        start=x['start'],
                        length=x['length'],
                    )

        for x in category:
            result[x['name']] = self._company_info_content(
                market=market, code=code, filename=x['filename'], start=x['start'], length=x['length']
            )

        return result

    def xdxr(self, symbol='', **kwargs):
        """
        读取除权除息信息

        :param symbol: 股票代码
        :return: pd.dataFrame or None
        """

        market = get_stock_market(symbol)
        code = normalize_stock_code(symbol)
        result = self.client.get_xdxr_info(int(market), code)

        return to_data(result, symbol=code, client=self, **kwargs)

    def finance(self, symbol='000001', **kwargs):
        """
        读取财务信息

        :param symbol: 股票代码
        :return:
        """

        market = get_stock_market(symbol)
        code = normalize_stock_code(symbol)
        result = self.client.get_finance_info(market=market, code=code)

        return to_data(result, symbol=code, client=self, **kwargs)

    def k(self, symbol='', begin=None, end=None, **kwargs):
        """
        读取k线信息

        :param symbol:  股票代码
        :param begin:   开始日期
        :param end:     截止日期
        :return: pd.dataFrame or None
        """

        result = self.get_k_data(symbol, begin, end)
        return to_data(result, symbol=symbol, **kwargs)

    def ohlc(self, **kwargs):
        return self.k(**kwargs)

    def get_k_data(self, code, start_date, end_date):
        # 开始时间离现在有几天
        first = (pd.to_datetime(end_date) - pd.to_datetime(datetime.now().date())).days
        first = (abs(first), 0)[first >= 0]

        # 结束时间离现在有几天
        last = (pd.to_datetime(start_date) - pd.to_datetime(datetime.now().date())).days
        last = (abs(last), 0)[last >= 0]

        # 去除节假日
        first -= int(first / 2.8)  # 非交易日大概是全年的1/3
        last -= int(last / 3.5)  # 非交易日大概是全年的1/3

        temp = []
        market = get_stock_market(code)
        code = normalize_stock_code(code)

        for i in range(math.ceil((last - first) / 800)):
            data = self.client.get_security_bars(9, market, code, (first + i * 800), 800)
            temp.append(self.client.to_df(data))

        data = pd.concat(temp)
        data = data.assign(date=data['datetime'].apply(lambda x: str(x)[0:10])).assign(code=str(code))
        data = data.set_index('date', drop=False, inplace=False)
        data = data.drop(['year', 'month', 'day', 'hour', 'minute', 'datetime'], axis=1)
        data = data.loc[(data.date >= start_date) & (data.date < end_date)]
        data = data.sort_index()

        return data

    def index(self, symbol='000001', frequency=9, start=0, offset=800, **kwargs):
        """
        获取指数k线

        K线种类:
        - 0 5分钟K线
        - 1 15分钟K线
        - 2 30分钟K线
        - 3 1小时K线
        - 4 日K线
        - 5 周K线
        - 6 月K线
        - 7 1分钟
        - 8 1分钟K线
        - 9 日K线
        - 10 季K线
        - 11 年K线

        :param symbol:      股票代码
        :param frequency:   数据频次
        :param market:      证券市场
        :param start:       开始位置
        :param offset:      每次获取条数
        :return: pd.dataFrame or None
        """
        frequency = get_frequency(frequency)

        offset = (offset, 800)[offset > 800]
        market = _pop_market(kwargs, symbol, index=True)
        code = normalize_stock_code(symbol)
        result = self.client.get_index_bars(int(frequency), int(market), str(code), int(start), int(offset))

        return to_data(result, symbol=code, client=self, **kwargs)

    def block(self, tofile='block.dat', **kwargs):
        """
        获取证券板块信息

        :param tofile: 保存文件
        :return: pd.dataFrame or None
        """

        result = self.client.get_and_parse_block_info(tofile)
        return to_data(result, **kwargs)


class ExtQuotes(BaseQuotes):
    """扩展市场实时行情"""

    # server = ("112.74.214.43", 7727)

    def __init__(self, server: list = None, bestip=False, timeout=15, **kwargs):
        """
        构造函数

        :param bestip:  最优服务器IP
        :param timeout: 超时时间
        :param kwargs:  可变参数
        """
        super().__init__(bestip=bestip, timeout=timeout, server=server, **kwargs)
        _remember_server('EX', self.server)

        try:
            config.get('SERVER').get('EX')[0]
        except ValueError as ex:
            logger.warning(ex)
        finally:
            self.server = _get_config_server('EX')

        for x in ['verbose', 'server', 'quiet']:
            if x in kwargs.keys():
                del kwargs[x]

        last_error = None
        for ip, port in _get_config_servers('EX'):
            self.client = TdxExHq_API(raise_exception=False, auto_retry=True, **kwargs)
            try:
                connected = self.client.connect(ip, int(port), time_out=timeout)
                if connected is False:
                    raise TimeoutError(f'connect failed: {ip}:{port}')
                self.server = (ip, int(port))
                _remember_server('EX', self.server)
                break
            except Exception as ex:  # noqa
                last_error = ex
                logger.warning(f'扩展行情服务器连接失败: {ip}:{port}, {ex}')
                try:
                    self.client.close()
                except Exception:
                    pass
        else:
            raise last_error or TimeoutError('扩展行情服务器连接失败')

        global instance
        instance = self

    @staticmethod
    def validate(market, symbol):
        """
        验证股票市场

        :param market: 股票市场
        :param symbol: 股票代码
        :return: tuple
        """

        if not market:
            if len(symbol.split('#')) > 1:
                market = symbol.split('#')[0]
                symbol = symbol.split('#')[1]

        if not market:
            raise ValueError('市场参数错误, 市场参数不能为空.')

        return int(market), symbol

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def markets(self, **kwargs):
        """
        获取实时市场列表

        :return: pd.dataFrame or None
        """

        result = self.client.get_markets()
        return to_data(result, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def instrument(self, start=0, offset=800, **kwargs):
        """
        查询代码列表

        :param start:   开始位置
        :param offset:  获取数量
        :return:
        """

        result = self.client.get_instrument_info(start=start, count=offset)
        return to_data(result, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def instrument_count(self):
        """
        市场商品数量

        :return:
        """

        result = self.client.get_instrument_count()

        return result

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def instruments(self, **kwargs):
        """
        查询所有代码列表

        :return:
        """

        result = []

        count = self.client.get_instrument_count()
        pages = math.ceil(count / 100)

        for page in tqdm(range(0, pages), ascii=True):
            result += self.client.get_instrument_info(page * 100, 100)

        return to_data(result, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def quote(self, market='', symbol='', **kwargs):
        """
        查询五档行情

        :param market: 市场ID
        :param symbol: 证券代码
        :return:
        """

        market, symbol = self.validate(market, symbol)
        result = self.client.get_instrument_quote(market, symbol)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def minute(self, market='', symbol='', **kwargs):
        """
        查询分时行情

        :param market: 市场ID
        :param symbol: 证券代码
        :return:
        """

        market, symbol = self.validate(market, symbol)
        result = self.client.get_minute_time_data(market, symbol)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def minutes(self, market=None, symbol='', date='', **kwargs):
        """
        查询历史分时行情

        :param market:  市场ID
        :param symbol:  证券代码
        :param date:    查询日期
        :return:
        """

        market, symbol = self.validate(market, symbol)
        result = self.client.get_history_minute_time_data(market, symbol, date)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def bars(self, frequency='', market='', symbol='', start=0, offset=800, **kwargs):
        """
        查询k线数据

        :param frequency: 数据频次, K线周期
        :param market: 市场ID
        :param symbol: 证券代码
        :param start:  起始位置
        :param offset: 获取数量
        :return:
        """

        frequency = get_frequency(frequency)
        market, symbol = self.validate(market, symbol)
        result = self.client.get_instrument_bars(
            category=frequency, market=market, code=symbol, start=start, count=offset
        )

        return to_data(result, symbol=symbol, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def transaction(self, market=None, symbol='', start=0, offset=800, **kwargs):
        """
        查询分笔成交

        :param market: 市场ID
        :param symbol: 证券代码
        :param start:  开始位置
        :param offset: 获取数量
        :return:
        """

        market, symbol = self.validate(market, symbol)
        result = self.client.get_transaction_data(market=market, code=symbol, start=start, count=offset)

        return to_data(result, symbol=symbol, client=self, **kwargs)

    @retry(
        wait=wait_random(min=1, max=10),
        stop=stop_after_attempt(3),
        retry_error_callback=return_last_value,
        retry=(retry_if_exception_type() | retry_if_result(check_empty)),
    )
    def transactions(self, market=None, symbol='', date='', start=0, offset=800, **kwargs):
        """
        查询历史分笔成交

        :param market:  市场ID
        :param symbol:  证券代码
        :param date:    查询日期
        :param start:   开始位置
        :param offset:  获取数量
        :return:
        """

        market, symbol = self.validate(market, symbol)
        result = self.client.get_history_transaction_data(
            market=market, code=symbol, date=int(date), start=start, count=offset
        )

        return to_data(result, symbol=symbol, client=self, **kwargs)
