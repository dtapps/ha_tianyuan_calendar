"""太阳位置（纬度参与计算）单元测试。

覆盖：赤纬近似下的高度角/方位角、日出日落换算、夜间负值、极昼极夜边界。
"""
from __future__ import annotations

import importlib.util
import os
from datetime import datetime

import pytest

# 计算太阳位置类为纯天文函数，仅依赖 lunar_python，不依赖 homeassistant。
# 但 custom_components 父包的 __init__ 会导入 homeassistant，导致无 HA 环境无法收集测试。
# 故直接按文件路径加载本模块，做独立单元测试（与运行/集成环境解耦）。
_路径 = os.path.join(
    os.path.dirname(__file__), "..",
    "custom_components", "tianyuan_calendar_duo", "tianyuan", "lifa", "lunar_logic.py",
)
_spec = importlib.util.spec_from_file_location("lunar_logic_standalone", os.path.abspath(_路径))
_模块 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_模块)
天元农历逻辑类 = _模块.天元农历逻辑类


def _高度角(结果: dict) -> float:
    return float(结果["solar_altitude"].rstrip("°"))


def _方位角(结果: dict) -> float:
    return float(结果["solar_azimuth"].rstrip("°"))


def _白昼(结果: dict) -> float:
    return float(结果["daylight_duration"].split()[0])


def test_赤道春分正午_北京() -> None:
    """春分日真太阳时正午：赤纬≈0，高度角≈90-纬度，方位角应指向南方(≈180°)。"""
    真太阳时 = datetime(2026, 3, 21, 12, 0, 0)
    纬度, 经度 = 39.9, 116.4
    结果 = 天元农历逻辑类.计算太阳位置类(真太阳时, 纬度, 经度)

    # 春分赤纬≈0，正午太阳高度角≈ 90 - 纬度
    assert _高度角(结果) == pytest.approx(90 - 纬度, abs=1.0)
    # 北半球正午太阳在南方，方位角≈180°
    assert _方位角(结果) == pytest.approx(180, abs=2)
    # 春分附近白昼≈12 小时
    assert _白昼(结果) == pytest.approx(12, abs=0.5)
    # 北京经度下，日出/日落标准时应在 06/18 点附近
    assert 结果["sunrise"].startswith(("05", "06"))
    assert 结果["sunset"].startswith(("17", "18"))


def test_夜间_高度角为负() -> None:
    """真太阳时午夜：太阳位于地平线下，高度角应为负。"""
    真太阳时 = datetime(2026, 3, 21, 0, 0, 0)
    结果 = 天元农历逻辑类.计算太阳位置类(真太阳时, 39.9, 116.4)
    assert _高度角(结果) < 0


def test_极夜_高纬冬季() -> None:
    """高纬度冬至：太阳全天不升起，返回极夜提示。"""
    真太阳时 = datetime(2026, 12, 22, 12, 0, 0)
    结果 = 天元农历逻辑类.计算太阳位置类(真太阳时, 80.0, 0.0)
    assert "极夜" in 结果["sunrise"]
    assert "极夜" in 结果["sunset"]
    assert 结果["daylight_duration"] == "0 小时"


def test_极昼_高纬夏季() -> None:
    """高纬度夏至：太阳全天不落下，返回极昼提示。"""
    真太阳时 = datetime(2026, 6, 21, 12, 0, 0)
    结果 = 天元农历逻辑类.计算太阳位置类(真太阳时, 80.0, 0.0)
    assert "极昼" in 结果["sunrise"]
    assert "极昼" in 结果["sunset"]
    assert 结果["daylight_duration"] == "24 小时"


def test_经度影响日出标准时() -> None:
    """相同纬度下，不同经度换算出的本地标准时日出应不同。"""
    真太阳时 = datetime(2026, 6, 21, 12, 0, 0)
    东经 = 天元农历逻辑类.计算太阳位置类(真太阳时, 30.0, 120.0)["sunrise"]
    西经 = 天元农历逻辑类.计算太阳位置类(真太阳时, 30.0, 90.0)["sunrise"]
    # 西经 90° 比东经 120° 偏西 30°，地方时晚 2 小时，日出标准时应更晚
    assert 西经 > 东经
