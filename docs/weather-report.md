# 东南亚·云南·海南 天气预报 + 气候监控项目

## 项目目标
为泰国（6大区域）、云南、海南提供天气信息，用于农业/橡胶业务决策参考。

## 两大任务

### 任务一：日度天气预报
- **脚本**: `scripts/weather_report.py`
- **频率**: 每天 8:00
- **内容**: 10城市天气预报（Open-Meteo API）
- **输出**: HTML 可视化报告 + 截图推送
- **覆盖区域**: 清迈、呵叻、曼谷、芭提雅、素叻他尼、普吉、昆明、西双版纳、海口、三亚

### 任务二：周度气候监控
- **脚本**: `scripts/seasia_climate_monitor.py`
- **频率**: 每周日 8:00
- **内容**: CPC 降水分析（4张）+ GFS 降水预报（4张），共8张图
- **输出**: HTML 周报 + 企微推送 + GitHub Pages 归档
- **数据来源**: NOAA CPC JAWF Monitoring

## 待完成
- [ ] 配置日度天气预报 cron（每天8:00）
- [ ] 配置周度气候监控 cron（每周日8:00）
- [ ] 确认推送渠道（私聊/群）
- [ ] 截图推送流程自动化

## 文件清单
| 文件 | 说明 |
|------|------|
| `scripts/weather_report.py` | 日度天气预报主脚本 |
| `scripts/weather_report.html` | HTML 可视化报告页面 |
| `scripts/seasia_climate_monitor.py` | 周度气候监控脚本 |
