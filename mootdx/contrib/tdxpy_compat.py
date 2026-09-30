"""tdxpy 握手兼容：新一代通达信行情主站拒绝第三个握手包（2026-09-30）。

tdxpy 的 ``TdxHq_API.setup`` 依次发 ``0x000d/01``、``0x000d/02`` 和 ``0x0fdb`` + 32 字节
旧客户端标识。新一代主站（101.x / 111.x / 114.141.x / 123.125.108.x …）对第三个包回
「客户端与行情主站不匹配,不能使用!」，之后 K 线 / 批量行情 / F10 目录全部返回空，
看起来像「连得上但报价为空」的僵尸——bestip 会把它们全部判死。老主站有没有第三个包
都一样。eltdx、injoyai/tdx 只发 ``0x000d/01``（+心跳）就能用所有主站。

这里把 ``setup`` 改成只发前两个包。``import mootdx`` 时自动安装，幂等；alphaquant 侧
``app/services/tdx_handshake_compat.py`` 用同一个标记，互不重复打。
去掉第三个包后 354 个候选主站里 117 台可用（原 11 台）。
"""

from __future__ import annotations

_FLAG = "_handshake_compat_no_cmd3"


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

    setup._original = TdxHq_API.setup
    TdxHq_API.setup = setup
    setattr(TdxHq_API, _FLAG, True)
    return True


install()
