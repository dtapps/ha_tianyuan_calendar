"""协调器集成测试：用真实 hass + 真实 config entry 跑通整条数据管线。

与实体层的 mock 测试不同，这里不替掉 coordinator，而是让它真的去算：
日级基础数据 → 时级动态数据 → 实时覆盖，再把日历事件范围拉到用户视角。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.tianyuan_calendar_duo.const import (
    CONF_BIRTHDAYS,
    CONF_CALC_MODE,
    CONF_CUSTOM_LATITUDE,
    CONF_CUSTOM_LONGITUDE,
    CONF_ENABLE_QIHUANG,
    CONF_ENABLE_SHUSHU,
    CONF_REFRESH_INTERVAL,
    DOMAIN,
    MODE_ST,
    MODE_TST,
)
from custom_components.tianyuan_calendar_duo.coordinator import TianYuanCoordinator

基础日级键 = {
    "农历",
    "阳历",
    "假期数据",
    "节气数据",
    "全量属性数据",
    "四柱八字数据",
    "天干地支数据",
    "十二天神数据",
    "当日冲煞数据",
    "东方星宿数据",
}

实时覆盖键 = {
    "真太阳时",
    "实时模式",
    "性别",
    "真太阳时数据",
    "十二时辰数据",
    "四柱八字数据",
    "天干地支数据",
    "易经名称数据",
    "易经信息数据",
    "六爻爻法数据",
    "辅行诀结果数据",
    "伤寒结果数据",
}

岐黄键 = {
    "纳甲筮法数据",
    "纳子筮法数据",
    "灵龟八法数据",
    "飞腾八法数据",
    "迎随补泻数据",
    "六步气机数据",
    "年度运气总览数据",
}

术数键 = {"小六壬数据", "梅花易数数据", "皇极经世数据"}


async def _建条目(hass: HomeAssistant, **覆盖选项) -> object:
    """走真实配置流建一个条目，再按需覆盖选项。"""
    流程 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    结果 = await hass.config_entries.flow.async_configure(
        流程["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 39.9,
            CONF_CUSTOM_LONGITUDE: 116.4,
            CONF_REFRESH_INTERVAL: 1,
        },
    )
    entry = 结果["result"]
    if 覆盖选项:
        hass.config_entries.async_update_entry(
            entry, options={**dict(entry.options), **覆盖选项}
        )
    return entry


async def _建协调器(
    hass: HomeAssistant, entry, 刷新: bool = True
) -> TianYuanCoordinator:
    coordinator = TianYuanCoordinator(hass, entry, "9.9.9")
    if 刷新:
        await coordinator.async_refresh()
    return coordinator


@pytest.fixture
async def 协调器(hass: HomeAssistant) -> TianYuanCoordinator:
    entry = await _建条目(hass)
    coordinator = await _建协调器(hass, entry)
    try:
        yield coordinator
    finally:
        await coordinator.async_shutdown()


# ==================== 数据管线 ====================


async def test_刷新后产出日级与实时全部键(协调器: TianYuanCoordinator) -> None:
    assert 协调器.last_update_success is True
    数据 = 协调器.data

    assert 基础日级键 <= set(数据)
    assert 实时覆盖键 <= set(数据)
    assert 数据["实时模式"] is True
    assert 数据["性别"] == "男"
    assert isinstance(数据["真太阳时"], datetime)


async def test_真实数据内容合理性(协调器: TianYuanCoordinator) -> None:
    数据 = 协调器.data

    assert 数据["全量属性数据"]["农历"]
    assert 数据["全量属性数据"]["天干地支"].count("年") >= 1
    assert 数据["四柱八字数据"]["state"]
    assert 数据["真太阳时数据"]["state"]
    # 真太阳时属性回写实例经纬度，供前端核对定位
    assert 数据["真太阳时数据"]["attributes"]["longitude"] == pytest.approx(116.4)
    assert 数据["真太阳时数据"]["attributes"]["latitude"] == pytest.approx(39.9)
    # 术数未开启时没有梅花卦名，易经名称数据为 None（前端据此隐藏）
    assert 数据["易经名称数据"] is None
    assert 数据["六爻爻法数据"]["state"]
    assert 数据["辅行诀结果数据"]["state"]
    assert 数据["伤寒结果数据"]["state"] == "麻黄汤"


async def test_未开启岐黄术数时不产出相关键(协调器: TianYuanCoordinator) -> None:
    assert not (岐黄键 & set(协调器.data))
    assert not (术数键 & set(协调器.data))


async def test_开启岐黄与术数后补齐全部键(hass: HomeAssistant) -> None:
    entry = await _建条目(hass, **{CONF_ENABLE_QIHUANG: True, CONF_ENABLE_SHUSHU: True})
    coordinator = await _建协调器(hass, entry)
    try:
        assert 岐黄键 <= set(coordinator.data)
        assert 术数键 <= set(coordinator.data)
        for 键 in 岐黄键 | 术数键:
            assert coordinator.data[键]["state"], f"{键} 缺少 state"
        # 术数开启后梅花卦名可用于易经详注
        assert coordinator.data["易经名称数据"]
        assert coordinator.data["易经信息数据"]
    finally:
        await coordinator.async_shutdown()


@pytest.mark.parametrize("模式", [MODE_ST, MODE_TST])
async def test_两种计算模式均可产出数据(hass: HomeAssistant, 模式: str) -> None:
    entry = await _建条目(hass, **{CONF_CALC_MODE: 模式})
    coordinator = await _建协调器(hass, entry)
    try:
        assert coordinator.last_update_success is True
        assert coordinator.data["农历"] is not None
        assert coordinator.data["全量属性数据"]["农历"]
        assert coordinator.entry.options[CONF_CALC_MODE] == 模式
    finally:
        await coordinator.async_shutdown()


async def test_查看日期切换到历史日(协调器: TianYuanCoordinator) -> None:
    协调器.查看日期 = date(2026, 2, 17)
    await 协调器.async_refresh()

    assert 协调器.data["实时模式"] is False
    assert 协调器.data["全量属性数据"]["农历"] == "正月初一"


async def test_计算真太阳时按经度平移() -> None:
    coordinator = TianYuanCoordinator.__new__(TianYuanCoordinator)
    时刻 = dt_util.now().replace(microsecond=0)

    同经 = coordinator._计算真太阳时类(时刻, 120.0)
    西移 = coordinator._计算真太阳时类(时刻, 90.0)

    assert abs((同经 - 时刻).total_seconds()) <= 17 * 60  # 仅均时差
    # 经度每差 1° 偏移 4 分钟，30° 即 120 分钟
    assert ((同经 - 西移).total_seconds() / 60) == pytest.approx(120, abs=17)


# ==================== 状态写入（下拉框联动） ====================


async def test_写入辅行诀大类会重置症状(协调器: TianYuanCoordinator) -> None:
    协调器.async_refresh = AsyncMock()
    await 协调器.写入辅行诀大类类("心")

    assert 协调器.辅行诀选中大类 == "心"
    assert 协调器.辅行诀选中症状  # 自动取该大类第一个症状
    协调器.async_refresh.assert_awaited_once()


async def test_写入辅行诀大类为空时症状置空(协调器: TianYuanCoordinator) -> None:
    协调器.async_refresh = AsyncMock()
    await 协调器.写入辅行诀大类类("〇")

    assert 协调器.辅行诀选中症状 == ""
    协调器.async_refresh.assert_awaited_once()


@pytest.mark.parametrize(
    ("方法名", "参数", "属性"),
    [
        ("写入辅行诀症状类", "目痛", "辅行诀选中症状"),
        ("写入伤寒六经类", "太阳", "伤寒选中六经"),
        ("写入伤寒证型类", "太阳-表寒实", "伤寒选中证型"),
        ("写入伤寒方名类", "麻黄汤", "伤寒选中方名"),
        ("选择实体选卦名类", "乾为天", "选中卦名"),
        ("写入六爻输入类", "111000", "六爻输入字符串"),
    ],
)
async def test各写入方法写状态并刷新(
    协调器: TianYuanCoordinator, 方法名: str, 参数: str, 属性: str
) -> None:
    协调器.async_refresh = AsyncMock()
    await getattr(协调器, 方法名)(参数)

    assert getattr(协调器, 属性) == 参数
    协调器.async_refresh.assert_awaited_once()


async def test_写入伤寒六经会把证型重置为该经第一项(
    协调器: TianYuanCoordinator,
) -> None:
    协调器.async_refresh = AsyncMock()
    await 协调器.写入伤寒六经类("厥阴")

    assert 协调器.伤寒选中六经 == "厥阴"
    assert "厥阴" in 协调器.伤寒选中证型
    协调器.async_refresh.assert_awaited_once()


async def test_写入伤寒证型会把方名重置为该证型第一方(
    协调器: TianYuanCoordinator,
) -> None:
    证型 = 协调器.伤寒选中证型
    协调器.async_refresh = AsyncMock()
    协调器.伤寒选中方名 = "故意写错"
    await 协调器.写入伤寒证型类(证型)

    assert 协调器.伤寒选中方名 != "故意写错"
    协调器.async_refresh.assert_awaited_once()


# ==================== 日历事件范围 ====================


async def test_日历事件范围每天拆成多行(协调器: TianYuanCoordinator) -> None:
    开始 = date(2026, 2, 17)
    事件 = await 协调器.获取日历事件范围数据类(开始, 开始 + timedelta(days=2))

    assert 事件
    # 每天至少一行农历事件
    按天 = {}
    for e in 事件:
        按天.setdefault(e.start, []).append(e)
    assert set(按天) == {开始, 开始 + timedelta(days=1)}
    assert 按天[开始][0].summary == "正月初一"
    assert all(e.description for e in 事件)


async def test_日历事件范围空区间返回空列表(协调器: TianYuanCoordinator) -> None:
    开始 = date(2026, 2, 17)
    assert await 协调器.获取日历事件范围数据类(开始, 开始) == []


async def test_生日事件范围(协调器: TianYuanCoordinator) -> None:
    entry = 协调器.entry
    协调器.hass.config_entries.async_update_entry(
        entry,
        options={**dict(entry.options), CONF_BIRTHDAYS: ["测试 1990-02-17"]},
    )
    开始 = date(2026, 2, 17)

    事件 = await 协调器.获取生日日历事件范围类(开始, 开始 + timedelta(days=2))

    assert len(事件) == 1
    assert "测试" in 事件[0].summary
    assert 事件[0].start == 开始


async def test_生日事件范围无配置为空(协调器: TianYuanCoordinator) -> None:
    开始 = date(2026, 2, 17)
    assert await 协调器.获取生日日历事件范围类(开始, 开始 + timedelta(days=2)) == []


async def test_单日摘要与单生日摘要构建器(协调器: TianYuanCoordinator) -> None:
    目标 = date(2026, 2, 17)
    单日 = await 协调器.获取日历事件范围数据类(目标, 目标 + timedelta(days=1))
    assert 单日

    # 用真实日级数据包验证两个构建器
    日数据 = 协调器._获取同步日级基础数据类(
        datetime(2026, 2, 17, 12, 0), datetime(2026, 2, 17, 12, 0), MODE_ST
    )
    摘要 = 协调器._构建单日历事件数据类(日数据, 目标)
    assert 摘要["summary"] == "正月初一"

    assert 协调器._构建单生日日历事件数据类(日数据, 目标) is None


# ==================== 设备信息 ====================


async def test_设备信息三套(协调器: TianYuanCoordinator) -> None:
    主 = 协调器.device_info
    assert 主["identifiers"] == {(DOMAIN, 协调器.entry.entry_id)}
    assert 主["translation_key"] == "tianyuan_lunar"
    assert 主["sw_version"] == "9.9.9"
    assert 主["entry_type"] == "service"

    岐黄 = 协调器.qihuang_device_info
    术数 = 协调器.shushu_device_info
    assert 岐黄["identifiers"] != 主["identifiers"]
    assert 术数["identifiers"] != 主["identifiers"]
    assert 岐黄["translation_key"] != 术数["translation_key"]
