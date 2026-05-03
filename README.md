通达信数据读取接口 - 活跃维护版
================================

这是 `mootdx` 的活跃维护 fork。上游项目 `mootdx/mootdx` 最后一次提交停留在
2024-07-16，近两年 A 股市场规则、北交所代码体系、通达信服务器和 Python 依赖
都有变化。本 fork 继续维护标准行情、扩展行情、本地文件、财务数据、复权、CLI 等
通达信数据读取能力，目标是成为当前更稳定、更适合新项目使用的 `mootdx` 版本。

原项目地址: <https://github.com/mootdx/mootdx>

本维护版地址: <https://github.com/mygudou/mootdx>

**声明: 本项目只作学习交流，不得用于任何商业目的。投资、交易和数据使用风险请自行承担。**

安装方法
--------

从 GitHub 安装当前维护版：

```shell
pip install -U "mootdx[all] @ git+https://github.com/mygudou/mootdx.git"
```

只安装核心依赖：

```shell
pip install -U "mootdx @ git+https://github.com/mygudou/mootdx.git"
```

如果你已经安装过 PyPI 上的旧版，可以先卸载再安装本 fork：

```shell
pip uninstall -y mootdx
pip install -U "mootdx[all] @ git+https://github.com/mygudou/mootdx.git"
```

运行环境
--------

- 操作系统: Windows / macOS / Linux
- Python: 3.8 及以上
- 在线行情需要可连接通达信行情服务器
- 本地读取需要通达信客户端目录，例如 `C:/new_tdx`

完整能力矩阵
------------

### 标准行情 `Quotes.factory(market="std")`

用于沪深京 A 股、指数、债券、基金、ETF、通达信板块指数等标准市场数据。

| 能力 | 接口 | 状态 | 说明 |
| --- | --- | --- | --- |
| 实时行情 / 五档报价 | `quotes()` | 支持 | 支持单代码、代码列表、`(market, code)` 精确市场元组 |
| 批量实时行情 | `quotes_batch()` | 支持 | 自动分批请求，适合自选股和股票池 |
| 全市场实时行情 | `quotes_all()` | 支持 | 支持沪深全市场；北交所证券列表受底层协议限制 |
| K 线 | `bars()` | 支持 | 5 分钟、15 分钟、30 分钟、1 小时、日、周、月、季、年等周期 |
| 指数 K 线 | `index()` / `index_bars()` | 支持 | 支持 `000001.SH`、`880008` 等指数和通达信 88 指数 |
| 当日分时 | `minute()` | 支持 | 读取当日分时数据 |
| 历史分钟线 | `minutes()` | 支持 | 指定交易日历史分钟数据，支持显式 `market=` |
| 当日分笔 | `transaction()` | 支持 | 当前交易日逐笔/分笔成交 |
| 历史分笔 | `transactions()` | 支持 | 默认带 `num` 成交笔数字段；可关闭兼容旧协议 |
| 全天历史分笔 | `transactions_all()` | 支持 | 自动分页尽可能拉取完整单日分笔 |
| 证券数量 | `stock_count()` | 支持 | 沪深市场可用；北交所底层请求会超时 |
| 证券列表 | `stocks()` / `stock_all()` | 支持 | 沪深市场可用 |
| F10 目录 | `F10C()` | 支持 | 公司信息目录 |
| F10 正文 | `F10()` | 支持 | 长文本已改为分块读取，避免被截断 |
| 除权除息 | `xdxr()` | 支持 | 返回通达信除权除息信息 |
| 财务信息 | `finance()` | 支持 | 返回通达信在线财务摘要 |
| 区间日线 | `k()` / `ohlc()` / `get_k_data()` | 支持 | 按日期区间读取并整理日线 |
| 在线板块文件 | `block()` | 支持 | 读取并解析通达信在线板块信息 |
| 连接状态 | `traffic()` / `close()` | 支持 | 查询流量统计、关闭连接 |

### 扩展行情 `Quotes.factory(market="ext")`

用于通达信扩展市场，例如期货、期权、港股、外盘等。可用性取决于当前通达信扩展行情服务器和账号权限。

