"""TianYuan 配置流实现."""
from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_REFRESH_INTERVAL,
    CONF_CUSTOM_LONGITUDE,
    CONF_CUSTOM_LATITUDE,
    CONF_ENABLE_SHUSHU,
    CONF_ENABLE_QIHUANG,
    CONF_ENABLE_SHENGRI,
    CONF_ENABLE_MORE,
    CONF_ENABLE_CARD,
    CONF_CALC_MODE,
    CONF_BIRTHDAYS,
    MODE_ST,
    MODE_TST,
    CONF_SYS_TOKEN,
    DEFAULT_REFRESH_INTERVAL,
)

class TianYuanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """处理初次安装和重新配置流程."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """初次安装：显示经纬度与频率（支持添加多个实例）."""
        if user_input is not None:
            # 初始化默认隐藏的选项
            经度 = float(user_input[CONF_CUSTOM_LONGITUDE])
            纬度 = float(user_input[CONF_CUSTOM_LATITUDE])
            options = {
                CONF_CUSTOM_LONGITUDE: 经度,
                CONF_CUSTOM_LATITUDE: 纬度,
                CONF_REFRESH_INTERVAL: int(user_input[CONF_REFRESH_INTERVAL]),
                CONF_ENABLE_QIHUANG: False,
                CONF_ENABLE_SHUSHU: False,   # 默认关闭
                CONF_ENABLE_MORE: False,  # 默认关闭
                CONF_ENABLE_CARD: False,  # 前端卡片默认关闭，避免全局注册
                CONF_CALC_MODE: MODE_ST,  # 默认兼容模式
            }
            # 标题按坐标生成，多个实例自动区分
            title = f"天元 ({纬度:.2f}°N, {经度:.2f}°E)"
            return self.async_create_entry(title=title, data={}, options=options)

        lon = float(self.hass.config.longitude or 120.0)
        lat = float(self.hass.config.latitude or 39.9)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_CUSTOM_LATITUDE, default=lat): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-90, max=90, step="any", mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_CUSTOM_LONGITUDE, default=lon): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-180, max=180, step="any", mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_REFRESH_INTERVAL, default=DEFAULT_REFRESH_INTERVAL): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=1440, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
            })
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TianYuanOptionsFlowHandler()

class TianYuanOptionsFlowHandler(config_entries.OptionsFlow):
    """配置修改界面：显示所有高级选项."""

    def __init__(self) -> None:
        """初始化时准备一个临时容器存储第一页的数据."""
        self._temp_options = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """基础配置与开关."""
        if user_input is not None:

            self._temp_options.update(user_input)
            
            if not user_input.get(CONF_ENABLE_QIHUANG) or not user_input.get(CONF_ENABLE_SHUSHU):
                self._temp_options[CONF_SYS_TOKEN] = ""

            if user_input.get(CONF_ENABLE_SHENGRI):
                return await self.async_step_birthdays()
        
            return self.async_create_entry(title="", data=self._temp_options)
        
        # 获取当前已保存的选项
        opts = self.config_entry.options
        schema_dict = {
            # 基础配置
            vol.Required(CONF_CUSTOM_LATITUDE, default=float(opts.get(CONF_CUSTOM_LATITUDE, 39.9))): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-90, max=90, step="any", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_CUSTOM_LONGITUDE, default=float(opts.get(CONF_CUSTOM_LONGITUDE, 120.0))): selector.NumberSelector(
                selector.NumberSelectorConfig(min=-180, max=180, step="any", mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_REFRESH_INTERVAL, default=int(opts.get(CONF_REFRESH_INTERVAL, 1))): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=1440, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            # 模式选择
            vol.Required(CONF_CALC_MODE, default=opts.get(CONF_CALC_MODE, MODE_ST)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[MODE_ST, MODE_TST],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_CALC_MODE
                )
            ),
            # 功能开关
            vol.Required(CONF_ENABLE_MORE, default=bool(opts.get(CONF_ENABLE_MORE, False))): selector.BooleanSelector(),
            vol.Required(CONF_ENABLE_CARD, default=bool(opts.get(CONF_ENABLE_CARD, False))): selector.BooleanSelector(),
            vol.Required(CONF_ENABLE_QIHUANG, default=bool(opts.get(CONF_ENABLE_QIHUANG, False))): selector.BooleanSelector(),
            vol.Required(CONF_ENABLE_SHUSHU, default=bool(opts.get(CONF_ENABLE_SHUSHU, False))): selector.BooleanSelector(),
            vol.Optional(CONF_ENABLE_SHENGRI, default=False): selector.BooleanSelector(),
        }

        if opts.get(CONF_ENABLE_QIHUANG) and opts.get(CONF_ENABLE_SHUSHU):
            schema_dict[vol.Optional(
                CONF_SYS_TOKEN, 
                default=opts.get(CONF_SYS_TOKEN, "")
            )] = selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD, 
                    autocomplete="off"
                )
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict)
        )
    
    async def async_step_birthdays(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """专门的生日管理页面."""
        if user_input is not None:

            self._temp_options.update(user_input)
            return self.async_create_entry(title="", data=self._temp_options)

        opts = self.config_entry.options
        return self.async_show_form(
            step_id="birthdays",
            data_schema=vol.Schema({

                vol.Optional(CONF_BIRTHDAYS, default=opts.get(CONF_BIRTHDAYS, [])): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[],
                        multiple=True,
                        custom_value=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            })
        )