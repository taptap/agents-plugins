---
name: grafana-dashboard-design
description: 当用户需要新建、重构、优化、复制、扩展 Grafana Dashboard 或 Panel 时触发。适用于梳理 dashboard 信息架构、选择 panel 类型、统一 datasource/阈值/配色/布局、输出可直接落地的 dashboard JSON 修改方案。若任务是配置 Grafana MCP、安装工具、或处理账号连接问题，转交 mcp-grafana，而不是使用此 skill。
---

# Grafana Dashboard Design

## 核心边界

只负责 Dashboard 设计与改造，不负责 Grafana MCP 安装、配置或凭证问题。

优先处理这些任务：
- 新建业务监控大盘
- 重构已有 Dashboard 的结构或视觉层次
- 为已有 Dashboard 增加 Panel / Row / 变量
- 将一组指标整理成可读性更强的 Dashboard JSON
- 统一阈值、单位、颜色、命名和信息密度

不要处理这些任务：
- 安装 `mcp-grafana`
- 配置 `~/.claude.json` 或 `~/.codex/config.toml`
- 排查 Grafana 登录、LDAP、网络、权限问题

## 执行流程

### 1. 明确设计目标

先识别 Dashboard 的目标用户和核心问题，再开始画面板。

必须先确认：
- 这是给谁看的：值班、研发、业务、管理层
- 用户最想在 10 秒内回答什么问题
- 大盘用于实时值守、日常分析、还是复盘汇报
- 默认时间范围和刷新频率

如果用户需求模糊，先收敛成一句话目标，例如：

```text
这个 Dashboard 的目标是让值班同学在 10 秒内判断服务是否异常、异常集中在哪个模块、以及是否正在扩大。
```

### 2. 决定是“继承改造”还是“全新设计”

#### 继承改造现有 Dashboard

先读取原 Dashboard，再决定改造策略。

必须执行：
- 使用 `get_dashboard_by_uid` 读取原 Dashboard
- 保留原 `uid`
- 默认沿用原 `datasource.uid`
- 默认沿用已有变量、folder、tags、refresh，除非用户明确要求调整

重点检查：
- 哪些 panel 已经服务核心目标，保留但重排
- 哪些 panel 重复、噪音大、命名不清，应该删除或合并
- 是否存在多个 datasource 混用且没有显式标注

#### 全新设计 Dashboard

没有现成 Dashboard 时，先补齐最小输入。

至少确认：
- datasource 类型和名称，例如 `prometheus`、`loki`、`cf-analysis`
- 监控对象，例如服务、接口、地域、机房、端
- 主维度，例如 `service`、`cluster`、`instance`、`country`
- 是否需要变量

如果 datasource 不明确，必须先问，不要擅自假设。

## 设计决策树

### 先决定 Dashboard 类型

- 值守型：优先状态、告警、趋势、爆点定位
- 经营型：优先总量、分布、环比、贡献度
- 排障型：优先错误、延迟、分维度对比、TopN
- 容量型：优先使用率、饱和度、增长趋势、剩余空间

### 再决定信息层次

遵循“先判断，再定位，再展开”的顺序。

推荐结构：

```text
Row 1: 全局健康 / 总览
Row 2: 核心趋势 / 关键漏斗
Row 3+: 分模块拆解
Bottom: 详细表格 / TopN / 原始明细
```

如果用户给的指标很多，优先删减，不要把所有指标摊平展示。

## 布局原则

### 金字塔结构

顶部展示少量高价值结论，中部展示趋势和对比，底部展示明细。

推荐模板：

```text
Row 1: 4-6 个 Stat，回答“现在是否健康”
Row 2: 2-4 个 TimeSeries / Gauge，回答“趋势是否恶化”
Row 3+: 按模块或维度拆组，回答“问题出在哪里”
Bottom: Table / BarGauge / PieChart，回答“具体是谁造成的”
```

### Row 命名

可以使用 emoji 前缀，但要克制，保证可扫描性。

推荐：
- `🎯 全局概览`
- `⚡ 性能表现`
- `🚀 服务健康`
- `📱 用户体验`
- `📊 业务结果`
- `🔥 错误与告警`
- `💻 资源利用`

不要把 emoji 当作唯一语义，标题本身必须可读。

### 栅格与信息密度

- 首屏优先放 24 栅格中的高价值面板
- 同一 Row 内，左侧放结论，右侧放趋势
- 同一类面板尺寸保持一致
- 一个屏幕内避免出现超过 6 个同权重结论面板

## Panel 选择规则

按问题选面板，不按“好看”选面板。