| 能力 | 接口 | 状态 | 说明 |
| --- | --- | --- | --- |
| 市场列表 | `markets()` | 支持 | 获取扩展市场 ID 和分类 |
| 单页合约列表 | `instrument()` | 支持 | 按 `start` / `offset` 分页读取 |
| 合约总数 | `instrument_count()` | 支持 | 返回扩展市场合约数量 |
| 全部合约列表 | `instruments()` | 支持 | 自动分页读取全部扩展合约 |
| 五档行情 | `quote()` | 支持 | 支持 `market=47, symbol="IF1709"` 和 `47#IF1709` |
| 当日分时 | `minute()` | 支持 | 扩展市场当日分时 |
| 历史分时 | `minutes()` | 支持 | 扩展市场指定日期分时 |
| K 线 | `bars()` | 支持 | 扩展市场 K 线 |
| 当日分笔 | `transaction()` | 支持 | 扩展市场分笔成交 |
| 历史分笔 | `transactions()` | 支持 | 扩展市场历史分笔成交 |

### 本地通达信 Reader `Reader.factory(market="std")`

用于读取本机通达信安装目录下的离线数据。

| 能力 | 接口 | 状态 | 读取位置 |
| --- | --- | --- | --- |
| 沪深京日线 | `daily()` | 支持 | `vipdoc/{sh,sz,bj}/lday/*.day` |
| 本地 1 分钟 / 5 分钟 | `minute()` / `fzline()` | 支持 | `vipdoc/{sh,sz}/minline`、`fzline` |
| 本地板块 | `block()` | 支持 | `T0002/hq_cache/block_*.dat` 等 |
| 常用板块别名 | `blocks()` | 支持 | `gn`、`fg`、`zs`、`sb`、`sp`、`hk`、`jj`、`mg`、`uk` |
| 板块文件清单 | `block_files()` | 支持 | 列出本地可解析板块文件 |
| 自定义板块 | `block_new()` | 支持 | 读取、创建、更新本地自定义板块 |
| 自选股 | `watchlist()` | 支持 | `T0002/blocknew/zxg.blk` |
| 证券基础信息 | `stock_list()` | 支持 | `T0002/hq_cache/shm.tnf`、`szm.tnf` |
| 证券搜索 | `stock_search()` | 支持 | 支持代码/名称模糊搜索和精确搜索 |
| 期货/期权合约规则 | `contracts()` | 支持 | `code2name.ini`、`code2name_qq.ini` |
| 本地财务文件 | `financial()` / `cw()` | 支持 | `vipdoc/cw/gpsh*.dat`、`gpsz*.dat` |

### 本地扩展市场 Reader `Reader.factory(market="ext")`

| 能力 | 接口 | 状态 | 说明 |
| --- | --- | --- | --- |
| 扩展市场日线 | `daily()` | 支持 | 读取 `vipdoc/ds/lday` 等扩展市场本地日线 |
| 扩展市场 1 分钟 | `minute()` | 支持 | 读取扩展市场本地分钟线 |
| 扩展市场 5 分钟 | `fzline()` | 支持 | 读取扩展市场本地 5 分钟线 |

### 财务、复权、工具

| 能力 | 接口 / 命令 | 状态 | 说明 |
| --- | --- | --- | --- |
| 财务文件列表 | `Affair.files()` / `mootdx affair --listfile` | 支持 | 获取通达信历史财务文件列表 |
| 财务文件下载 | `Affair.fetch()` / `mootdx affair --fetch` | 支持 | 下载单个或全部 `gpcw*.zip` |
| 财务文件解析 | `Affair.parse()` / `FinancialReader.to_data()` | 支持 | 解析 zip/dat 为 DataFrame |
| 前复权 / 后复权 | `to_data(adjust="qfq/hfq")` | 支持 | 日线读取时可传复权参数 |
| 复权工具 | `mootdx.tools.reversion` | 支持 | 提供前复权、后复权等计算工具 |
| 节假日工具 | `mootdx.utils.holiday` | 支持 | 交易日/节假日判断工具 |
| 文件导出 | `to_file()` | 支持 | CSV、Excel、HDF5、JSON |
| 行情服务器测速 | `mootdx bestip` | 支持 | 测速并写入 `~/.mootdx/config.json` |
| 在线行情 CLI | `mootdx quotes` | 支持 | 命令行读取在线 K 线 |
| 本地行情 CLI | `mootdx reader` | 支持 | 命令行读取本地数据 |
| 批量下载 CLI | `mootdx bundle` | 支持 | 批量导出多个证券 K 线 |

