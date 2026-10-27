"""TianYuan Calendar 配置流测试。"""

from __future__ import annotations

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.tianyuan_calendar_duo.const import (
    DOMAIN,
    CONF_CUSTOM_LONGITUDE,
    CONF_CUSTOM_LATITUDE,
    CONF_REFRESH_INTERVAL,
    CONF_ENABLE_MORE,
    CONF_ENABLE_CARD,
    CONF_ENABLE_QIHUANG,
    CONF_ENABLE_SHUSHU,
    CONF_ENABLE_SHENGRI,
    CONF_CALC_MODE,
    CONF_BIRTHDAYS,
    CONF_SYS_TOKEN,
    MODE_ST,
)


async def test_user_flow_minimal(hass: HomeAssistant) -> None:
    """初次安装：填经纬度与刷新频率即可完成."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 39.9,
            CONF_CUSTOM_LONGITUDE: 120.0,
            CONF_REFRESH_INTERVAL: 1,
        },
    )
    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "天元 (39.90°N, 120.00°E)"
    assert result2["data"] == {}
    opts = result2["options"]
    assert opts[CONF_ENABLE_MORE] is False
    assert opts[CONF_ENABLE_QIHUANG] is False
    assert opts[CONF_ENABLE_SHUSHU] is False


async def test_options_flow_birthdays_step_routing(hass: HomeAssistant) -> None:
    """选项流：开启生日开关应路由进入生日管理子页面（开关仅作为进入门控）。"""
    # 先建立条目
    entry_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    created = await hass.config_entries.flow.async_configure(
        entry_result["flow_id"],
        {CONF_CUSTOM_LONGITUDE: 120.0, CONF_REFRESH_INTERVAL: 1},
    )
    entry_id = created["result"].entry_id

    # 选项流：开启生日开关 -> 应进入 birthdays 子步骤
    opts_result = await hass.config_entries.options.async_init(entry_id)
    assert opts_result["type"] == data_entry_flow.FlowResultType.FORM
    assert opts_result["step_id"] == "init"

    routed = await hass.config_entries.options.async_configure(
        opts_result["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 39.9,
            CONF_CUSTOM_LONGITUDE: 120.0,
            CONF_REFRESH_INTERVAL: 1,
            CONF_CALC_MODE: MODE_ST,
            CONF_ENABLE_MORE: False,
            CONF_ENABLE_QIHUANG: False,
            CONF_ENABLE_SHUSHU: False,
            CONF_ENABLE_SHENGRI: True,
        },
    )
    assert routed["type"] == data_entry_flow.FlowResultType.FORM
    assert routed["step_id"] == "birthdays"


async def test_user_flow_allows_multiple_instances(hass: HomeAssistant) -> None:
    """支持添加多个实例：第二个实例也应成功创建，且标题按坐标区分."""
    # 第一个实例
    r1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    c1 = await hass.config_entries.flow.async_configure(
        r1["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 39.9,
            CONF_CUSTOM_LONGITUDE: 116.4,
            CONF_REFRESH_INTERVAL: 1,
        },
    )
    assert c1["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert c1["title"] == "天元 (39.90°N, 116.40°E)"

    # 第二个实例（不同坐标）
    r2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    c2 = await hass.config_entries.flow.async_configure(
        r2["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 22.5,
            CONF_CUSTOM_LONGITUDE: 114.1,
            CONF_REFRESH_INTERVAL: 5,
        },
    )
    assert c2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert c2["title"] == "天元 (22.50°N, 114.10°E)"

    # 两个实例并存，且 unique_id 不会冲突（由 entry.entry_id 区分）
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_options_flow_persists_latitude(hass: HomeAssistant) -> None:
    """选项流：纬度配置应被正确保存."""
    # 先完成用户流，创建初始实例
    init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    created = await hass.config_entries.flow.async_configure(
        init["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 39.9,
            CONF_CUSTOM_LONGITUDE: 120.0,
            CONF_REFRESH_INTERVAL: 1,
        },
    )
    assert created["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = created["result"]
    assert entry.options[CONF_CUSTOM_LATITUDE] == 39.9
    assert entry.options[CONF_CUSTOM_LONGITUDE] == 120.0

    # 通过选项流修改纬度并验证持久化
    init_options = await hass.config_entries.options.async_init(entry.entry_id)
    updated = await hass.config_entries.options.async_configure(
        init_options["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 23.1,
            CONF_CUSTOM_LONGITUDE: 113.3,
            CONF_REFRESH_INTERVAL: 2,
            CONF_CALC_MODE: MODE_ST,
            CONF_ENABLE_MORE: False,
            CONF_ENABLE_CARD: False,
            CONF_ENABLE_QIHUANG: False,
            CONF_ENABLE_SHUSHU: False,
        },
    )
    assert updated["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CUSTOM_LATITUDE] == 23.1
    assert entry.options[CONF_CUSTOM_LONGITUDE] == 113.3

    # options 流会触发条目重载（reload），重载是异步调度、尚未完成；
    # 必须先等其结束（状态回到 LOADED），否则紧接着的卸载会因处于
    # SETUP_IN_PROGRESS 而抛 OperationNotAllowed。
    await hass.async_block_till_done()

    # 清理：卸载实例以取消 coordinator 的定时刷新定时器，避免遗留 timer 导致测试报错
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


# ==================== 高级选项：系统令牌与生日 ====================


async def _建基础条目(hass: HomeAssistant) -> str:
    """走用户流建一个默认条目，返回 entry_id。"""
    流程 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    创建 = await hass.config_entries.flow.async_configure(
        流程["flow_id"],
        {
            CONF_CUSTOM_LATITUDE: 39.9,
            CONF_CUSTOM_LONGITUDE: 120.0,
            CONF_REFRESH_INTERVAL: 1,
        },
    )
    return 创建["result"].entry_id


def _选项输入(**覆盖) -> dict:
    """选项流 init 步骤的完整表单输入。"""
    输入 = {
        CONF_CUSTOM_LATITUDE: 39.9,
        CONF_CUSTOM_LONGITUDE: 120.0,
        CONF_REFRESH_INTERVAL: 1,
        CONF_CALC_MODE: MODE_ST,
        CONF_ENABLE_MORE: False,
        CONF_ENABLE_CARD: False,
        CONF_ENABLE_QIHUANG: False,
        CONF_ENABLE_SHUSHU: False,
        CONF_ENABLE_SHENGRI: False,
    }
    输入.update(覆盖)
    return 输入


async def _清理条目(hass: HomeAssistant) -> None:
    """等条目恢复 LOADED 后卸载，避免遗留刷新定时器。"""
    await hass.async_block_till_done()
    for entry in list(hass.config_entries.async_entries(DOMAIN)):
        await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_options_flow_hides_token_field_by_default(hass: HomeAssistant) -> None:
    """两个开关未同时开启时不渲染系统令牌输入框。"""
    entry_id = await _建基础条目(hass)

    opts_result = await hass.config_entries.options.async_init(entry_id)
    表单键 = {str(k) for k in opts_result["data_schema"].schema}

    assert CONF_ENABLE_QIHUANG in 表单键
    assert CONF_ENABLE_SHUSHU in 表单键
    assert CONF_SYS_TOKEN not in 表单键

    await _清理条目(hass)


async def test_options_flow_shows_token_field_when_both_enabled(
    hass: HomeAssistant,
) -> None:
    """岐黄与术数同时开启后，再次进入选项页会渲染密钥输入框。"""
    entry_id = await _建基础条目(hass)
    entry = hass.config_entries.async_get_entry(entry_id)
    hass.config_entries.async_update_entry(
        entry,
        options={
            **dict(entry.options),
            CONF_ENABLE_QIHUANG: True,
            CONF_ENABLE_SHUSHU: True,
            CONF_SYS_TOKEN: "旧令牌",
        },
    )

    opts_result = await hass.config_entries.options.async_init(entry_id)
    表单键 = {str(k) for k in opts_result["data_schema"].schema}

    assert CONF_SYS_TOKEN in 表单键

    await _清理条目(hass)


async def test_options_flow_saves_new_token(hass: HomeAssistant) -> None:
    entry_id = await _建基础条目(hass)
    entry = hass.config_entries.async_get_entry(entry_id)
    hass.config_entries.async_update_entry(
        entry,
        options={
            **dict(entry.options),
            CONF_ENABLE_QIHUANG: True,
            CONF_ENABLE_SHUSHU: True,
            CONF_SYS_TOKEN: "旧令牌",
        },
    )

    opts_result = await hass.config_entries.options.async_init(entry_id)
    created = await hass.config_entries.options.async_configure(
        opts_result["flow_id"],
        _选项输入(
            **{
                CONF_ENABLE_QIHUANG: True,
                CONF_ENABLE_SHUSHU: True,
                CONF_SYS_TOKEN: "新令牌",
            }
        ),
    )

    assert created["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_get_entry(entry_id)
    assert entry.options[CONF_SYS_TOKEN] == "新令牌"
    await _清理条目(hass)


async def test_options_flow_clears_token_when_a_switch_is_off(
    hass: HomeAssistant,
) -> None:
    """关闭任一开关时令牌必须清空，避免残留无效授权。"""
    entry_id = await _建基础条目(hass)
    entry = hass.config_entries.async_get_entry(entry_id)
    hass.config_entries.async_update_entry(
        entry,
        options={
            **dict(entry.options),
            CONF_ENABLE_QIHUANG: True,
            CONF_ENABLE_SHUSHU: True,
            CONF_SYS_TOKEN: "旧令牌",
        },
    )

    opts_result = await hass.config_entries.options.async_init(entry_id)
    created = await hass.config_entries.options.async_configure(
        opts_result["flow_id"],
        _选项输入(
            **{
                CONF_ENABLE_QIHUANG: True,
                CONF_ENABLE_SHUSHU: False,
                CONF_SYS_TOKEN: "旧令牌",
            }
        ),
    )

    assert created["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_get_entry(entry_id)
    assert entry.options[CONF_ENABLE_SHUSHU] is False
    assert entry.options[CONF_SYS_TOKEN] == ""
    await _清理条目(hass)


async def test_birthdays_step_persists_list(hass: HomeAssistant) -> None:
    """生日子页提交后写入条目选项。"""
    entry_id = await _建基础条目(hass)

    opts_result = await hass.config_entries.options.async_init(entry_id)
    routed = await hass.config_entries.options.async_configure(
        opts_result["flow_id"],
        _选项输入(**{CONF_ENABLE_SHENGRI: True}),
    )
    assert routed["step_id"] == "birthdays"

    created = await hass.config_entries.options.async_configure(
        routed["flow_id"],
        {CONF_BIRTHDAYS: ["张三 1990-10-25", "李四 1995-05-20 农历"]},
    )

    assert created["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_get_entry(entry_id)
    assert entry.options[CONF_BIRTHDAYS] == ["张三 1990-10-25", "李四 1995-05-20 农历"]
    assert entry.options[CONF_ENABLE_SHENGRI] is True
    await _清理条目(hass)


async def test_birthdays_step_backfills_saved_values(hass: HomeAssistant) -> None:
    """再次进入生日子页时，已保存的生日作为默认值回填。"""
    entry_id = await _建基础条目(hass)
    entry = hass.config_entries.async_get_entry(entry_id)
    hass.config_entries.async_update_entry(
        entry,
        options={**dict(entry.options), CONF_BIRTHDAYS: ["王五 1991-01-01"]},
    )

    opts_result = await hass.config_entries.options.async_init(entry_id)
    routed = await hass.config_entries.options.async_configure(
        opts_result["flow_id"], _选项输入(**{CONF_ENABLE_SHENGRI: True})
    )

    assert routed["step_id"] == "birthdays"
    生日键 = next(k for k in routed["data_schema"].schema if str(k) == CONF_BIRTHDAYS)
    assert 生日键.default() == ["王五 1991-01-01"]
    await _清理条目(hass)
