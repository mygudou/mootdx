"""新一代行情主站拒绝 tdxpy 第三个握手包（2026-09-30）：import mootdx 后只发前两个。"""

import struct


class _FakeSocketClient:
    """最小 socket 替身：BaseParser 会累加这些计数器，所以都要有。"""

    def __init__(self):
        self.sent = []
        self.send_pkg_num = self.recv_pkg_num = 0
        self.send_pkg_bytes = self.recv_pkg_bytes = 0
        self.last_api_send_bytes = self.last_api_recv_bytes = 0
        self.first_pkg_send_time = None

    def send(self, pkg):
        self.sent.append(bytes(pkg))
        return len(pkg)

    def recv(self, n):  # 16 字节头（体长 1）+ 1 字节体
        if n == 16:
            return b'\xb1\xcb\x74\x00' + b'\x00' * 8 + struct.pack('<HH', 1, 1)
        return b'\x01'


def test_import_mootdx_installs_handshake_compat():
    import mootdx  # noqa: F401
    from tdxpy.hq import TdxHq_API

    assert getattr(TdxHq_API, '_handshake_compat_no_cmd3', False) is True


def test_setup_sends_only_the_two_0x000d_packets():
    import mootdx  # noqa: F401
    from tdxpy.hq import TdxHq_API

    api = TdxHq_API.__new__(TdxHq_API)
    api.client = _FakeSocketClient()
    api.setup()

    types = [pkg[10:12] for pkg in api.client.sent]
    assert types == [b'\x0d\x00', b'\x0d\x00'], types
    assert [pkg[12] for pkg in api.client.sent] == [1, 2]
    # 0x0fdb（旧客户端标识）绝不能再发：新一代主站会回「客户端与行情主站不匹配,不能使用!」
    assert not any(pkg[10:12] == b'\xdb\x0f' for pkg in api.client.sent)


def test_install_is_idempotent():
    from mootdx.contrib import tdxpy_compat
    from tdxpy.hq import TdxHq_API

    first = TdxHq_API.setup
    assert tdxpy_compat.install() is False
    assert TdxHq_API.setup is first