### 市场和代码格式

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| 沪市 / 深市 / 北交所市场识别 | 支持 | `sh`、`sz`、`bj`，以及市场 ID `1`、`0`、`2` |
| 常见后缀 | 支持 | `600036.SH`、`000001.SZ`、`920493.BJ`、`000300.SS` |
| 常见前缀 | 支持 | `sh600036`、`sz000001`、`bj920493` |
| 直接市场元组 | 支持 | 例如 `(1, "600036")`、`(2, "920493")` |
| 通达信 88 指数 | 支持 | 例如 `880008` 全 A 等权，不再误判为北交所 |
| 北交所新代码段 | 支持 | `920xxx`、`43xxxx`、`83xxxx`、`87xxxx` |

当前边界
--------

这些边界已经验证过，README 里明确写出来，避免伪造支持：

- 北交所日 K、分钟 K、实时行情、五档报价、历史分钟线、历史分笔、财务信息、除权除息可用。
- 北交所全市场证券列表暂不支持；底层 `get_security_list(market=2)` 请求会超时。
- 北交所 F10 暂不支持；底层公司信息目录直接返回空。
- 扩展市场依赖通达信扩展行情服务器和账号权限，不同服务器返回能力可能不同。
- 本地 `.tnf` 已支持基础字段；更多隐藏字段语义还在对表中。
- 本地 `.tdf`、`.tfz`、`.tcu`、扩展数据管理器 `.dat/.idx` 还没有完整解析。
- 北交所涨跌幅 `30%`、主板/创业板/科创板涨跌幅等交易制度没有写进本库；`mootdx` 是行情读取库，不做下单撮合，也不自己计算涨停价和跌停价。

为什么使用这个 fork
--------------------

这个版本不是只修北交所，而是对通达信数据读取链路做持续维护。当前已经修复或补齐：

- 更新标准行情和扩展行情可用服务器，并增加服务器 fallback。
- 修复 `BESTIP.HQ` 为空导致启动时报 `ValueError` 的问题。
- 修复 pandas 新版本下 `fillna(method=...)` 的兼容性问题。
- 支持 `bj920493`、`920493.BJ`、`000300.SS`、`000300.SH`、`000001.SZ` 等常见代码格式。
- 支持北交所 `920xxx` 新证券代码号段，修复 `920` 被误判为上交所的问题。
- 绕过 `tdxpy` 对北交所实时报价的人为拦截，北交所实时行情和五档报价可用。
- 放开并验证北交所历史分钟线、历史分笔接口。
- 修复 `000300.SS` 被误分类为深市的问题。
- 修复 `88xxxx` 通达信板块/自定义指数被误判为北交所的问题。
- 修复 F10 长文本被截断的问题，按通达信返回长度分块读取。
- 历史分笔成交默认返回 `num` 成交笔数，并新增 `transactions_all()`。
- 新增 `quotes_batch()` / `quotes_all()`。
- 支持直接传入 `(market, code)` 查询。
- 本地通达信 `vipdoc/bj` 北交所日线文件可读取。
- 修复上交所可转债本地日线成交量单位偏大 10 倍的问题。
- 新增本地自选股 `zxg.blk` 读取能力。
- 新增本地 `T0002/hq_cache` 板块别名入口。
- 新增本地 `shm.tnf`、`szm.tnf` 证券基础信息读取和搜索。
- 新增本地 `code2name.ini`、`code2name_qq.ini` 扩展市场合约规则读取。
- 新增本地 `vipdoc/cw/gpsh*.dat`、`gpsz*.dat` 财务文件读取。
- CSV/Excel/JSON 等导出会保留日线/分钟线的时间索引。
- 修复命令行 `quotes` / `bundle` 的周期参数映射。
- 历史 K 线返回异常 `0-00-00` 日期时会自动丢弃坏行，避免偶发解析异常。

对应上游 issue 包括但不限于：

- `#30` 读取不到北交所本地数据
- `#90` 周线偶发非法日期
- `#107` `880008` 等通达信指数数据获取
- `#114` / `#52` 历史分笔缺少成交笔数
- `#103` 北交所数据无法获取
- `#113` 分时行情无法区分股票代码还是指数代码
- `#116` F10 长文本被截断
- `#138` 分时读取不能传入列表
- `#140` 北交所 `920` 代码判断逻辑
- `#150` 空 BESTIP 导致启动报错
- `#151` `000300.SS` 误分类
- `#154` / `#155` 复权接口兼容性
- `#82` 本地读取可转债成交量单位

