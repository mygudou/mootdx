"""tdxpy 握手兼容：新一代通达信行情主站拒绝第三个握手包（2026-09-30）。

tdxpy 的 ``TdxHq_API.setup`` 依次发 ``0x000d/01``、``0x000d/02`` 和 ``0x0fdb`` + 32 字节
旧客户端标识。新一代主站（101.x / 111.x / 114.141.x / 123.125.108.x …）对第三个包回
「客户端与行情主站不匹配,不能使用!」，之后 K 线 / 批量行情 / F10 目录全部返回空，
看起来像「连得上但报价为空」的僵尸——bestip 会把它们全部判死。老主站有没有第三个包
都一样。eltdx、injoyai/tdx 只发 ``0x000d/01``（+心跳）就能用所有主站。

这里把 ``setup`` 改成只发前两个包。``import mootdx`` 时自动安装，幂等。
去掉第三个包后 354 个候选主站里 117 台可用（原 11 台）。

实时分时 ``get_minute_time_data``（2026-10-08）：同一批主站对 ``0x051d`` 的应答也换了框架——
``行数(2) + 00 00 + 市场(1) + 代码(6) + 一段变长的报价块 + 行数据``，行数据仍是和历史分时一样的
三个 varint（价差 / 保留 / 量）。tdxpy 的解析器从偏移 4 起直接读 varint，把 ``01 "600519"`` 当成了
第一行（首行价 0.01、量 48 = ``'0'``），之后整段乱价负量。这里按「市场+代码回显」识别新框架，
再从回显之后逐字节试探行起点：3×行数 个 varint 恰好消费到包尾、量非负、价格在 30% 带内即为真；
老框架（无回显）走原路径。116 台可用主站 2026-10-08 全部是新框架。
"""

from __future__ import annotations

import struct
from collections import OrderedDict

_FLAG = "_handshake_compat_no_cmd3"
_MT_FLAG = "_minute_time_compat_v2_framing"


def install() -> bool:
    try:
        from tdxpy.hq import TdxHq_API
        from tdxpy.parser.setup_commands import SetupCmd1, SetupCmd2
    except Exception:  # noqa: BLE001
        return False
    if getattr(TdxHq_API, _FLAG, False):
        return False

    def setup(self):
        SetupCmd1(self.client).call_api()
        SetupCmd2(self.client).call_api()

    setup._original = getattr(TdxHq_API, 'setup', None)  # 测试替身可能没有 setup
    TdxHq_API.setup = setup
    setattr(TdxHq_API, _FLAG, True)
    install_minute_time_compat()
    return True


def _varint_rows(body, start, num):
    from tdxpy.helper import get_price

    pos = start
    last = 0
    rows = []
    for _ in range(num):
        price_raw, pos = get_price(body, pos)
        _reserved, pos = get_price(body, pos)
        vol, pos = get_price(body, pos)
        last += price_raw
        rows.append((last, vol))
    return rows, pos


def find_minute_time_rows(body, num, first=11):
    """新框架里行数据的起点：报价块是变长的（混有 4 字节定长字段），不能按固定偏移跳。

    从 ``first`` 起逐字节试探：``3*num`` 个 varint 恰好消费到包尾、量全部非负、价格为正且
    最高/最低在 1.3 倍以内，才算行起点。找不到返回 None（调用方必须响亮失败，不能吐乱价）。
    """
    for start in range(first, len(body)):
        try:
            rows, end = _varint_rows(body, start, num)
        except (IndexError, struct.error):
            continue
        if end != len(body):
            continue
        prices = [r[0] for r in rows]
        vols = [r[1] for r in rows]
        if min(vols) < 0 or min(prices) <= 0 or max(prices) > min(prices) * 1.3:
            continue
        return start
    return None


def parse_minute_time_body(body, market, code, coefficient):
    """实时分时应答 → [{'price', 'vol'}, ...]，同时认老框架与 2026 新框架。"""
    body = bytes(body)
    if len(body) < 2:
        return []
    (num,) = struct.unpack("<H", body[:2])
    if num == 0:
        return []
    echo = None
    if market is not None and code:
        code_bytes = code.encode("utf-8") if isinstance(code, str) else bytes(code)
        echo = bytes([int(market) & 0xFF]) + code_bytes[:6]
    if echo is not None and body[4:11] == echo:
        start = find_minute_time_rows(body, num, first=11)
        if start is None:
            raise ValueError(
                "minute-time packet with market/code echo but no recognizable rows "
                f"(num={num}, len={len(body)})"
            )
    else:
        start = 4
    rows, _ = _varint_rows(body, start, num)
    return [OrderedDict([("price", float(last) * coefficient), ("vol", vol)]) for last, vol in rows]


def install_minute_time_compat() -> bool:
    try:
        from tdxpy.parser.std.get_minute_time_data import GetMinuteTimeData
    except Exception:  # noqa: BLE001
        return False
    if getattr(GetMinuteTimeData, _MT_FLAG, False):
        return False
    original_set_params = GetMinuteTimeData.setParams

    def setParams(self, market, code):
        original_set_params(self, market, code)
        self._compat_market = int(market)
        self._compat_code = code.encode("utf-8") if isinstance(code, str) else bytes(code)

    def parseResponse(self, body_buf):
        return parse_minute_time_body(
            body_buf,
            getattr(self, "_compat_market", None),
            getattr(self, "_compat_code", None),
            self.coefficient,
        )

    setParams._original = original_set_params
    parseResponse._original = GetMinuteTimeData.parseResponse
    GetMinuteTimeData.setParams = setParams
    GetMinuteTimeData.parseResponse = parseResponse
    setattr(GetMinuteTimeData, _MT_FLAG, True)
    return True


def new_hq_api(**kwargs):
    """拿一个已装握手补丁的标准行情客户端。上层应通过这里而不是直接 import tdxpy。"""

    install()
    install_minute_time_compat()
    from tdxpy.hq import TdxHq_API

    return TdxHq_API(**kwargs)


install()
install_minute_time_compat()
