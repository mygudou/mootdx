通达信数据读取接口 - 活跃维护版
================================

这是 `mootdx` 的活跃维护 fork。上游项目 `mootdx/mootdx` 最后一次提交停留在
2024-07-16，近两年 A 股市场规则、北交所代码体系、通达信服务器和 Python 依赖
都有变化。本 fork 继续维护这些兼容性问题，目标是成为当前更稳定、更适合新项目使用
的 `mootdx` 版本。

原项目地址: <https://github.com/mootdx/mootdx>

本维护版地址: <https://github.com/mygudou/mootdx>

**声明: 本项目只作学习交流，不得用于任何商业目的。投资、交易和数据使用风险请自行承担。**

为什么使用这个 fork
--------------------

这个版本已经修复或确认了上游社区近期开出的主要问题：

- 支持北交所 `920xxx` 新证券代码号段，修复 `920` 被误判为上交所的问题。
- 支持 `bj920493`、`920493.BJ`、`000300.SS`、`000300.SH`、`000001.SZ` 等常见代码格式。
- 修复 `000300.SS` 被误分类为深市的问题。
- 绕过 `tdxpy` 对北交所实时报价的人为拦截，北交所实时行情和五档报价可用。
- 放开并验证北交所历史分钟线、历史分笔接口。
- 本地通达信 `vipdoc/bj` 北交所日线文件可读取。
- 修复 F10 长文本被截断的问题，按通达信返回长度分块读取。
- 更新可用行情服务器，并增加标准市场、扩展市场服务器 fallback。
- 修复 `BESTIP.HQ` 为空导致 `ValueError: not enough values to unpack` 的问题。
- 修复 pandas 新版本下 `fillna(method=...)` 的兼容性问题。
- 历史 K 线返回异常 `0-00-00` 日期时会自动丢弃坏行，避免偶发解析异常。

对应上游 issue 包括但不限于：

- `#30` 读取不到北交所本地数据
- `#90` 周线偶发非法日期
- `#103` 北交所数据无法获取
- `#113` 分时行情无法区分股票代码还是指数代码
- `#116` F10 长文本被截断
- `#138` 分时读取不能传入列表
- `#140` 北交所 `920` 代码判断逻辑
- `#150` 空 BESTIP 导致启动报错
- `#151` `000300.SS` 误分类
- `#154` / `#155` 复权接口兼容性

能力边界
--------

我对北交所和扩展市场做了实测，结论如下：

| 功能 | 状态 | 说明 |
| --- | --- | --- |
| 北交所日 K / 分钟 K | 支持 | `client.bars("920493")` 可用 |
| 北交所实时行情 / 五档报价 | 支持 | `client.quotes(["920493"])` 可用 |
| 北交所历史分钟线 | 支持 | `client.minutes("920493", date="20260430")` 可用 |
| 北交所历史分笔 | 支持 | `client.transactions("920493", date="20260430")` 可用 |
| 北交所财务信息 / 除权除息 | 支持 | `finance` / `xdxr` 实测可用 |
| 北交所本地 vipdoc 日线 | 支持 | 自动查找 `vipdoc/bj/lday/bjxxxxxx.day` |
| 北交所全市场证券列表 | 暂不支持 | 底层 `get_security_list(market=2)` 请求会超时，不是 mootdx 简单漏实现 |
| 北交所 F10 | 暂不支持 | 直接走底层协议返回空目录 |
| 扩展市场 | 部分支持 | `markets` / `instrument` 实测可用，具体品种依赖通达信服务器 |

北交所涨跌幅 `30%`、主板/创业板/科创板涨跌幅等交易制度没有写进本库，因为
`mootdx` 是行情读取库，不做下单撮合，也不自己计算涨停价和跌停价。已扫描代码，
没有发现把 A 股涨跌幅写死为 `10%` 的逻辑。

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

使用示例
--------

### 线上行情

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market="std", timeout=5)

# A 股日 K
daily = client.bars(symbol="600036", frequency="day", offset=10)

# 北交所日 K
bse_daily = client.bars(symbol="920493", frequency="day", offset=10)

# 北交所实时行情和五档报价
quote = client.quotes(["920493"])

# 北交所历史分钟线
minutes = client.minutes(symbol="920493", date="20260430")

# 北交所历史分笔
ticks = client.transactions(symbol="920493", date="20260430", offset=50)

# 指数分钟线。000001 默认会按股票识别为深市，如需上证指数请显式传 market=1。
sse_index_minutes = client.minutes(symbol="000001", date="20260430", market=1)

client.close()
```

### F10 长文本

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market="std")

content = client.F10(symbol="000858", name="财务分析")
print(len(content))

client.close()
```

### 通达信离线数据读取

```python
from mootdx.reader import Reader

reader = Reader.factory(market="std", tdxdir="C:/new_tdx")

# 沪深日线
daily = reader.daily(symbol="600036")

# 北交所本地日线，会查找 vipdoc/bj/lday/bj920493.day
bse_daily = reader.daily(symbol="920493")

# 1 分钟 / 5 分钟
minute_1 = reader.minute(symbol="600036", suffix=1)
minute_5 = reader.minute(symbol="600036", suffix=5)
```

### 扩展市场

```python
from mootdx.quotes import Quotes

client = Quotes.factory(market="ext", timeout=5)

markets = client.markets()
instruments = client.instrument(start=0, offset=10)

client.close()
```

开发和测试
----------

```shell
pytest -q
```

本 fork 当前维护原则：

- 能通过通达信标准协议确认的，优先修复。
- `tdxpy` 人为限制但底层协议可用的，在 `mootdx` 侧绕过。
- 底层协议直接超时或返回空的，不伪造支持，会在 README 里标清能力边界。
- 对市场规则变化只修影响行情读取的部分，不把交易规则硬编码到行情库里。

License
-------

MIT License
