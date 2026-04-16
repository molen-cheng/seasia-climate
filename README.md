# seasia-climate

东南亚·云南·海南 天气预报与气候监控工具集，为农业/橡胶业务提供天气信息支持。

## 两个任务

### 🌤️ 日度天气预报 (`weather_report.py`)

- **数据源**: Open-Meteo API（免费，无需 key）
- **覆盖**: 泰国6城（清迈、呵叻、曼谷、芭提雅、素叻他尼、普吉）+ 云南2城（昆明、西双版纳）+ 海南2城（海口、三亚）
- **内容**: 每城29天图表（14天历史 + 今日 + 14天预报），温度折线 + 降水柱状图
- **频率**: 每天 8:00
- **输出**: HTML 报告 + 截图推送

### 🌏 周度气候监控 (`seasia_climate_monitor.py`)

- **数据源**: NOAA CPC JAWF Monitoring
- **内容**: CPC 降水分析4张（7天/15天，总量/距平）+ GFS 降水预报4张（第1周/第2周，总量/距平）
- **频率**: 每周日 8:00
- **输出**: HTML 周报 + 企微推送 + GitHub Pages 归档

## 目录结构

```
seasia-climate/
├── scripts/
│   ├── weather_report.py          # 日度天气预报
│   ├── weather_report.html        # HTML 可视化报告
│   └── seasia_climate_monitor.py  # 周度气候监控
├── docs/
│   └── weather-report.md          # 项目文档
├── images/                        # 日度图像归档
├── logs/                          # 运行日志
├── reports/                       # 日报报告
└── weekly_report/                 # 周报报告
    └── YYYY-MM-DD/
        └── index.html
```

## 依赖

- Python 3.8+
- requests
- Playwright + Chrome（日度截图）
