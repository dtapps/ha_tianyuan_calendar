# 开发记录（DEV.md）

> 本文件记录本分支相对原作者 `PraxiGEN/ha_tianyuan_calendar` 的本地改动与目的。
> 面向开发者：说明「改了什么、为什么改、改动落在哪里」。

---

## 1. 支持经纬度配置（新增纬度）

**背景**：原作者只开放了「地理经度」用于真太阳时校准，纬度没有任何配置项，也未参与任何计算。

**改动**：
- `const.py`：新增配置键 `CONF_CUSTOM_LATITUDE`。
- `config_flow.py`：初次安装与高级设置均新增「地理纬度」数字输入（范围 -90~90），默认取 `hass.config.latitude`（HA 系统位置）。
- `coordinator.py`：在 `_async_update_data` 中读取 `CONF_CUSTOM_LATITUDE`，存入 `self.纬度`，并写入 `真太阳时` 实体的属性便于核对定位。

**目的**：让集成能拿到纬度，为后续天文计算提供输入。

---

## 2. 纬度参与天文计算（核心新增）

**背景**：现有功能（真太阳时、节气、八字、天干地支、子午流注、五运六气、二十八宿）全部只依赖「真太阳时（=经度+均时差）」与「日期/时辰」，**与纬度无关**。纬度此前仅是定位标签。

**改动** — `tianyuan/lifa/lunar_logic.py`：
- 新增静态方法 `天元农历逻辑类.计算太阳位置类(真太阳时, 纬度, 经度)`，纯本地 `math` 计算，无新依赖。
  - 配合数据：纬度 φ + 真太阳时（已含经度时差，→时角 H）+ 太阳赤纬 δ（由日序 Cooper 近似推算，无需天文库）。
  - 输出：
    - `太阳高度角`：`asin(sinφ·sinδ + cosφ·cosδ·cosH)`
    - `太阳方位角`：地平坐标向量公式（自正北顺时针，北=0°/东=90°/南=180°/西=270°）
    - `太阳赤纬`：中间量，供核对
    - `日出` / `日落`：半昼时角 `H0=arccos(-tanφ·tanδ)`，并减去经度时差与均时差换算回本地标准时
    - `白昼时长`：`2·H0/15` 小时
  - 处理极昼/极夜（高纬度）：返回「极昼（太阳全天不落下）」/「极夜（太阳全天不升起）」提示，不报错。
- `获取更多实体类` 增加可选参数 `纬度/经度`；当两者均提供时，将太阳位置写入「真太阳时数据」实体的 attributes。

**目的**：让纬度真正落地为有用的天文数据（太阳高度/方位、日出日落、白昼），而不只是标签。

---

## 3. 修复太阳方位角公式 bug

**背景**：初始实现的方位角公式为 `atan2(sinH, cosH·sinφ - tanδ·cosφ)`，正午（H=0、δ≈0）会算出 0°（北），但北半球正午太阳实际在南方（180°），方向错误。

**改动** — `lunar_logic.py`：
改用正确的地平坐标向量公式：
```
北分量 = sinδ·cosφ - cosδ·sinφ·cosH
东分量 = -cosδ·sinH
方位角   = atan2(东分量, 北分量)   # 自正北顺时针
```

---

## 4. 真正支持多实例

**背景**：用户希望添加多个位置（不同经纬度）的集成实例。作者有两处限制单实例：
1. `config_flow.py` 的 `if self._async_current_entries(): return self.async_abort(...)` —— 已移除，并让标题按坐标生成 `天元 (lat°N, lon°E)` 以区分实例。
2. `manifest.json` 的 `"single_config_entry": true` —— **这是 HA 层面真正阻止第二个配置条目的开关**，之前被遗漏。

**改动**：
- `manifest.json`：`single_config_entry` 由 `true` 改为 `false`。
- `coordinator.py`：日级缓存 key 已含经纬度（`D_{日期}_{纬度}_{经度}_{模式}`），不同实例坐标不会串缓存；实体 `unique_id` 与设备 `identifiers` 均基于 `entry.entry_id`，多实例不冲突。

**目的**：允许在同一 HA 中添加多个不同经纬度的天元历法实例。

---

## 5. i18n（实体属性中英文）

**背景**：新增的太阳位置属性（及原有的太阳时/经纬度）在前端直接以中文 key 显示，英文环境无翻译。

**改动** — `translations/en.json` 与 `translations/zh-Hans.json`：
在 `entity.sensor.tst_time.state_attributes` 下补充翻译键：
`太阳时 / 经度 / 纬度 / 太阳高度角 / 太阳方位角 / 太阳赤纬 / 日出 / 日落 / 白昼时长`
→ 英文 `Solar Time / Longitude / Latitude / Solar Altitude / Solar Azimuth / Solar Declination / Sunrise / Sunset / Daylight Duration`。

**说明**：HA 的 `state_attributes` 翻译要求翻译键与代码中 attributes dict 的 key 完全一致（本项目历史约定属性 key 为中文），因此翻译键为中文、翻译的是显示名 `name`。

---

## 6. 单元测试

**新增** — `tests/test_solar_position.py`（5 项，全部通过）：
- 春分正午（北京）：高度角≈`90-纬度`、方位角≈180°（南）、白昼≈12h、日出/日落≈06/18 点。
- 夜间：太阳高度角为负。
- 高纬冬季 → 极夜、高纬夏季 → 极昼边界。
- 经度影响：相同纬度下不同经度换算出的本地标准时日出不同。

**说明**：`计算太阳位置类` 为纯函数，仅依赖 `lunar_python`。因 `custom_components` 父包 `__init__` 会导入 `homeassistant`，测试用 `importlib` 直接加载 `lunar_logic.py` 文件，使其在无 HA 环境下也能独立运行。在含 `homeassistant` 的 CI/本地环境同样可收集。


