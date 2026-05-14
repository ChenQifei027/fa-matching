# IT桔子全量机构发现与智能匹配设计文档

> 2026-05-14

---

## 功能概述

在现有"库内机构匹配"基础上，新增基于 IT桔子 全量机构的智能匹配能力：

1. 从 IT桔子 `/investfirm`（按今年投资数降序）抓取前200家机构及其近2年投资事件
2. LLM 分析每家机构的投资偏好，生成结构化画像并缓存入库
3. 匹配时采用两阶段过滤：Python 快速筛选候选池 → LLM 深度排序
4. 匹配推荐页新增"IT桔子全量"Tab，机构详情页展示偏好画像

---

## 数据模型

### `institutions` 表新增3列

| 列名 | 类型 | 说明 |
|---|---|---|
| `source` | TEXT | `'manual'` 或 `'itjuzi_discovery'`，区分手动添加与自动发现 |
| `preference_profile` | TEXT | LLM 分析结果（JSON字符串） |
| `preference_analyzed_at` | TEXT | 最后分析时间（ISO格式），超过30天视为过期 |

### `preference_profile` JSON 结构

```json
{
  "investment_themes": ["医疗健康", "先进制造", "AI"],
  "preferred_stages": ["A轮", "B轮"],
  "typical_ticket": "1–5亿人民币",
  "geo_focus": ["北京", "成都"],
  "recent_active": true,
  "summary": "近两年重点投医疗器械和工业AI，偏好A/B轮，国产替代主题明显",
  "records_count": 18
}
```

### `investment_records` 表

不变，发现机构与手动机构共用同一张表。

---

## 后台任务流程

### Job 1：发现机构（`discover`）

```
1. 爬取 https://www.itjuzi.com/investfirm（按今年投资数降序，翻页取前200家）
2. 提取每家机构：名称、IT桔子 URL、今年投资数
3. upsert 进 institutions 表（source='itjuzi_discovery'，已存在则跳过基本信息）
4. 对每家机构爬取详情页：
   - 抓取近2年投资事件（公司名、赛道、轮次、金额、日期、事件URL）
   - 存入 investment_records 表（去重插入）
预计耗时：30–60 分钟（200家 × 约10–20秒/家）
```

### Job 2：分析偏好（`analyze-preferences`）

```
1. 取所有机构中满足以下条件之一的：
   - preference_analyzed_at 为 NULL
   - preference_analyzed_at 距今超过 30 天
2. 对每家机构：
   - 筛出 invested_date >= 今天-730天 的记录
   - 若记录数为0则跳过
   - 构造 LLM prompt：记录列表 → 输出 preference_profile JSON
   - 写回 institutions.preference_profile 和 preference_analyzed_at
预计耗时：约40分钟（200家 × 约12秒/LLM调用）
```

### 触发入口

| 位置 | 操作 | 触发内容 |
|---|---|---|
| 机构管理页工具栏 | "🌐 发现机构" | 仅运行 Job 1 |
| 机构详情面板 | "🧠 分析偏好" | 仅对该机构运行 Job 2 |
| 机构管理页工具栏 | "⚡ 一键预热" | Job 1 + Job 2 串行 |
| 匹配推荐页提示条 | "一键预热" | Job 1 + Job 2 串行 |

所有 Job 通过现有 job polling 机制显示进度。

---

## 两阶段匹配逻辑

### 阶段一：Python 快速过滤（无 LLM）

```python
输入：project.sector, project.sub_sector, project.stage

对所有 preference_profile 不为空的机构：
  sector_score = len(project_sectors ∩ institution.investment_themes)
  stage_score  = 1 if project.stage in institution.preferred_stages else 0
  active_bonus = 1 if institution.recent_active else 0
  total = sector_score * 2 + stage_score * 2 + active_bonus

取 total > 0 的机构，按 total 降序取前40名作为候选池
```

### 阶段二：LLM 深度排序（1次调用）

```
Prompt 输入：
  - 项目：名称、赛道、细分、阶段、亮点、融资需求、BP摘要
  - 候选机构（≤40家）：机构名 + preference_profile.summary

LLM 输出：
  Top 10 推荐，每条包含：
  - institution_name
  - score（0–100）
  - reason（≤80字，具体说明偏好与项目的匹配点）

响应时间：约 20 秒
```

### 与现有匹配的关系

- 现有"库内机构匹配"流程完全保留
- 新功能作为独立模式，匹配推荐页新增 Tab 切换

---

## UI 变更

### 机构管理页

**工具栏（现有搜索框右侧）**

- 新增 `🌐 发现机构` 按钮 → 触发 Job 1
- 新增 `⚡ 一键预热` 按钮 → 触发 Job 1 + Job 2
- 运行期间显示进度（通过现有 job polling）

**机构列表**

- "最后更新"列旁新增"偏好"列：已分析显示 `✅ 日期`，未分析显示 `—`
- 操作列新增 `🧠` 按钮（分析单家机构偏好）

**详情面板 - 基本信息 Tab**

新增只读展示区（位于字段表单上方）：

```
【投资偏好画像】（最后分析：2026-05-14）
医疗健康  先进制造  AI          ← investment_themes 标签
A轮  B轮                        ← preferred_stages 标签
近两年重点投医疗器械和工业AI，偏好A/B轮，国产替代主题明显
```

### 匹配推荐页

**Tab 切换**

| Tab | 说明 |
|---|---|
| 库内机构 | 现有流程，仅匹配手动添加的机构 |
| IT桔子全量（新） | 两阶段匹配，基于 preference_profile |

**"IT桔子全量" Tab 内**

- 顶部状态栏：`已分析 X / 200 家机构，最后更新：YYYY-MM-DD` + `[一键预热]`
- 若未分析机构 > 0，显示黄色提示条："建议先完成预热以获得最佳匹配效果"
- 匹配结果卡片新增标签：`近两年活跃` / `主题：医疗健康、AI`

---

## 技术边界说明

- **不新建表**：所有数据复用现有 `institutions` 和 `investment_records` 表
- **增量更新**：已分析且未过期的机构跳过，避免重复消耗 LLM token
- **降级处理**：Job 1 爬取失败的机构跳过，不影响已有数据
- **Token 控制**：阶段二候选池上限40家，每家 summary ≤ 100字，单次 prompt 可控
