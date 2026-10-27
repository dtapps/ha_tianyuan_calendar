"""边界分支补充测试：平台装载开关、异常包装、解析失败与数据兜底。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.tianyuan_calendar_duo import calendar as 日历平台
from custom_components.tianyuan_calendar_duo import sensor as 传感器平台
from custom_components.tianyuan_calendar_duo import text as 文本平台
from custom_components.tianyuan_calendar_duo.const import (
    CONF_CUSTOM_LATITUDE,
    CONF_CUSTOM_LONGITUDE,
    CONF_ENABLE_MORE,
    CONF_ENABLE_QIHUANG,
    CONF_ENABLE_SHUSHU,
    CONF_REFRESH_INTERVAL,
    DOMAIN,
)
from custom_components.tianyuan_calendar_duo.coordinator import TianYuanCoordinator
from custom_components.tianyuan_calendar_duo.tianyuan import (
    五运六气类,
    六爻占卜类,
    易经详注类,
    辅行诀脏腑用药法要类,
    伤寒杂病论类,
)
from custom_components.tianyuan_calendar_duo.tianyuan.library import maps_loader

from .helpers import make_coordinator, make_entry, 真农历

时刻 = datetime(2026, 10, 27, 12, 0)

# ==================== 平台装载开关 ====================


def _平台条目(**选项):
    coordinator = make_coordinator()
    return SimpleNamespace(
        entry_id="e1",
        data={},
        options=选项,
        runtime_data=coordinator,
    )


async def test_传感器平台_更多实体开关生效() -> None:
    async_add = MagicMock()
    await 传感器平台.async_setup_entry(
        None, _平台条目(**{CONF_ENABLE_MORE: True}), async_add
    )

    新增 = [e for call in async_add.call_args_list for e in call.args[0]]
    assert any(isinstance(e, 传感器平台.TianYuanAdvancedSensor) for e in 新增)


async def test_传感器平台_关闭更多实体时不创建() -> None:
    async_add = MagicMock()
    await 传感器平台.async_setup_entry(None, _平台条目(), async_add)

    新增 = [e for call in async_add.call_args_list for e in call.args[0]]
    assert 新增
    assert not any(isinstance(e, 传感器平台.TianYuanAdvancedSensor) for e in 新增)


async def test_文本平台_术数未开启时不创建实体() -> None:
    async_add = MagicMock()
    await 文本平台.async_setup_entry(None, _平台条目(), async_add)

    async_add.assert_not_called()


async def test_文本平台_无专业权限时私有输入框被过滤() -> None:
    async_add = MagicMock()
    await 文本平台.async_setup_entry(
        None, _平台条目(**{CONF_ENABLE_SHUSHU: True}), async_add
    )

    async_add.assert_not_called()


async def test_文本平台_有专业权限时创建输入框() -> None:
    async_add = MagicMock()
    with patch.object(文本平台, "检查专业权限类", return_value=True):
        await 文本平台.async_setup_entry(
            None, _平台条目(**{CONF_ENABLE_SHUSHU: True}), async_add
        )

    新增 = [e for call in async_add.call_args_list for e in call.args[0]]
    assert len(新增) == 1
    assert isinstance(新增[0], 文本平台.TianYuanLiuYaoInput)


async def test_日历实体_有数据但缺全量属性时返回None() -> None:
    co = make_coordinator(data={"农历": object()})
    desc = 日历平台.TianYuanCalendarEntityDescription(
        key="lunar_almanac", translation_key="lunar_almanac", cal_type="almanac"
    )
    entity = 日历平台.TianYuanCalendarEntity(co, make_entry(), desc)

    assert entity.event is None


# ==================== 协调器异常包装 ====================


async def _建协调器(hass: HomeAssistant) -> TianYuanCoordinator:
    流程 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    创建 = await hass.config_entries.flow.async_configure(
        流程["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 39.9,
            CONF_CUSTOM_LONGITUDE: 116.4,
            CONF_REFRESH_INTERVAL: 1,
        },
    )
    await hass.async_block_till_done()
    return TianYuanCoordinator(hass, 创建["result"], "1.0.0")


async def test_计算异常被包装为UpdateFailed(hass: HomeAssistant) -> None:
    coordinator = await _建协调器(hass)
    try:
        with patch.object(
            coordinator, "_获取同步日级基础数据类", side_effect=RuntimeError("炸了")
        ):
            with pytest.raises(UpdateFailed, match="天元历法计算失败"):
                await coordinator._async_update_data()
    finally:
        await coordinator.async_shutdown()


async def test_UpdateFailed原样透出(hass: HomeAssistant) -> None:
    coordinator = await _建协调器(hass)
    try:
        with patch.object(
            coordinator,
            "_获取同步日级基础数据类",
            side_effect=UpdateFailed("上游已判定失败"),
        ):
            with pytest.raises(UpdateFailed, match="上游已判定失败"):
                await coordinator._async_update_data()
    finally:
        await coordinator.async_shutdown()


# ==================== 辅行诀 劳 / 误治 ====================


def test_辅行诀选方_劳损走救诸劳损分类() -> None:
    结果 = 辅行诀脏腑用药法要类.辅行诀选方类("不能久视")

    assert 结果["state"] == "大补肝劳汤"
    属性 = 结果["attributes"]
    assert 属性["脏腑"] == "救诸劳损"
    assert 属性["虚实性质"] == "劳损"


def test_辅行诀选方_误治走救误治分类() -> None:
    结果 = 辅行诀脏腑用药法要类.辅行诀选方类("不思食")

    assert 结果["state"] == "泻肝救脾汤"
    属性 = 结果["attributes"]
    assert 属性["脏腑"] == "救误治"
    assert 属性["虚实性质"] == "救逆"


# ==================== 伤寒联动兜底 ====================


def test_纳子法伤寒选方_证型无对应方名时返回空串(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        伤寒杂病论类, "根据证型查方名法", staticmethod(lambda _证: None)
    )

    assert 伤寒杂病论类.子午流注纳子法伤寒选方("胆经", "实") == ""


# ==================== 五运六气 兜底分支 ====================


def test_客气序列_在泉与推演不符时回退查表(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """顺序表异常时，终之气直接按在泉查表兜底。"""
    monkeypatch.setattr(
        五运六气类,
        "三阴三阳顺序表",
        [
            "厥阴风木",
            "少阳相火",
            "太阴湿土",
            "太阳寒水",
            "少阴君火",
            "阳明燥金",
        ],
    )

    客气 = dict(五运六气类.获取六步客气法("子"))

    assert 客气["终之气"] == "阳明燥金"  # 在泉
    assert 客气["三之气"] == "少阴君火"  # 司天
    assert 客气["初之气"] == "厥阴风木"


def test_运气同化_同岁会() -> None:
    """己辰：土运 + 辰属土（岁会），阴干且岁运与在泉同属土（同岁会）。"""
    结果 = 五运六气类.计算运气同化法("己", "辰")

    assert 结果["岁会"] is True
    assert 结果["同岁会"] is True
    assert 结果["描述"] == "岁会，同岁会"


# ==================== 资源加载兜底 ====================


def test_解密空串与非法串返回空字典() -> None:
    assert maps_loader._ShushuAssetEngine.decrypt_item(None) == {}
    assert maps_loader._ShushuAssetEngine.decrypt_item("") == {}
    assert maps_loader._ShushuAssetEngine.decrypt_item("这不是合法密文!!!") == {}


def test_资源文件损坏时降级为空映射(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maps_loader._ShushuAssetEngine, "_cache", None)
    monkeypatch.setattr(
        maps_loader.lzma,
        "decompress",
        lambda _blob: (_ for _ in ()).throw(ValueError("损坏")),
    )

    assert maps_loader.加载全量映射表类() == {}
    assert maps_loader.获取所有卦名列表类() == []


def test_卦象查询未知名称返回空字典() -> None:
    assert 易经详注类.获取易经卦象类("查无此卦") == {}
    # 包装类仍返回结构，但属性为空
    包装 = 易经详注类.获取详注包装类("查无此卦")
    assert 包装["state"] == "查无此卦"
    assert 包装["attributes"] == {}


def test_卦象查询空名称回落到乾为天() -> None:
    包装 = 易经详注类.获取详注包装类(None)
    assert 包装["state"] == "乾为天"
    assert 包装["attributes"]


# ==================== 六爻输入解析 ====================


def test_六爻空输入等待摇卦() -> None:
    结果 = 六爻占卜类.执行占卜流程类("", None)

    assert 结果["state"] == "等待摇卦"
    assert "输入格式" in 结果["attributes"]["提示"]

    assert 六爻占卜类.执行占卜流程类("   ", None)["state"] == "等待摇卦"


def test_六爻带动爻分隔可解析() -> None:
    结果 = 六爻占卜类.执行占卜流程类("101011-25", 真农历(时刻))

    assert 结果["state"] == "风火家人"
    assert 结果["attributes"]["本卦名称"]


def test_六爻中文输入可解析() -> None:
    结果 = 六爻占卜类.执行占卜流程类("阳阴阳阳阴阳-6", 真农历(时刻))

    assert 结果["state"] == "离为火"
    assert 结果["attributes"]["本卦名称"]


@pytest.mark.parametrize("非法输入", ["10101", "1010111", "abcdef", "1-2-3"])
def test_六爻非法输入返回格式错误(非法输入: str) -> None:
    结果 = 六爻占卜类.执行占卜流程类(非法输入, None)

    assert 结果["state"] == "格式错误"
    assert 结果["summary"] == "输入格式不合法"
    assert 结果["attributes"]["当前输入"] == 非法输入


def test_六爻干支五行_短串返回未知() -> None:
    assert 六爻占卜类.干支地支五行法("甲") == "未知"
    assert 六爻占卜类.干支地支五行法("甲子") == 六爻占卜类.地支五行表["子"]


def test_占卜类爻数不足抛异常() -> None:
    with pytest.raises(ValueError, match="六爻必须是6条"):
        六爻占卜类.占卜类([{"爻": 1, "moving": False}], "甲")


def test_卦象查询空名称返回空字典() -> None:
    assert 易经详注类.获取易经卦象类(None) == {}
    assert 易经详注类.获取易经卦象类("未知") == {}
