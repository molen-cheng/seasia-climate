#!/usr/bin/env python3
"""
东南亚·云南·海南 每日天气预报
数据源：Open-Meteo API（免费，无需 key）
"""

import json
import os
import sys
import urllib.request
from pathlib import Path
from datetime import datetime

# 加载 .env 文件
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip())

FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK_URL", "")
FEISHU_WEBHOOK_SECRET = os.environ.get("FEISHU_WEBHOOK_SECRET", "")

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
        {"name": "勐腊", "region": "", "lat": 21.46, "lon": 101.56, "tz": "Asia/Shanghai"},
        {"name": "景洪", "region": "", "lat": 22.01, "lon": 100.80, "tz": "Asia/Shanghai"},
    ],
    "🇨🇳 海南": [
        {"name": "琼海市", "region": "", "lat": 19.25, "lon": 110.47, "tz": "Asia/Shanghai"},
        {"name": "儋州", "region": "", "lat": 19.52, "lon": 109.58, "tz": "Asia/Shanghai"},
    ],
}

API_BASE = "https://api.open-meteo.com/v1/forecast"
DAILY_VARS = "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"


def fetch_all_cities(all_cities, days=16):
    """批量获取所有城市预报数据（按时区分组合并请求）"""
    tz_groups = {}
    for city in all_cities:
        tz = city['tz']
        if tz not in tz_groups:
            tz_groups[tz] = []
        tz_groups[tz].append(city)

    cache = {}
    for tz, cities in tz_groups.items():
        lats = ",".join(str(c['lat']) for c in cities)
        lons = ",".join(str(c['lon']) for c in cities)
        url = (
            f"{API_BASE}?latitude={lats}&longitude={lons}"
            f"&daily={DAILY_VARS}&forecast_days={days}&timezone={tz}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "weather-report/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        for idx, city in enumerate(cities):
            d = data[idx] if isinstance(data, list) else data
            daily = d["daily"]
            result = []
            for i, date in enumerate(daily["time"]):
                result.append({
                    "date": date,
                    "max_temp": daily["temperature_2m_max"][i],
                    "min_temp": daily["temperature_2m_min"][i],
                    "precip": daily["precipitation_sum"][i],
                    "precip_prob": daily["precipitation_probability_max"][i],
                })
            cache[city['name']] = result
    return cache


def fetch_city(city_name, cache):
    return cache.get(city_name, [])


def fmt_table(days):
    lines = []
    lines.append("| 时段 | 最高温 | 最低温 | 降水量 | 降水概率 |")
    lines.append("|------|--------|--------|--------|----------|")
    for i, d in enumerate(days):
        label = "今日" if i == 0 else (d["date"][5:] if i <= 6 else None)
        if label is None:
            break
        p_prob_str = f"{d['precip_prob']}%" if d["precip_prob"] is not None else "—"
        lines.append(
            f"| {label} | {d['max_temp']}°C | {d['min_temp']}°C "
            f"| {d['precip']}mm | {p_prob_str} |"
        )
    return "\n".join(lines)


def trend_summary(days):
    if not days:
        return ""
    temps = [d["max_temp"] for d in days]
    precs = [d["precip"] for d in days]
    min_t = min(temps)
    max_t = max(temps)
    total_p = sum(precs)
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
    now = datetime.now()
    weekday_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    date_str = now.strftime("%Y-%m-%d")
    weekday = weekday_map[now.weekday()]

    lines = []
    all_cities = [c for cities in REGIONS.values() for c in cities]
    try:
        cache = fetch_all_cities(all_cities)
    except Exception as e:
        cache = {}
        lines.append(f"⚠️ 数据获取失败：{e}")

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
                data = fetch_city(city['name'], cache)
                if not data:
                    lines.append(f"⚠️ 无数据")
                    continue
                lines.append(fmt_table(data[:7]))
                lines.append("")
                lines.append(f"> 📊 7天趋势：{trend_summary(data[:7])}")
            except Exception as e:
                lines.append(f"⚠️ 获取失败：{e}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 📌 15天趋势概览")
    lines.append("")

    for section_name, cities in REGIONS.items():
        lines.append(f"**{section_name}**")
        lines.append("")
        lines.append("| 区域 | 温度范围 | 总降水 | 趋势 |")
        lines.append("|------|----------|--------|------|")
        for city in cities:
            label = city["region"] if city["region"] else city["name"]
            try:
                data = fetch_city(city['name'], cache)
                if not data:
                    lines.append(f"| {label} | — | — | ⚠️ 无数据 |")
                    continue
                lines.append(f"| {label} {fmt_trend_row(data)}")
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
