"""行情主站健康探针（四维）：连得上、报价非空、K 线非空、价格对。

背景（2026-07-20 / 2026-09-30）：
- 只看 TCP 建连或 ``get_security_count`` 会放过「能连、count 正常、K 线永远为空」的僵尸；
- 只看延迟会放过「连得上、答得快、价格却是旧的」的主站——``servertime`` 字段语义因标的而异
  （同一次响应里各标的相差十几分钟），不能拿它判新鲜，只能拿价格和独立源比。

这是 mootdx 拥有的唯一一套健康判法：``bestip`` 用它选站，上层选路器（alphaquant）用它做
后台探针。参考价来源通过 ``reference_prices`` 注入（签名 ``codes -> {code: price}``），
mootdx 本身不依赖任何外部 HTTP 源；不注入就跳过比价（``price_check='skipped'``），
注入了但拿不到参考价是 ``'unverified'``——两者都**不是**「价格错」。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, Mapping, Optional

ReferencePrices = Callable[[Iterable[str]], Mapping[str, object]]

#: 交叉比价用的流动性标的 (market, code)：深沪各一只大票 + 一只 ETF
DEFAULT_CANARIES: tuple[tuple[int, str], ...] = ((0, '000001'), (1, '600519'), (1, '510300'))
#: 两个源同一时刻的价差容差；超过就不是同一时刻的行情
PRICE_TOLERANCE = 0.003
#: K 线探针：000001 日线 2 根（category 9 = 日线）
BARS_PROBE = (9, 0, '000001', 0, 2)


@dataclass
class HostProbe:
    addr: str
    port: int
    ok: bool = False
    stage: str = 'connect'  # connect / quotes / bars / price / ok
    ms: Optional[float] = None
    price_check: str = 'skipped'  # skipped / unverified / agree / disagree
    detail: str = ''
    feed_prices: dict = field(default_factory=dict)

    @property
    def endpoint(self) -> tuple[str, int]:
        return self.addr, self.port


def price_agreement(
    feed_prices: Mapping[str, object],
    reference_prices: Mapping[str, object],
    *,
    tolerance: float = PRICE_TOLERANCE,
) -> tuple[Optional[bool], str]:
    """三态：True 一致 / False 多数标的价差超容差 / None 可比标的不足两只（无法判断）。"""

    comparable: list[tuple[str, float, float]] = []
    for code, ref in reference_prices.items():
        try:
            r = float(ref)  # type: ignore[arg-type]
            f = float(feed_prices.get(code))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if r > 0 and f > 0:
            comparable.append((code, f, r))
    if len(comparable) < 2:
        return None, f'only {len(comparable)} comparable canary'
    mismatched = [(c, f, r) for c, f, r in comparable if abs(f - r) / r > tolerance]
    if len(mismatched) * 2 >= len(comparable):
        detail = '; '.join(f'{c} feed {f} vs ref {r}' for c, f, r in mismatched)
        return False, f'{len(mismatched)}/{len(comparable)} canaries disagree: {detail}'
    return True, f'{len(comparable) - len(mismatched)}/{len(comparable)} canaries agree'


def servertime_looks_stale(servertimes: Iterable[object], now: datetime) -> tuple[bool, str]:
    """报价包 ``servertime`` 是否**可疑**（只是线索，裁决交给 ``price_agreement``）。

    连续竞价落后 >120s、午休停在 11:29 前、收盘后停在 14:59 前算可疑；开盘前或没有
    可解析的 servertime 不可疑。``now`` 必须是上海时间。
    """

    stamps = []
    for value in servertimes:
        text = str(value or '').strip()
        if not text:
            continue
        try:
            hh, mm, ss = text.split(':')[:3]
            stamps.append(now.replace(hour=int(hh), minute=int(mm), second=int(float(ss)), microsecond=0))
        except (ValueError, AttributeError):
            continue
    if not stamps:
        return False, 'no servertime'
    latest = max(stamps)
    hm = (now.hour, now.minute)
    lag = (now - latest).total_seconds()
    weekday = now.weekday() < 5
    if weekday and ((9, 30) <= hm < (11, 30) or (13, 0) <= hm < (15, 0)):
        if lag > 120:
            return True, f'servertime {latest:%H:%M:%S} lags wall clock by {lag:.0f}s during trading'
        return False, f'lag {lag:.0f}s'
    if weekday and (11, 30) <= hm < (13, 0):
        if (latest.hour, latest.minute) < (11, 29):
            return True, f'servertime {latest:%H:%M:%S} stuck before the morning close'
        return False, 'lunch break'
    if hm >= (15, 0):
        if (latest.hour, latest.minute) < (14, 59):
            return True, f'servertime {latest:%H:%M:%S} stuck before the closing auction'
        return False, 'after close'
    return False, 'outside session'


def _new_api():
    from mootdx.contrib.tdxpy_compat import new_hq_api

    return new_hq_api(raise_exception=True)


def probe_host(
    addr: str,
    port: int = 7709,
    *,
    timeout: float = 3.0,
    reference_prices: Optional[ReferencePrices] = None,
    canaries: Iterable[tuple[int, str]] = DEFAULT_CANARIES,
    tolerance: float = PRICE_TOLERANCE,
) -> HostProbe:
    """对一台行情主站做四维体检；任何一步失败 ``ok=False`` 并在 ``stage``/``detail`` 说明。"""

    canaries = tuple(canaries)
    probe = HostProbe(addr=addr, port=int(port))
    api = _new_api()
    started = time.perf_counter()
    try:
        if not api.connect(addr, int(port), time_out=timeout):
            probe.detail = 'connect failed'
            return probe
        probe.stage = 'quotes'
        quotes = api.get_security_quotes(list(canaries)) or []
        feed = {str(q.get('code')): q.get('price') for q in quotes if isinstance(q, dict)}
        probe.feed_prices = feed
        if len([p for p in feed.values() if p]) < 2:
            probe.detail = f'quotes empty ({len(quotes)} rows)'
            return probe
        probe.stage = 'bars'
        if not api.get_security_bars(*BARS_PROBE):
            probe.detail = 'stock bars empty'
            return probe
        probe.ms = round((time.perf_counter() - started) * 1000, 1)
        probe.stage = 'price'
        if reference_prices is None:
            probe.price_check = 'skipped'
        else:
            note = ''
            try:
                reference = dict(reference_prices([code for _, code in canaries]))
            except Exception as exc:  # noqa: BLE001 - 参考源挂了不等于主站坏了
                reference = {}
                note = f'; reference unavailable: {exc}'
            agreement, why = price_agreement(feed, reference, tolerance=tolerance)
            probe.price_check = {True: 'agree', False: 'disagree', None: 'unverified'}[agreement]
            probe.detail = why + note
            if agreement is False:
                return probe
        probe.ok = True
        probe.stage = 'ok'
        return probe
    except Exception as exc:  # noqa: BLE001
        probe.detail = f'{type(exc).__name__}: {str(exc)[:80]}'
        return probe
    finally:
        try:
            api.disconnect()
        except Exception:  # noqa: BLE001
            pass


def probe_hosts(
    hosts: Iterable[tuple[str, int]],
    *,
    timeout: float = 3.0,
    workers: int = 24,
    reference_prices: Optional[ReferencePrices] = None,
) -> list[HostProbe]:
    """并发体检一批主站；结果按 ok 优先、延迟升序。"""

    hosts = list(dict.fromkeys((str(a), int(p)) for a, p in hosts))
    if not hosts:
        return []
    results: list[HostProbe] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(hosts)))) as pool:
        futures = {
            pool.submit(probe_host, a, p, timeout=timeout, reference_prices=reference_prices): (a, p)
            for a, p in hosts
        }
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda r: (not r.ok, r.ms if r.ms is not None else 1e9, r.addr))
    return results