| 场景 | 推荐面板 | 不推荐 |
|------|---------|-------|
| 单值状态 | `stat` | `gauge` 过多堆叠 |
| 百分比健康度 | `gauge` | 用 `stat` 硬表示区间 |
| 时间趋势 | `timeseries` | `bargauge` |
| 排名对比 | `bargauge` / `table` | `piechart` |
| 占比分布 | `piechart` | 类别很多时继续用饼图 |
| 详细明细 | `table` | 用多个 `stat` 拼表格 |
| 状态变化时间轴 | `state-timeline` | `timeseries` 强行表达状态切换 |

额外约束：
- TopN 排名超过 8 个类别时，优先 `table`
- 饼图类别超过 6 个时，优先改成 `bargauge` 或 `table`
- 需要展示“变化趋势 + 当前值”时，优先 `stat` + sparkline，而不是单独再加一个小趋势图

## Visual 规范

### 阈值色

| 状态 | 色值 |
|------|------|
| 危险 | `#F2495C` |
| 警告 | `#FF9830` |
| 正常 | `#73BF69` |

阈值必须有业务语义，不要只给颜色不给解释。

### 主题色

优先从 Grafana 常用调色板中选，控制同一 Row 内颜色数量。

| 色值 | 用途建议 |
|------|---------|
| `#5794F2` | 主趋势 |
| `#6ED0E0` | 次趋势 |
| `#73BF69` | 健康 / 成功 |
| `#FF9830` | 警告 / 风险 |
| `#F2495C` | 错误 / 异常 |
| `#B877D9` | 对比系列 |
| `#FADE2A` | 突出提醒 |
| `#8AB8FF` | 次级蓝色系列 |

规则：
- 同一图中的“主线”固定一种颜色
- 成功 / 错误 / 警告语义尽量全局一致
- 不要让颜色承担唯一语义，阈值文本和单位也要清楚

### 单位与命名

必须显式配置：
- 百分比：`percentunit`
- 毫秒：`ms`
- 秒：`s`
- 字节：`bytes`
- QPS / RPM / count：根据业务单位设置

标题规则：
- 面板标题使用“指标 + 维度”格式
- 避免“监控1”“趋势图”“统计值”这类空标题
- 如果是 TopN，标题直接写 `Top 5 Error APIs`

## 推荐配置

### Stat

- `colorMode: background`
- `graphMode: area`
- 需要值守时优先背景色，强调状态变化

### TimeSeries

- `fillOpacity: 20`
- `gradientMode: opacity`
- `lineInterpolation: smooth`
- `thresholdsStyle.mode: line+area`

只在趋势连续、采样足够平滑时使用 `smooth`。尖峰型数据不要强行平滑。

### Gauge

- `showThresholdLabels: true`
- `showThresholdMarkers: true`

Gauge 适合展示占比和容量，不适合展示经常波动的绝对值。

### PieChart

- `pieType: donut`
- `legend.displayMode: table`

只有类别少、占比意义强时才用。

### BarGauge

- `displayMode: gradient`
- `orientation: horizontal`

适合 TopN、排名、对比，不适合展示时间轴数据。

## Query 与 DataSource 约束

### datasource 处理

默认原则：
- 改造现有 Dashboard 时，优先保持 `datasource.uid` 一致
- 新增 panel 时，先确认是否允许使用新的 datasource
- 一个 Row 内尽量不要混多个 datasource，除非用户明确需要

### 查询设计原则

- 一个 panel 只回答一个问题
- 一个 panel 内的系列数量尽量控制在 1-5 条
- 查询别名必须可读，不直接暴露复杂 label 组合
- 先聚合后展示，避免把原始高基数系列直接丢进图里

如果用户没有给具体 query：
- 先按“核心结论”反推指标
- 再确定分组维度
- 最后补窗口、聚合方式和阈值

## 变量策略

只有在“用户会反复切换维度”时才加变量。

适合加变量的场景：
- 服务 / 集群 / 机房 / 环境切换
- 国家 / 渠道 / 端切换
- 多实例 dashboard 复用

不适合加变量的场景：
- 只是为了减少面板数量
- 变量太多，导致首屏操作复杂
- 核心值守信息被折叠到变量之后

## 输出要求

交付时优先给出可直接落地的结果，而不是只讲理念。

优先级从高到低：
1. 直接可用的 dashboard JSON 修改
2. 面板清单 + 每个 panel 的用途
3. datasource / 变量 / 阈值说明
4. 还缺哪些用户输入

如果用户是让你“帮我设计”，至少输出：
- Row 结构
- 每个 Row 的目标
- 每个 panel 的类型、标题、指标说明
- 哪些 panel 需要阈值和单位

## 完成前检查清单

提交前逐项检查：
- datasource 是否明确且一致
- 首屏是否能在 10 秒内回答核心问题
- 面板是否存在重复表达
- 单位、阈值、标题是否完整
- 饼图、Gauge 是否被滥用
- Table 是否只放到底部或明细区域
- 变量是否真的有必要
- 保留原 Dashboard 时是否误改 `uid` 或关键变量

如果不能通过上面的检查，不要急着输出 JSON，先收敛设计。
