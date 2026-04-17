# seasia-climate 天气预报项目总结

> 日期：2026-04-16 | 作者：Orange

---

## 一、项目背景

为东南亚（泰国）、云南、海南地区建立自动化天气预报系统，每日生成可视化天气预报报告并推送至飞书群。

## 二、项目仓库

- **GitHub 仓库**：`molen-cheng/seasia-climate`
- **本地 clone 路径**：`/tmp/seasia-climate-sync/seasia-climate`
- **主要脚本**：
  - `scripts/weather_report.py` — Markdown 文字版天气预报
  - `scripts/weather_report.html` — Chart.js 可视化 HTML 版（最终格式）
  - `scripts/seasia_climate_monitor.py` — 周度气候监测（CPC/GFS 降水图，已砍掉日度模式）

## 三、覆盖城市

### 🇹🇭 泰国（6个）
| 城市 | 区域 | 坐标 | 时区 |
|------|------|------|------|
| 清迈 | 北部 | 18.79, 98.98 | Asia/Bangkok |
| 呵叻 | 东北部 | 14.97, 102.10 | Asia/Bangkok |
| 曼谷 | 中部 | 13.76, 100.50 | Asia/Bangkok |
| 芭提雅 | 东部 | 12.92, 100.88 | Asia/Bangkok |
| 素叻他尼 | 南部东 | 9.14, 99.33 | Asia/Bangkok |
| 普吉 | 南部西 | 7.88, 98.40 | Asia/Bangkok |

### 🇨🇳 云南（2个）
| 城市 | 坐标 | 时区 |
|------|------|------|
| 勐腊 | 21.46, 101.56 | Asia/Shanghai |
| 景洪 | 22.01, 100.80 | Asia/Shanghai |

### 🇨🇳 海南（2个）
| 城市 | 坐标 | 时区 |
|------|------|------|
| 琼海市 | 19.25, 110.47 | Asia/Shanghai |
| 儋州 | 19.52, 109.58 | Asia/Shanghai |

## 四、技术架构

### 4.1 数据源
- **Open-Meteo API**（免费，无需 key）
- 历史数据：`archive-api.open-meteo.com`（过去14天）
- 预报数据：`api.open-meteo.com`（未来16天）
- 批量优化：按 timezone 分组合并请求（10次→2次，耗时从10s降到2s）

### 4.2 输出格式
- **HTML 可视化版**（最终格式）：Chart.js 渲染温度折线图+降水柱状图，城市卡片两列布局
- 包含：14天趋势图表 + 月度降水对比表格（已去掉趋势列）
- 通过 Playwright（Chromium）截图为 PNG

### 4.3 推送方式
- 飞书群 webhook：`https://open.feishu.cn/open-apis/bot/v2/hook/e0ce773d-44cd-4295-afa9-d8dd6b158ff2`
- 签名密钥：`C5HuwaTbX7nmeWYttrtCPf`
- **限制**：webhook 只支持发文字，发图片需走飞书应用 API（需 access token）
- **当前方案**：截图通过 `message` 工具发送到飞书私聊/群聊

### 4.4 飞书目标群
- **chat_id**：`oc_d693540ce5a005cf0bc3e6c430119e3b`

## 五、定时任务

### 5.1 日度天气预报
| 项目 | 值 |
|------|-----|
| Cron ID | `9c34e28d-66ae-4e6c-b009-f08966b26ad3` |
| Schedule | `0 8 * * *` @ Asia/Shanghai |
| Agent | cron-agent |
| Model | zai/glm-5-turbo |
| Timeout | 300s |
| Session | isolated |

### 5.2 周度气候监测
| 项目 | 值 |
|------|-----|
| Cron ID | `015f5c57-ba7c-4eaa-9477-e22f34f72a4f` |
| Schedule | `0 8 * * 0`（每周日）@ Asia/Shanghai |
| Agent | cron-agent |
| Model | zai/glm-5-turbo |
| Timeout | 120s |
| Session | isolated |

### 5.3 系统 crontab
| 任务 | Schedule | 说明 |
|------|----------|------|
| oilchem_monitor (京排) | */5 9-12 周一至周五 | 石化价格监控 |
| oilchem_monitor (丁二烯库存) | */5 15-18 周三周四 | 库存监控 |
| oilchem_monitor (顺丁库存) | */5 15-18 周三周四 | 库存监控 |
| shfe_br_warrant | 0 16 周一至周五 | SHFE BR仓单日报 |
| cron_healthcheck | 0 * * * * | 每小时健康检查 |

## 六、已完成的工作

1. ✅ GitHub 仓库创建与本地 clone
2. ✅ gh CLI 安装配置（v2.89.0，Classic token）
3. ✅ 项目重构：日度天气预报 + 周度气候监测分离
4. ✅ 城市更新：云南→勐腊/景洪，海南→琼海市/儋州
5. ✅ 批量 API 优化：按 timezone 分组合并请求
6. ✅ HTML 可视化报告：Chart.js 图表 + 两列布局
7. ✅ Playwright 自动截图
8. ✅ 飞书推送通道打通（webhook 签名验证）
9. ✅ GitHub commits 已 push（ec09fd5, 2aef3c9, b1b635c, 47930c4）

## 七、已知问题

### 7.1 ⚠️ 数据精度问题
- **Open-Meteo 在中国地区精度不足**
  - 云南景洪低温偏差大（Open-Meteo: 20.8°C vs 中国天气网: 14°C）
  - 这是 Open-Meteo 在山区地形的数据局限
- **建议**：中国城市（云南/海南）换用和风天气 API，泰国继续用 Open-Meteo
  - 需要到 dev.qweather.com 注册获取免费 API key（每天1000次）

### 7.2 ⚠️ Cron 任务推送未完全跑通
- cron-agent 的 announce delivery 到飞书一直 400 报错
- 脚本内嵌 webhook 推送文字已成功
- **截图发图到群**尚未集成到 cron 自动流程
- 当前依赖 `message` 工具手动发图

### 7.3 ⚠️ WSL Git Push 不稳定
- WSL 的 git over HTTPS 存在 TLS 握手失败（gnutls 问题）
- **待 push 的 commit**：`fd76a42`（批量 API 优化）
- 需要在 Windows 侧手动 push

### 7.4 ⚠️ Playwright 截图依赖
- 截图需要 Chromium 浏览器，依赖 `playwright` Python 包
- 需确保 cron 任务运行环境已安装

## 八、待办事项

- [ ] 解决 cron 任务截图自动推送到飞书群
- [ ] 评估是否引入和风天气 API 提升中国城市数据精度
- [ ] push `fd76a42` commit 到 GitHub（Windows 侧）
- [ ] 更新 cron 任务 payload，集成截图+发图完整流程
- [ ] 验证周度气候监测 cron 任务正常运行

## 九、关键配置速查

| 配置项 | 值 |
|--------|-----|
| 飞书用户 ID | `ou_c1412dc5296d986a3c9ee3649b5e6d50` |
| 飞书目标群 chat_id | `oc_d693540ce5a005cf0bc3e6c430119e3b` |
| 飞书 Webhook URL | `https://open.feishu.cn/open-apis/bot/v2/hook/e0ce773d-44cd-4295-afa9-d8dd6b158ff2` |
| Webhook 签名密钥 | `C5HuwaTbX7nmeWYttrtCPf` |
| GitHub 账号 | `molen-cheng` |
| gh CLI 路径 | `/home/linuxbrew/.linuxbrew/bin/gh` |
| skillhub 安装的 github skill | `~/.openclaw/workspace/skills/github` |
