"""TianYuan 测试辅助：构造轻量 mock coordinator 与 entry。

这些 helper 不依赖真实的 lunar_python / assets.dat，仅用于实体纯逻辑断言，
可在安装了 homeassistant 测试框架（pytest-homeassistant）的环境中运行。
"""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from lunar_python import Lunar, Solar


def make_entry(entry_id: str = "test_entry") -> SimpleNamespace:
    """返回最小可用的 entry 替身，仅提供实体构造所需的 entry_id。"""
    return SimpleNamespace(entry_id=entry_id)


class 阳历替身:
    """阳历替身：只实现被测代码用到的 Solar 取值接口。"""

    def __init__(self, 年: int = 2026, 月: int = 1, 日: int = 1) -> None:
        self._年 = 年
        self._月 = 月
        self._日 = 日

    def getYear(self) -> int:  # noqa: N802 - 对齐 lunar_python 接口
        return self._年

    def getMonth(self) -> int:  # noqa: N802
        return self._月

    def getDay(self) -> int:  # noqa: N802
        return self._日

    def toYmd(self) -> str:  # noqa: N802
        return f"{self._年}-{self._月:02d}-{self._日:02d}"

    def toString(self) -> str:  # noqa: N802
        return self.toYmd()


class 农历替身:
    """农历替身：按关键字覆盖任意取数接口，未覆盖的走默认值。

    被测的术数/岐黄引擎只通过 duck typing 调 lunar_python.Lunar 的方法，
    因此用显式默认值构造可控输入，避免依赖真实历法数据。
    """

    def __init__(
        self,
        *,
        月: int = 1,
        日: int = 1,
        月中文: str = "正",
        年干: str = "甲",
        年支: str = "子",
        年干索引: int = 0,
        年支索引: int = 0,
        日干: str = "甲",
        日支: str = "子",
        日干支: str | None = None,
        时干: str = "甲",
        时支: str = "子",
        时支索引: int = 0,
        阳历: 阳历替身 | None = None,
        节气表: dict[str, Any] | None = None,
    ) -> None:
        self._月 = 月
        self._日 = 日
        self._月中文 = 月中文
        self._年干 = 年干
        self._年支 = 年支
        self._年干索引 = 年干索引
        self._年支索引 = 年支索引
        self._日干 = 日干
        self._日支 = 日支
        self._日干支 = 日干支 if 日干支 is not None else f"{日干}{日支}"
        self._时干 = 时干
        self._时支 = 时支
        self._时支索引 = 时支索引
        self._阳历 = 阳历 or 阳历替身()
        self._节气表 = 节气表 or {}

    # --- 基础 ---
    def getMonth(self) -> int:  # noqa: N802
        return self._月

    def getDay(self) -> int:  # noqa: N802
        return self._日

    def getMonthInChinese(self) -> str:  # noqa: N802
        return self._月中文

    def getYearGan(self) -> str:  # noqa: N802
        return self._年干

    def getYearZhi(self) -> str:  # noqa: N802
        return self._年支

    def getYearGanIndex(self) -> int:  # noqa: N802
        return self._年干索引

    def getYearZhiIndex(self) -> int:  # noqa: N802
        return self._年支索引

    def getYearGanExact(self) -> str:  # noqa: N802
        return self._年干

    def getYearZhiExact(self) -> str:  # noqa: N802
        return self._年支

    # --- 日 ---
    def getDayGanExact2(self) -> str:  # noqa: N802
        return self._日干

    def getDayZhiExact2(self) -> str:  # noqa: N802
        return self._日支

    def getDayInGanZhiExact2(self) -> str:  # noqa: N802
        return self._日干支

    # --- 时 ---
    def getTimeGan(self) -> str:  # noqa: N802
        return self._时干

    def getTimeZhi(self) -> str:  # noqa: N802
        return self._时支

    def getTimeZhiIndex(self) -> int:  # noqa: N802
        return self._时支索引

    def getTimeInGanZhi(self) -> str:  # noqa: N802
        return f"{self._时干}{self._时支}"

    # --- 附属对象 ---
    def getSolar(self) -> 阳历替身:  # noqa: N802
        return self._阳历

    def getJieQiTable(self) -> dict[str, Any]:  # noqa: N802
        return self._节气表


def 真农历(时刻: datetime) -> Lunar:
    """构造真实农历对象（依赖 lunar_python，无 HA 依赖）。"""
    return Lunar.fromDate(时刻)


def 真阳历(时刻: datetime) -> Solar:
    """构造真实阳历对象（依赖 lunar_python，无 HA 依赖）。"""
    return Solar.fromDate(时刻)


def 固定日期(年: int = 2026, 月: int = 10, 日: int = 27) -> date:
    """测试用的固定日期，避免 date.today() 带来的不确定性。"""
    return date(年, 月, 日)


class FakeLunar:
    """模拟 lunar_python.Lunar 在 main_lunar 取值时用到的方法。"""

    def __init__(self, month: str = "七", day: str = "廿三") -> None:
        self._month = month
        self._day = day

    def getMonthInChinese(self) -> str:
        return self._month

    def getDayInChinese(self) -> str:
        return self._day


def make_coordinator(data: dict | None = None, **kwargs) -> MagicMock:
    """构造一个 MagicMock 充当 coordinator，提供各实体读取所需的属性。"""
    co = MagicMock()
    co.data = data
    co.last_update_success = True
    co.性别 = kwargs.get("性别", "男")
    co.选中卦名 = kwargs.get("选中卦名", None)
    co.辅行诀选中大类 = kwargs.get("辅行诀选中大类", "肝")
    co.辅行诀选中症状 = kwargs.get("辅行诀选中症状", "胁下痛")
    co.伤寒选中六经 = kwargs.get("伤寒选中六经", "太阳")
    co.伤寒选中证型 = kwargs.get("伤寒选中证型", "太阳-表寒实")
    co.伤寒选中方名 = kwargs.get("伤寒选中方名", "麻黄汤")
    co.六爻输入字符串 = kwargs.get("六爻输入字符串", "阳阳阳阴阴阴")
    co.查看日期 = kwargs.get("查看日期", None)
    return co
