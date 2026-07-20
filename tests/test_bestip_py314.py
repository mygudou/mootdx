"""bestip 在 Python 3.12+/3.14 下的两个 bug：

1. server(sync=False) 用 asyncio.get_event_loop() 起异步探测，3.14 起无运行
   循环时直接 RuntimeError —— `python -m mootdx bestip` 整个挂掉。
2. bestip() 探测失败时仍然 json.dump 默认配置，把用户已有的 BESTIP 清空。
"""
import importlib
import json

server_mod = importlib.import_module('mootdx.server')


def _fake_hosts():
    return [
        {'addr': '1.1.1.1', 'port': 7709, 'time': 0, 'site': 'slow'},
        {'addr': '3.3.3.3', 'port': 7709, 'time': 0, 'site': 'fast'},
    ]


def test_server_async_path_works_without_running_loop(monkeypatch):
    latency = {'1.1.1.1': 300.0, '3.3.3.3': 20.0}

    def fake_connect2(proxy, index='HQ'):
        proxy['time'] = latency[proxy['addr']]
        return proxy

    monkeypatch.setitem(server_mod.hosts, 'HQ', _fake_hosts())
    monkeypatch.setattr(server_mod, 'connect2', fake_connect2)
    monkeypatch.setitem(server_mod.results, 'HQ', [])

    out = server_mod.server(index='HQ', limit=5, console=False, sync=False)

    assert out == [('3.3.3.3', 7709), ('1.1.1.1', 7709)]


def test_bestip_preserves_existing_bestip_when_probe_fails(monkeypatch, tmp_path):
    config_file = tmp_path / 'config.json'
    existing = {
        'SERVER': {'HQ': [['老服务器', '218.6.170.47', 7709]]},
        'BESTIP': {'HQ': ['218.6.170.47', 7709], 'EX': '', 'GP': ''},
        'TDXDIR': 'C:/new_tdx',
    }
    config_file.write_text(json.dumps(existing), encoding='utf-8')

    def broken_server(**kwargs):
        raise RuntimeError('no event loop')

    monkeypatch.setattr(server_mod, 'get_config_path', lambda name: str(config_file))
    monkeypatch.setattr(server_mod, 'server', broken_server)

    server_mod.bestip(console=False, limit=5, sync=False)

    saved = json.loads(config_file.read_text(encoding='utf-8'))
    assert saved['BESTIP']['HQ'] == ['218.6.170.47', 7709], '探测失败不能清空已有 BESTIP'
