"""构造函数 fallback 建连必须用短超时（≤5s），连上后恢复用户的操作超时。

历史问题: connect(time_out=timeout) 直接用 15s 默认操作超时做建连超时；
fallback 列表里一个丢包黑洞服务器（如 119.147.212.81）就让每次实例化
卡满 15s 才轮到下一个。
"""
import importlib

quotes_mod = importlib.import_module('mootdx.quotes')


class _FakeSock:
    def __init__(self):
        self._closed = False
        self.timeouts = []

    def settimeout(self, t):
        self.timeouts.append(t)


class _FakeAPI:
    instances = []
    dead_ips = set()

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.client = _FakeSock()
        self.connect_calls = []
        type(self).instances.append(self)

    def connect(self, ip, port, time_out=None):
        self.connect_calls.append((ip, int(port), time_out))
        return ip not in type(self).dead_ips

    def close(self):
        pass


def _patch_servers(monkeypatch, servers):
    monkeypatch.setattr(quotes_mod, '_get_config_servers', lambda index: list(servers))
    monkeypatch.setattr(quotes_mod, '_get_config_server', lambda index: servers[0])
    monkeypatch.setattr(quotes_mod, '_remember_server', lambda index, server: None)


def setup_function():
    _FakeAPI.instances = []
    _FakeAPI.dead_ips = set()


def test_std_quotes_caps_connect_timeout_then_restores_op_timeout(monkeypatch):
    monkeypatch.setattr(quotes_mod, 'TdxHq_API', _FakeAPI)
    _patch_servers(monkeypatch, [('9.9.9.9', 7709)])

    std = quotes_mod.StdQuotes(timeout=15)

    api = _FakeAPI.instances[-1]
    _, _, connect_timeout = api.connect_calls[0]
    assert connect_timeout <= 5, '建连不该等满 15s 操作超时'
    assert api.client.timeouts and api.client.timeouts[-1] == 15, '连上后要恢复操作超时'
    assert std.server == ('9.9.9.9', 7709)


def test_std_quotes_small_timeout_used_as_is(monkeypatch):
    monkeypatch.setattr(quotes_mod, 'TdxHq_API', _FakeAPI)
    _patch_servers(monkeypatch, [('9.9.9.9', 7709)])

    quotes_mod.StdQuotes(timeout=3)

    api = _FakeAPI.instances[-1]
    assert api.connect_calls[0][2] == 3


def test_std_quotes_falls_back_past_dead_server_with_capped_timeout(monkeypatch):
    monkeypatch.setattr(quotes_mod, 'TdxHq_API', _FakeAPI)
    _FakeAPI.dead_ips = {'8.8.8.8'}
    _patch_servers(monkeypatch, [('8.8.8.8', 7709), ('9.9.9.9', 7709)])

    std = quotes_mod.StdQuotes(timeout=15)

    assert std.server == ('9.9.9.9', 7709)
    all_connects = [c for api in _FakeAPI.instances for c in api.connect_calls]
    assert all(t <= 5 for _, _, t in all_connects)


def test_ext_quotes_caps_connect_timeout_then_restores_op_timeout(monkeypatch):
    monkeypatch.setattr(quotes_mod, 'TdxExHq_API', _FakeAPI)
    _patch_servers(monkeypatch, [('7.7.7.7', 7720)])

    ext = quotes_mod.ExtQuotes(timeout=15)

    api = _FakeAPI.instances[-1]
    _, _, connect_timeout = api.connect_calls[0]
    assert connect_timeout <= 5
    assert api.client.timeouts and api.client.timeouts[-1] == 15
    assert ext.server == ('7.7.7.7', 7720)
