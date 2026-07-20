"""server() 必须按响应时间排序并应用 limit —— 不管 console 开不开。

历史 bug: 排序/limit 只在 console=True 分支里做，导致 bestip(console=False)
（即 Quotes.factory(bestip=True) 和 config.setup 自动选优）选出来的是
"列表序第一个活的服务器"，不是最快的。
"""
import importlib

server_mod = importlib.import_module('mootdx.server')


def _fake_hosts():
    return [
        {'addr': '1.1.1.1', 'port': 7709, 'time': 0, 'site': 'slow'},
        {'addr': '2.2.2.2', 'port': 7709, 'time': 0, 'site': 'dead'},
        {'addr': '3.3.3.3', 'port': 7709, 'time': 0, 'site': 'fast'},
    ]


def test_server_sorts_by_latency_and_limits_without_console(monkeypatch):
    latency = {'1.1.1.1': 300.0, '2.2.2.2': None, '3.3.3.3': 20.0}

    def fake_connect(proxy):
        proxy['time'] = latency[proxy['addr']]
        return proxy

    monkeypatch.setitem(server_mod.hosts, 'HQ', _fake_hosts())
    monkeypatch.setattr(server_mod, 'connect', fake_connect)
    monkeypatch.setitem(server_mod.results, 'HQ', [])

    out = server_mod.server(index='HQ', limit=2, console=False, sync=True)

    # 最快的排第一（bestip() 取 data[0]），死服务器剔除，limit 生效
    assert out == [('3.3.3.3', 7709), ('1.1.1.1', 7709)]


def test_server_limit_none_returns_all_alive_sorted(monkeypatch):
    latency = {'1.1.1.1': 300.0, '2.2.2.2': 50.0, '3.3.3.3': 20.0}

    def fake_connect(proxy):
        proxy['time'] = latency[proxy['addr']]
        return proxy

    monkeypatch.setitem(server_mod.hosts, 'HQ', _fake_hosts())
    monkeypatch.setattr(server_mod, 'connect', fake_connect)
    monkeypatch.setitem(server_mod.results, 'HQ', [])

    out = server_mod.server(index='HQ', limit=None, console=False, sync=True)

    assert out == [('3.3.3.3', 7709), ('2.2.2.2', 7709), ('1.1.1.1', 7709)]
