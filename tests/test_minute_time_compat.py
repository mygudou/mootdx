"""实时分时新框架解析（2026-10-08）：市场+代码回显 + 变长报价块 + varint 行。"""

import struct
from collections import OrderedDict

import pytest

import mootdx  # noqa: F401  触发 contrib.tdxpy_compat 安装
from mootdx.contrib import tdxpy_compat

# 2026-10-08 10:2x 从 123.125.108.101 抓到的 600519 实时分时应答（52 行）。
LIVE_BODY = bytes.fromhex(
    "340000000136303035313999038e9a0f98149c0b850ee605b3d5cf09ce9a0fb38c010378d3854ea34c9140008cad385e4101035f000a046802010d8c0da29a0f9cff02a91bf702c2ad01b60a04d345af059001f61d87038b058703a102fa011a9a0381038f0bbd0245870ea802d30497019e0337d6028a026fcd03bf0228fc029d02d302fe088804dd01ed138304c901f80f8903a302e00cb9022bec029801ec02f31db7059803cb039f01c602c502aa0173ee05b101a401f0039201e501fb03990177f6049a012fdd05ae01a901d50da7031cd401850136c7019501e9021aa501830276371e0f97018402b801bf016989018201e801102d72de01980193021788014f33387f0f378601393fc101223acd017898010a7680019501503a340b3fde014fa9016f703645d7018d018102de04a706ce01003c2a0fba0120378f01c901451f"
)


def _varint(v: int) -> bytes:
    neg = v < 0
    v = abs(v)
    out = [(v & 0x3F) | (0x40 if neg else 0) | (0x80 if (v >> 6) else 0)]
    v >>= 6
    while v:
        out.append((v & 0x7F) | (0x80 if (v >> 7) else 0))
        v >>= 7
    return bytes(out)


def _old_body(rows):
    body = struct.pack("<H", len(rows)) + b"\x00\x00"
    last = 0
    for price, vol in rows:
        body += _varint(price - last) + _varint(0) + _varint(vol)
        last = price
    return body


def test_new_framing_decodes_to_the_true_minute_series():
    rows = tdxpy_compat.parse_minute_time_body(LIVE_BODY, 1, "600519", 0.01)
    assert len(rows) == 52
    assert [(round(r["price"], 2), r["vol"]) for r in rows[:3]] == [
        (1245.78, 1769),
        (1243.95, 694),
        (1243.99, 367),
    ]
    assert (round(rows[-1]["price"], 2), rows[-1]["vol"]) == (1245.58, 31)
    assert min(r["vol"] for r in rows) >= 0


def test_old_framing_still_parses_from_offset_four():
    body = _old_body([(124578, 1769), (124395, 694), (124399, 367)])
    rows = tdxpy_compat.parse_minute_time_body(body, 1, "600519", 0.01)
    assert [(round(r["price"], 2), r["vol"]) for r in rows] == [
        (1245.78, 1769),
        (1243.95, 694),
        (1243.99, 367),
    ]


def test_echo_without_recognizable_rows_fails_loudly_instead_of_garbage():
    body = struct.pack("<H", 3) + b"\x00\x00" + b"\x01600519" + b"\xff" * 5
    with pytest.raises(ValueError, match="no recognizable rows"):
        tdxpy_compat.parse_minute_time_body(body, 1, "600519", 0.01)


def test_tdxpy_parser_class_is_patched_and_idempotent():
    from tdxpy.parser.std.get_minute_time_data import GetMinuteTimeData

    assert getattr(GetMinuteTimeData, tdxpy_compat._MT_FLAG, False) is True
    assert tdxpy_compat.install_minute_time_compat() is False  # 已装，不重复打

    class _Client:
        pass

    parser = GetMinuteTimeData(_Client())
    parser.setParams(1, "600519")
    assert parser._compat_market == 1 and parser._compat_code == b"600519"
    rows = parser.parseResponse(LIVE_BODY)
    assert isinstance(rows[0], OrderedDict) and round(rows[0]["price"], 2) == 1245.78
