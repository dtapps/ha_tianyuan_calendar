"""日历逻辑引擎测试：多行历书事件拆分 / 生日自动转换 / 单日摘要包装。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from lunar_python import Lunar, Solar

from custom_components.tianyuan_calendar_duo.tianyuan import (
    天元日历逻辑类,
    天元农历逻辑类,
)

from .helpers import 真阳历, 真农历

目标日 = date(2026, 2, 17)  # 丙午年正月初一，春节


def _真实日数据(年: int = 2026, 月: int = 2, 日: int = 17) -> dict:
    """用真实历法数据构造协调器单日包的等价结构。"""
    时刻 = datetime(年, 月, 日, 12, 0)
    农历 = Lunar.fromDate(时刻)
    阳历 = Solar.fromDate(时刻)
    return {
        "农历": 农历,
        "阳历": 阳历,
        "假期数据": 天元农历逻辑类.获取假期数据类(农历, 阳历, 时刻),
        "节气数据": 天元农历逻辑类.获取节气数据类(农历, 阳历),
        "全量属性数据": 天元农历逻辑类.获取全量属性数据类(农历, 阳历),
    }


# ==================== 多行历书事件 ====================


def test_包装多行事件_真实数据拆成四行() -> None:
    事件 = 天元日历逻辑类.包装多行历书事件法(目标日, _真实日数据())

    assert len(事件) == 4
    assert [e.location for e in 事件] == ["农历日期", "节日节气", "年干支", "月日干支"]
    assert all(e.start == 目标日 for e in 事件)
    assert all(e.end == 目标日 + timedelta(days=1) for e in 事件)


def test_包装多行事件_农历行含物候月相九星() -> None:
    农历行 = 天元日历逻辑类.包装多行历书事件法(目标日, _真实日数据())[0]

    assert 农历行.summary == "正月初一"
    assert "【历法】农历 正月初一" in 农历行.description
    for 标签 in ("【物候】", "【月相】", "【季节】", "【九星】"):
        assert 标签 in 农历行.description


def test_包装多行事件_节日节气行拼接假期() -> None:
    """非交节当日节气名为空，标题只由假期标签构成。"""
    节日行 = 天元日历逻辑类.包装多行历书事件法(目标日, _真实日数据())[1]

    assert 节日行.summary == "[假] 春节"
    assert "【节日】[假] 春节" in 节日行.description
    assert "【性质】法定节假日" in 节日行.description
    assert "【时令】立春 2026-02-04 ➔ 雨水 2026-02-18" in 节日行.description


def test_包装多行事件_交节当日标题带节气名() -> None:
    """立春当日节气名非空，标题由「节气名 | 假期标签」拼接。"""
    立春日 = date(2026, 2, 4)
    事件 = 天元日历逻辑类.包装多行历书事件法(立春日, _真实日数据(2026, 2, 4))

    节日行 = 事件[1]
    assert 节日行.summary == "立春"
    assert "【节日】立春" in 节日行.description


def test_包装多行事件_干支两行分别极简与详列() -> None:
    事件 = 天元日历逻辑类.包装多行历书事件法(目标日, _真实日数据())

    年行, 月日行 = 事件[2], 事件[3]
    assert 年行.summary == "丙午马年"
    assert "【岁次】丙午马年" in 年行.description
    assert "【日禄】" in 年行.description

    assert 月日行.summary == "庚寅月 壬戌日"
    for 标签 in ("【建除】", "【宜】", "【忌】", "【冲煞】", "【彭祖】", "【神煞】"):
        assert 标签 in 月日行.description


def test_包装多行事件_空数据只保留农历占位行() -> None:
    事件 = 天元日历逻辑类.包装多行历书事件法(目标日, {})

    assert len(事件) == 1
    assert 事件[0].summary == ""
    assert 事件[0].location == "农历日期"


def test_包装多行事件_无节气无假期只剩农历行() -> None:
    日数据 = {"全量属性数据": {"农历": "九月十八", "天干地支": "丙午年 戊戌月"}}
    事件 = 天元日历逻辑类.包装多行历书事件法(目标日, 日数据)

    assert len(事件) == 1  # 干支不足三段，不拆干支行
    assert 事件[0].summary == "九月十八"


def test_包装多行事件_有节气无假期为普通工作日性质() -> None:
    日数据 = {
        "节气数据": {
            "节气名": "立冬",
            "attributes": {"上一节气": "霜降", "下一节气": "小雪"},
        },
    }
    事件 = 天元日历逻辑类.包装多行历书事件法(目标日, 日数据)

    assert len(事件) == 2
    assert 事件[1].summary == "立冬"
    assert "【性质】普通工作日" in 事件[1].description


def test_包装多行事件_调休补班性质() -> None:
    日数据 = {
        "假期数据": {
            "显示列表": ["[班] 春节调休"],
            "attributes": {"假期信息": {"名称": "春节调休", "是否工作日": "是"}},
        },
    }
    事件 = 天元日历逻辑类.包装多行历书事件法(目标日, 日数据)

    assert "【性质】调休工作日 (补班)" in 事件[1].description


def test_包装多行事件_周末休息性质() -> None:
    日数据 = {
        "假期数据": {
            "显示列表": ["周末"],
            "attributes": {"假期信息": {"名称": "无假期", "是否工作日": "否"}},
        },
    }
    事件 = 天元日历逻辑类.包装多行历书事件法(目标日, 日数据)

    assert "【性质】周末休息" in 事件[1].description


# ==================== 生日事件 ====================


def _生日对象(年: int = 2026, 月: int = 2, 日: int = 17) -> tuple[Lunar, Solar]:
    时刻 = datetime(年, 月, 日, 12, 0)
    return Lunar.fromDate(时刻), Solar.fromDate(时刻)


def test_生日_公历生日命中() -> None:
    农历, 阳历 = _生日对象()

    事件 = 天元日历逻辑类.检测并包装生日事件集类(
        目标日, 农历, 阳历, ["张三 1990-02-17"]
    )

    assert len(事件) == 1
    assert 事件[0].summary == "🎂 张三 的公历生日"
    assert "【公历生日】1990-02-17" in 事件[0].description
    assert 事件[0].location == "天元历书·生日提醒"
    assert 事件[0].end == 目标日 + timedelta(days=1)


def test_生日_农历生日命中并自动换算公历() -> None:
    农历, 阳历 = _生日对象()
    当前农历月日 = (农历.getMonth(), 农历.getDay())

    事件 = 天元日历逻辑类.检测并包装生日事件集类(
        目标日,
        农历,
        阳历,
        [f"李四 1985-{当前农历月日[0]:02d}-{当前农历月日[1]:02d} 农历"],
    )

    assert len(事件) == 1
    assert 事件[0].summary == "🎂 李四 的农历生日"
    assert "【农历生日】" in 事件[0].description
    assert "【对应公历】" in 事件[0].description


def test_生日_同一人公历与农历同日会出两条() -> None:
    农历, 阳历 = _生日对象()
    当前农历月日 = (农历.getMonth(), 农历.getDay())
    配置 = [
        "张三 1990-02-17",
        f"张三 1985-{当前农历月日[0]:02d}-{当前农历月日[1]:02d} 农历",
    ]

    事件 = 天元日历逻辑类.检测并包装生日事件集类(目标日, 农历, 阳历, 配置)

    assert len(事件) == 2
    assert 事件[0].summary.endswith("公历生日") or 事件[0].summary.endswith("农历生日")
    assert {e.summary for e in 事件} == {"🎂 张三 的公历生日", "🎂 张三 的农历生日"}


def test_生日_无效条目全部跳过() -> None:
    农历, 阳历 = _生日对象()
    配置 = ["随便写点什么", "1990-02-17", "王五 不是日期", "赵六 1990-13-45"]

    assert 天元日历逻辑类.检测并包装生日事件集类(目标日, 农历, 阳历, 配置) == []


def test_生日_空配置或缺对象返回空() -> None:
    农历, 阳历 = _生日对象()

    assert 天元日历逻辑类.检测并包装生日事件集类(目标日, 农历, 阳历, []) == []
    assert (
        天元日历逻辑类.检测并包装生日事件集类(目标日, None, 阳历, ["张三 2026-02-17"])
        == []
    )
    assert (
        天元日历逻辑类.检测并包装生日事件集类(目标日, 农历, None, ["张三 2026-02-17"])
        == []
    )


def test_生日_不相关的生日不出事件() -> None:
    农历, 阳历 = _生日对象()

    事件 = 天元日历逻辑类.检测并包装生日事件集类(
        目标日, 农历, 阳历, ["张三 1990-06-01"]
    )

    assert 事件 == []


# ==================== 单日摘要包装 ====================


def test_包装单日生日摘要_命中时合并姓名与描述() -> None:
    农历, 阳历 = _生日对象()

    摘要 = 天元日历逻辑类.包装单日生日摘要类(
        目标日, 农历, 阳历, ["张三 1990-02-17", "李四 1991-02-17"]
    )

    assert 摘要 is not None
    assert 摘要["summary"] == "🎂 张三 的公历生日 | 🎂 李四 的公历生日"
    assert "【公历生日】" in 摘要["description"]
    assert 摘要["location"] == "家人生日"
    assert 摘要["start"] == 目标日
    assert 摘要["end"] == 目标日 + timedelta(days=1)


def test_包装单日生日摘要_无生日返回None() -> None:
    农历, 阳历 = _生日对象()
    assert 天元日历逻辑类.包装单日生日摘要类(目标日, 农历, 阳历, []) is None


def test_包装单日摘要事件_真实数据() -> None:
    摘要 = 天元日历逻辑类.包装单日摘要事件法(_真实日数据(), 目标日)

    assert 摘要 is not None
    assert 摘要["summary"] == "正月初一"
    assert 摘要["location"] == _真实日数据()["全量属性数据"]["东方星宿"]
    for 标签 in ("〖干支〗", "〖建除〗", "〖神煞〗", "〖彭祖〗", "〖宜〗", "〖忌〗"):
        assert 标签 in 摘要["description"]
    assert 摘要["end"] == 目标日 + timedelta(days=1)


def test_包装单日摘要事件_无属性返回None() -> None:
    assert 天元日历逻辑类.包装单日摘要事件法({}, 目标日) is None
    assert 天元日历逻辑类.包装单日摘要事件法({"全量属性数据": {}}, 目标日) is None


# ==================== 假期判定分支 ====================


def test_假期_调休上班日显示补班标签() -> None:
    """2026-01-04 为元旦调休补班日。"""
    时刻 = datetime(2026, 1, 4, 12, 0)
    农历, 阳历 = Lunar.fromDate(时刻), Solar.fromDate(时刻)

    数据 = 天元农历逻辑类.获取假期数据类(农历, 阳历, 时刻)

    assert 数据["state"] == "元旦节调休"
    assert 数据["是否工作日"] == "是"
    assert "[班] 元旦节调休" in 数据["显示列表"]
    assert 数据["attributes"]["假期信息"]["类型"] == "工作日"


def test_假期_非法定假日但有节日时列出节日() -> None:
    """2026-03-08 妇女节：无国家法定安排，节日仍要显示。"""
    时刻 = datetime(2026, 3, 8, 12, 0)
    农历, 阳历 = Lunar.fromDate(时刻), Solar.fromDate(时刻)

    数据 = 天元农历逻辑类.获取假期数据类(农历, 阳历, 时刻)

    assert 数据["attributes"]["假期信息"]["名称"] == "无假期"
    assert any("妇女节" in 项 for 项 in 数据["显示列表"])


def test_假期_法定假日不重复列出同名节日() -> None:
    """春节既是法定假日又是农历节日，显示列表只保留 [假] 前缀那一条。"""
    时刻 = datetime(2026, 2, 17, 12, 0)
    农历, 阳历 = Lunar.fromDate(时刻), Solar.fromDate(时刻)

    数据 = 天元农历逻辑类.获取假期数据类(农历, 阳历, 时刻)

    assert 数据["显示列表"].count("[假] 春节") == 1
    assert "春节" not in 数据["显示列表"]