使用示例
--------

### 标准在线行情

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market="std", timeout=5)

daily = client.bars(symbol="600036", frequency="day", offset=10)
quote = client.quotes(["600036", "000001.SZ", "920493.BJ"])
quotes = client.quotes_batch([(1, "600036"), (0, "000001"), (2, "920493")])
all_quotes = client.quotes_all(market=[0, 1])

minutes = client.minutes(symbol="600036", date="20260430")
ticks = client.transactions(symbol="000001", date="20260430", offset=10)
all_ticks = client.transactions_all(symbol="000001", date="20260430")

xdxr = client.xdxr(symbol="600036")
finance = client.finance(symbol="600036")
f10 = client.F10(symbol="000858", name="财务分析")

client.close()
```

### 指数和北交所

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market="std", timeout=5)

# 通达信 88 指数，例如全 A 等权
all_a_equal_weight = client.index(symbol="880008", frequency="day", offset=10)

# 上证指数。000001 默认可能按股票规则识别，指数建议显式传 market=1。
sse_index_minutes = client.minutes(symbol="000001", date="20260430", market=1)

# 北交所
bse_daily = client.bars(symbol="920493", frequency="day", offset=10)
bse_quote = client.quotes(["920493"])
bse_minutes = client.minutes(symbol="920493", date="20260430")
bse_ticks = client.transactions(symbol="920493", date="20260430")

client.close()
```

### 扩展在线行情

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market="ext", timeout=5)

markets = client.markets()
count = client.instrument_count()
instruments = client.instrument(start=0, offset=100)
quote = client.quote(symbol="47#IF1709")
bars = client.bars(frequency="day", symbol="47#IF1709", start=0, offset=100)

client.close()
```

### 通达信本地数据

```python
from mootdx.reader import Reader

reader = Reader.factory(market="std", tdxdir="C:/new_tdx")

daily = reader.daily(symbol="600036")
bse_daily = reader.daily(symbol="920493")
minute_1 = reader.minute(symbol="600036", suffix=1)
minute_5 = reader.minute(symbol="600036", suffix=5)

watchlist = reader.watchlist()
concept_blocks = reader.blocks("gn", group=True)
available_blocks = reader.block_files()

stocks = reader.stock_list(market="all")
matches = reader.stock_search("600036", market="sh", exact=True)

futures = reader.contracts(kind="future")
options = reader.contracts(kind="option")

local_finance = reader.financial(market="sh")
```

### 财务文件

```python
from mootdx.affair import Affair

files = Affair.files()
Affair.fetch(downdir="output", filename=files[0]["filename"])
data = Affair.parse(downdir="output", filename=files[0]["filename"])
```

### 命令行

```shell
mootdx bestip -l 5
mootdx quotes -s 600036 -a daily -o output/600036.csv
mootdx reader -d C:/new_tdx -s 600036 -a daily
mootdx affair --listfile
mootdx bundle -s 600036,000001 -a daily -o bundle
```

开发和测试
----------

```shell
pytest -q
```

本维护版每次修复都应配套测试。能通过通达信标准协议确认的，优先修复；`tdxpy` 人为限制但底层协议可用的，在 `mootdx` 侧绕过；底层协议直接超时或返回空的，不伪造支持，会在 README 里标清边界。

后续维护方向
------------

- 标准行情：继续补齐指数、债券、基金、ETF、北交所、新三板等代码类型和字段含义。
- 扩展行情：持续验证期货、期权、港股、外盘等市场，区分协议能力和服务器权限。
- 本地文件：继续补齐扩展数据管理器 `.dat/.idx`、`.tdf`、`.tfz`、`.tcu` 等解析，并完善 `.tnf` 字段含义。
- 板块体系：继续整理行业、概念、地域、自定义板块、自选股的字段和对表测试。
- F10/财务：补齐长文本、财报文件、字段字典和异常数据校验。
- 与通达信客户端对表：对典型股票、指数、债券、ETF、期货、期权样本做持续回归测试。

License
-------

MIT License
