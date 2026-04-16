#!/usr/bin/env python3
"""
东南亚·云南·海南 每日天气预报
数据源：Open-Meteo API（免费，无需 key）
"""

import json
import sys
import urllib.request
from datetime import datetime, timedelta

# ========== 城市配置 ==========
REGIONS = {
    "🇹🇭 泰国": [
        {"name": "清迈", "region": "北部", "lat": 18.79, "lon": 98.98, "tz": "Asia/Bangkok"},
        {"name": "呵叻", "region": "东北部", "lat": 14.97, "lon": 102.10, "tz": "Asia/Bangkok"},
        {"name": "曼谷", "region": "中部", "lat": 13.76, "lon": 100.50, "tz": "Asia/Bangkok"},
        {"name": "芭提雅", "region": "东部", "lat": 12.92, "lon": 100.88, "tz": "Asia/Bangkok"},
        {"name": "素叻他尼", "region": "南部东", "lat": 9.14, "lon": 99.33, "tz": "Asia/Bangkok"},
        {"name": "普吉", "region": "南部西", "lat": 7.88, "lon": 98.40, "tz": "Asia/Bangkok"},
    ],
    "🇨🇳 云南": [
        {"name": "昆明", "region": "", "lat": 25.04, "lon": 102.68, "tz": "Asia/Shanghai"},
        {"name": "西双版纳", "region": "", "lat": 22.01, "lon": 100.80, "tz": "Asia/Shanghai"},
    ],
    "🇨🇳 海南": [
        {"name": "海口", "region": "", "lat": 20.02, "lon": 110.35, "tz": "Asia/Shanghai"},
        {"name": "三亚", "region": "", "lat": 18.25, "lon": 109.50, "tz": "Asia/Shanghai"},
    ],
}

API_BASE = "https://api.open-meteo.com/v1/forecast"
DAILY_VARS = "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"


def fetch_city(city, days=16):
    """获取单个城市的预报数据"""
    url = (
        f"{API_BASE}?latitude={city['lat']}&longitude={city['lon']}"
        f"&daily={DAILY_VARS}&forecast_days={days}&timezone={city['tz']}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "weather-report/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    d = data["daily"]
    result = []
    for i, date in enumerate(d["time"]):
        result.append({
            "date": date,
            "max_temp": d["temperature_2m_max"][i],
            "min_temp": d["temperature_2m_min"][i],
            "precip": d["precipitation_sum"][i],
            "precip_prob": d["precipitation_probability_max"][i],
        })
    return result


def fmt_table(days, show_index=True):
    """格式化7天表格"""
    lines = []
    header = "| 时段 | 最高温 | 最低温 | 降水量 | 降水概率 |"
    sep = "|------|--------|--------|--------|----------|"
    lines.append(header)
    lines.append(sep)
    for i, d in enumerate(days):
        if i == 0:
            label = "今日"
        elif i <= 6:
            # 提取月/日
            dt = d["date"]
            label = dt[5:]  # MM-DD
        else:
            break
        p_prob = d["precip_prob"]
        p_prob_str = f"{p_prob}%" if p_prob is not None else "—"
        lines.append(
            f"| {label} | {d['max_temp']}°C | {d['min_temp']}°C "
            f"| {d['precip']}mm | {p_prob_str} |"
        )
    return "\n".join(lines)


def trend_summary(days):
    """生成趋势一句话"""
    if not days:
        return ""
    temps = [d["max_temp"] for d in days]
    precs = [d["precip"] for d in days]
    min_t = min(temps)
    max_t = max(temps)
    total_p = sum(precs)
    # 简单趋势判断：后半段降水 vs 前半段
    mid = len(days) // 2
    first_half_rain = sum(precs[:mid]) if mid > 0 else 0
    second_half_rain = sum(precs[mid:])
    if second_half_rain > first_half_rain * 1.5:
        rain_trend = "后段降雨增多"
    elif second_half_rain < first_half_rain * 0.5:
        rain_trend = "逐渐转晴"
    elif total_p < 5:
        rain_trend = "整体偏干"
    elif total_p > 50:
        rain_trend = "持续多雨"
    else:
        rain_trend = "有零星降水"
    return f"气温 {min_t}~{max_t}°C，总降水 {total_p:.0f}mm，{rain_trend}"


def fmt_trend_row(days):
    """15天趋势概览行"""
    if not days:
        return ""
    temps = [d["max_temp"] for d in days] + [d["min_temp"] for d in days]
    min_t = min(temps)
    max_t = max(temps)
    total_p = sum(d["precip"] for d in days)
    mid = len(days) // 2
    first_half = sum(d["precip"] for d in days[:mid]) if mid > 0 else 0
    second_half = sum(d["precip"] for d in days[mid:])
    if second_half > first_half * 1.5:
        trend = "后段多雨"
    elif second_half < first_half * 0.5:
        trend = "逐渐转晴"
    elif total_p < 5:
        trend = "整体偏干"
    elif total_p > 50:
        trend = "持续多雨"
    else:
        trend = "有零星降水"
    return f"| {min_t}~{max_t}°C | {total_p:.0f}mm | {trend} |"


def generate_report():
    """生成完整报告"""
    now = datetime.now()
    weekday_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    date_str = now.strftime("%Y-%m-%d")
    weekday = weekday_map[now.weekday()]

    lines = []
    lines.append(f"**🌡️ 东南亚·云南·海南 每日天气预报**")
    lines.append("")
    lines.append(f"📅 {date_str} {weekday} | 北京时间 {now.strftime('%H:%M')}")
    lines.append("---")

    for section_name, cities in REGIONS.items():
        lines.append("")
        lines.append(f"### {section_name}")

        for city in cities:
            lines.append("")
            if city["region"]:
                lines.append(f"**📍 {city['region']} · {city['name']}**")
            else:
                lines.append(f"**📍 {city['name']}**")
            lines.append("")

            try:
                data = fetch_city(city)
                # 今日 + 7天表格
                lines.append(fmt_table(data[:7]))
                lines.append("")
                # 7天趋势
                lines.append(f"> 📊 7天趋势：{trend_summary(data[:7])}")
            except Exception as e:
                lines.append(f"⚠️ 获取失败：{e}")

    # 15天趋势概览
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 📌 15天趋势概览")
    lines.append("")

    # 缓存数据用于趋势
    all_data = {}
    for section_name, cities in REGIONS.items():
        lines.append(f"**{section_name}**")
        lines.append("")
        header = "| 区域 | 温度范围 | 总降水 | 趋势 |"
        lines.append(header)
        lines.append("|------|----------|--------|------|")
        for city in cities:
            label = city["region"] if city["region"] else city["name"]
            try:
                if city["name"] not in all_data:
                    all_data[city["name"]] = fetch_city(city)
                data = all_data[city["name"]]
                row = f"| {label} {fmt_trend_row(data)}"
                lines.append(row)
            except Exception as e:
                lines.append(f"| {label} | — | — | ⚠️ 获取失败 |")

        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("`设计:Orange | 数据源:Open-Meteo | 生成:OpenClaw`")

    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_report()
    print(report)
    # 保存到文件
    output_path = "/tmp/weather_report.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[已保存到 {output_path}]", file=sys.stderr)
