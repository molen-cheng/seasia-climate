"""
东南亚气候异常监控脚本
来源: NOAA CPC JAWF Monitoring - Southeast Asia
功能:
  1. 定期下载降水/温度监测图像
  2. 检测异常（距平图像存档对比）
  3. 生成HTML日报
"""

import os
import sys
import io
import subprocess
import requests
import argparse

# Windows GBK 终端编码兼容
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import hashlib
import json
import shutil
from datetime import datetime, date
from pathlib import Path

# ─── 配置区 ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent / "seasia_climate_data"
IMG_DIR  = BASE_DIR / "images"
LOG_DIR  = BASE_DIR / "logs"

# 企业微信机器人 Webhook（复用于丁二烯监控）
WECHAT_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=809ed264-9ef8-4371-8413-24fb5ae63658"
RPT_DIR  = BASE_DIR / "reports"

BASE_URL = "https://www.cpc.ncep.noaa.gov"

# 所有要监控的图像
IMAGES = {
    # ── 降水总量 ──
    "precip_1day_total":   "/products/JAWF_Monitoring/SEAsia/daily/p.1day.figa.gif",
    "precip_7day_total":   "/products/JAWF_Monitoring/SEAsia/daily/p.7day.figa.gif",
    "precip_15day_total":  "/products/JAWF_Monitoring/SEAsia/daily/p.15day.figa.gif",
    "precip_30day_total":  "/products/JAWF_Monitoring/SEAsia/daily/p.30day.figa.gif",
    # ── 降水距平（异常）──
    "precip_7day_anom":    "/products/JAWF_Monitoring/SEAsia/daily/p.7day.figb.gif",
    "precip_15day_anom":   "/products/JAWF_Monitoring/SEAsia/daily/p.15day.figb.gif",
    "precip_30day_anom":   "/products/JAWF_Monitoring/SEAsia/daily/p.30day.figb.gif",
    # ── 温度（日/周/月）──
    "temp_daily_min":      "/products/analysis_monitoring/regional_monitoring/dcmin5.png",
    "temp_daily_max":      "/products/analysis_monitoring/regional_monitoring/dcmax5.png",
    "temp_daily_avg":      "/products/analysis_monitoring/regional_monitoring/dcavg5.png",
    "temp_weekly_min":     "/products/analysis_monitoring/regional_monitoring/wcmin5.png",
    "temp_weekly_max":     "/products/analysis_monitoring/regional_monitoring/wcmax5.png",
    "temp_weekly_avg":     "/products/analysis_monitoring/regional_monitoring/wcavg5.png",
    "temp_weekly_anom":    "/products/analysis_monitoring/regional_monitoring/wctan5.png",
    "temp_monthly_avg":    "/products/analysis_monitoring/regional_monitoring/1cavg5.png",
    "temp_monthly_anom":   "/products/analysis_monitoring/regional_monitoring/1ctan5.png",
    # ── 站点分布 ──
    "station_daily":       "/products/gnum/SEAsia_curr.p.gnum.gif",
}

# 图像中文标签
LABELS = {
    "precip_1day_total":  "降水量 - 近1天总量",
    "precip_7day_total":  "降水量 - 近7天总量",
    "precip_15day_total": "降水量 - 近15天总量",
    "precip_30day_total": "降水量 - 近30天总量",
    "precip_7day_anom":   "降水距平 - 近7天 ⚠️",
    "precip_15day_anom":  "降水距平 - 近15天 ⚠️",
    "precip_30day_anom":  "降水距平 - 近30天 ⚠️",
    "temp_daily_min":     "温度 - 日最低",
    "temp_daily_max":     "温度 - 日最高",
    "temp_daily_avg":     "温度 - 日平均",
    "temp_weekly_min":    "温度 - 周最低",
    "temp_weekly_max":    "温度 - 周最高",
    "temp_weekly_avg":    "温度 - 周平均",
    "temp_weekly_anom":   "温度距平 - 周 ⚠️",
    "temp_monthly_avg":   "温度 - 月平均",
    "temp_monthly_anom":  "温度距平 - 月 ⚠️",
    "station_daily":      "站点分布 - 当日",
}

# ─── 工具函数 ──────────────────────────────────────────────

def setup_dirs():
    for d in [IMG_DIR, LOG_DIR, RPT_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    today = date.today().strftime("%Y-%m-%d")
    with open(LOG_DIR / f"{today}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ─── 核心下载逻辑 ─────────────────────────────────────────

def download_images(today_str: str) -> dict:
    """
    下载所有图像，保存到 images/<today>/
    返回 {key: {"path": ..., "changed": bool, "error": str|None}}
    """
    today_dir = IMG_DIR / today_str
    today_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (SEAsia Climate Monitor; research use)"
    }

    for key, path in IMAGES.items():
        url = BASE_URL + path
        ext = Path(path).suffix  # .gif or .png
        save_path = today_dir / f"{key}{ext}"

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            save_path.write_bytes(resp.content)

            # 与昨天对比是否有变化
            changed = True
            # 找最近一次旧文件
            old_files = sorted([
                p for p in IMG_DIR.glob(f"*/{key}{ext}")
                if str(p) != str(save_path)
            ])
            if old_files:
                old_md5 = file_md5(old_files[-1])
                new_md5 = file_md5(save_path)
                changed = (old_md5 != new_md5)

            results[key] = {"path": str(save_path), "changed": changed, "error": None}
            status = "🔄 已更新" if changed else "✅ 无变化"
            log(f"{status} | {key}")

        except Exception as e:
            results[key] = {"path": None, "changed": False, "error": str(e)}
            log(f"❌ 下载失败 | {key} | {e}")

    return results

# ─── 异常检测（简单规则）────────────────────────────────────

def detect_anomalies(results: dict) -> list:
    """
    检测距平类图像是否发生更新（代表有气候异常值变化）
    返回异常信号列表
    """
    anom_keys = [k for k in results if "anom" in k]
    alerts = []
    for key in anom_keys:
        r = results[key]
        if r["error"]:
            alerts.append({"level": "ERROR", "key": key, "msg": f"下载失败: {r['error']}"})
        elif r["changed"]:
            alerts.append({"level": "WARN", "key": key, "msg": f"距平图已更新，请关注: {LABELS.get(key, key)}"})
    return alerts

# ─── HTML报告生成 ─────────────────────────────────────────

def generate_report(today_str: str, results: dict, alerts: list) -> Path:
    today_dir = IMG_DIR / today_str
    rpt_path = RPT_DIR / f"seasia_{today_str}.html"

    # 分组顺序：降水总量 → 降水距平 → 温度 → 温度距平
    groups = {
        "🌧️ 降水总量":     [k for k in IMAGES if "total" in k and "temp" not in k],
        "🌧️ 降水距平":     [k for k in IMAGES if "anom" in k and "temp" not in k],
        "🌡️ 温度监测":     [k for k in IMAGES if "temp" in k and "anom" not in k],
        "⚡ 温度距平":     [k for k in IMAGES if "temp" in k and "anom" in k],
        "📍 站点分布": [k for k in IMAGES if "station" in k],
    }

    # 告警HTML
    alert_html = ""
    if alerts:
        items = "".join(
            f'<li class="alert-{"error" if a["level"]=="ERROR" else "warn"}">'
            f'<b>[{a["level"]}]</b> {a["msg"]}</li>'
            for a in alerts
        )
        alert_html = f'<div class="alert-box"><ul>{items}</ul></div>'
    else:
        alert_html = '<div class="alert-ok">✅ 当前无异常信号</div>'

    # 图像卡片
    def card(key):
        r = results.get(key, {})
        label = LABELS.get(key, key)
        if r.get("error"):
            return f'<div class="card error"><div class="card-title">{label}</div><p>❌ 加载失败</p></div>'
        img_path = r.get("path", "")
        # 使用相对路径（报告在reports/，图像在images/today/）
        rel = os.path.relpath(img_path, rpt_path.parent) if img_path else ""
        changed_badge = '<span class="badge-new">NEW</span>' if r.get("changed") else ""
        return (
            f'<div class="card">'
            f'<div class="card-title">{label} {changed_badge}</div>'
            f'<a href="{rel}" target="_blank">'
            f'<img src="{rel}" alt="{label}" onerror="this.src=\'\'"/>'
            f'</a></div>'
        )

    sections_html = ""
    for group_title, keys in groups.items():
        cards = "".join(card(k) for k in keys)
        sections_html += f'<h2>{group_title}</h2><div class="grid">{cards}</div>'

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>东南亚气候监测日报 - {today_str}</title>
<style>
  body {{font-family: 'Segoe UI', Arial, sans-serif; background:#f4f6fa; margin:0; padding:0; color:#222;}}
  header {{background:linear-gradient(90deg,#0a5275,#1a8fc4); color:#fff; padding:18px 32px;}}
  header h1 {{margin:0; font-size:1.5rem;}}
  header p  {{margin:4px 0 0; font-size:.9rem; opacity:.85;}}
  .container {{max-width:1280px; margin:24px auto; padding:0 24px;}}
  h2 {{font-size:1.15rem; color:#0a5275; border-left:4px solid #1a8fc4; padding-left:10px; margin:28px 0 12px;}}
  .grid {{display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:16px; margin-bottom:16px;}}
  .card {{background:#fff; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,.08); padding:12px; transition:.2s;}}
  .card:hover {{box-shadow:0 4px 16px rgba(0,0,0,.15);}}
  .card-title {{font-size:.85rem; font-weight:600; color:#444; margin-bottom:8px;}}
  .card img {{width:100%; height:auto; border-radius:4px; cursor:zoom-in;}}
  .card.error {{border:1px solid #f5c6cb; background:#fff5f5;}}
  .badge-new {{background:#e74c3c; color:#fff; font-size:.7rem; padding:2px 6px; border-radius:4px; margin-left:6px;}}
  .alert-box {{background:#fff3cd; border:1px solid #ffc107; border-radius:8px; padding:14px 18px; margin-bottom:20px;}}
  .alert-box ul {{margin:0; padding-left:18px;}}
  .alert-box .alert-warn {{color:#856404; margin:4px 0;}}
  .alert-box .alert-error {{color:#721c24; margin:4px 0;}}
  .alert-ok {{background:#d4edda; border:1px solid #28a745; border-radius:8px; padding:12px 18px; color:#155724; margin-bottom:20px;}}
  .source-link {{font-size:.8rem; color:#888; text-align:center; margin-top:32px; padding:16px;}}
  .source-link a {{color:#1a8fc4;}}
</style>
</head>
<body>
<header>
  <h1>🌏 东南亚气候监测日报</h1>
  <p>数据来源：NOAA CPC JAWF Monitoring | 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
</header>
<div class="container">
  <h2>🚨 异常告警</h2>
  {alert_html}
  {sections_html}
  <div class="source-link">
    数据来源：<a href="https://www.cpc.ncep.noaa.gov/products/JAWF_Monitoring/SEAsia/index.shtml" target="_blank">
    NOAA CPC Southeast Asia Monitoring</a>
  </div>
</div>
</body>
</html>"""

    rpt_path.write_text(html, encoding="utf-8")
    log(f"📄 报告已生成: {rpt_path}")
    return rpt_path

# ─── 周报专用下载（4+4张图）─────────────────────────────────

WEEKLY_IMAGES = {
    # CPC 降水分析
    "01_CPC_7day_降水总量":   "/products/JAWF_Monitoring/SEAsia/daily/p.7day.figa.gif",
    "02_CPC_7day_降水距平":   "/products/JAWF_Monitoring/SEAsia/daily/p.7day.figb.gif",
    "03_CPC_15day_降水总量":  "/products/JAWF_Monitoring/SEAsia/daily/p.15day.figa.gif",
    "04_CPC_15day_降水距平":  "/products/JAWF_Monitoring/SEAsia/daily/p.15day.figb.gif",
    # GFS 降水预报（来源：GFS_forecasts.shtml）
    "05_GFS_第1周_降水总量":  "/products/JAWF_Monitoring/GFS/SEAsia_curr.p.gfs1a.gif",
    "06_GFS_第1周_降水距平":  "/products/JAWF_Monitoring/GFS/SEAsia_curr.p.gfs1b.gif",
    "07_GFS_第2周_降水总量":  "/products/JAWF_Monitoring/GFS/SEAsia_curr.p.gfs2a.gif",
    "08_GFS_第2周_降水距平":  "/products/JAWF_Monitoring/GFS/SEAsia_curr.p.gfs2b.gif",
}

WEEKLY_LABELS = {
    "01_CPC_7day_降水总量":  "CPC 降水总量 - 近7天",
    "02_CPC_7day_降水距平":  "CPC 降水距平 - 近7天",
    "03_CPC_15day_降水总量": "CPC 降水总量 - 近15天",
    "04_CPC_15day_降水距平": "CPC 降水距平 - 近15天",
    "05_GFS_第1周_降水总量": "GFS 降水预报 - 第1周总量",
    "06_GFS_第1周_降水距平": "GFS 降水预报 - 第1周距平",
    "07_GFS_第2周_降水总量": "GFS 降水预报 - 第2周总量",
    "08_GFS_第2周_降水距平": "GFS 降水预报 - 第2周距平",
}

WEEKLY_CATEGORIES = {
    "📊 CPC 降水分析（7天 / 15天）": [
        "01_CPC_7day_降水总量", "02_CPC_7day_降水距平",
        "03_CPC_15day_降水总量", "04_CPC_15day_降水距平",
    ],
    "🌦️ GFS 降水预报（第1周 / 第2周）": [
        "05_GFS_第1周_降水总量", "06_GFS_第1周_降水距平",
        "07_GFS_第2周_降水总量", "08_GFS_第2周_降水距平",
    ],
}


def download_weekly(today_str: str) -> dict:
    """下载周报所需的8张图像"""
    weekly_dir = BASE_DIR / "weekly_report" / today_str
    weekly_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    headers = {"User-Agent": "Mozilla/5.0 (SEAsia Weekly Report; research use)"}

    for key, path in WEEKLY_IMAGES.items():
        url = BASE_URL + path
        ext = Path(path).suffix
        save_path = weekly_dir / f"{key}{ext}"

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            save_path.write_bytes(resp.content)
            results[key] = {"path": str(save_path), "error": None}
            log(f"✅ {key}")

            # 同时备份到 images/<today>/
            img_today_dir = IMG_DIR / today_str
            img_today_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(save_path, img_today_dir / f"{key}{ext}")

        except Exception as e:
            results[key] = {"path": None, "error": str(e)}
            log(f"❌ {key} | {e}")

    return results


def generate_weekly_report(today_str: str, results: dict) -> Path:
    """生成周报HTML，附带下载链接"""
    weekly_dir = BASE_DIR / "weekly_report" / today_str
    rpt_path = weekly_dir / "index.html"

    def card(key):
        label = WEEKLY_LABELS.get(key, key)
        r = results.get(key, {})
        if r.get("error"):
            return (
                f'<div class="card">'
                f'<div class="card-label"><span class="tag-cpc">{label}</span> ❌ 下载失败</div>'
                f'</div>'
            )
        img_path = r.get("path", "")
        rel = os.path.relpath(img_path, rpt_path.parent) if img_path else ""
        fname = Path(img_path).name
        cat_class = "tag-cpc" if "CPC" in key else "tag-gfs"
        return (
            f'<div class="card">'
            f'<img src="{fname}" alt="{label}">'
            f'<div class="card-label">'
            f'<span class="{cat_class}">{"CPC" if "CPC" in key else "GFS"}</span>'
            f'{label} '
            f'<a class="dl-btn" href="{fname}" download>下载</a>'
            f'</div></div>'
        )

    sections_html = ""
    for group_title, keys in WEEKLY_CATEGORIES.items():
        cards = "".join(card(k) for k in keys)
        sections_html += f'<h2>{group_title}</h2><div class="grid">{cards}</div>'

    success_count = sum(1 for r in results.values() if not r.get("error"))

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>东南亚气候周报图像 - {today_str}</title>
<style>
  body {{ font-family: "微软雅黑", Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; }}
  h1 {{ color: #1a3c6e; border-bottom: 3px solid #1a3c6e; padding-bottom: 8px; font-size: 20px; }}
  h2 {{ color: #2d5fa0; font-size: 15px; margin-top: 24px; margin-bottom: 10px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .card {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; }}
  .card img {{ width: 100%; display: block; }}
  .card-label {{ padding: 8px 12px; font-size: 13px; color: #444; background: #f0f4fa; border-top: 1px solid #dde4ee; }}
  .tag-cpc {{ background: #1a3c6e; color: #fff; border-radius: 4px; padding: 2px 7px; font-size: 11px; margin-right: 6px; }}
  .tag-gfs {{ background: #2d8a4e; color: #fff; border-radius: 4px; padding: 2px 7px; font-size: 11px; margin-right: 6px; }}
  .meta {{ font-size: 12px; color: #888; margin-bottom: 16px; }}
  .dl-btn {{ display: inline-block; margin-left: 8px; padding: 3px 10px; background: #2d5fa0; color: #fff; border-radius: 4px; font-size: 12px; text-decoration: none; }}
  .dl-btn:hover {{ background: #1a3c6e; }}
  .summary {{ background: #fff; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px; border-left: 4px solid #1a3c6e; font-size: 13px; }}
</style>
</head>
<body>
<h1>🌏 东南亚气候周报图像 - {today_str}</h1>
<div class="summary">
  <b>数据来源：</b>NOAA CPC JAWF Monitoring &nbsp;|&nbsp;
  <b>下载时间：</b>{datetime.now().strftime("%Y-%m-%d %H:%M")} &nbsp;|&nbsp;
  <b>成功下载：</b>{success_count}/8 张
</div>
{sections_html}
<p class="meta" style="margin-top:24px;">
  数据来源：<a href="https://www.cpc.ncep.noaa.gov/products/JAWF_Monitoring/SEAsia/index.shtml" target="_blank">
  NOAA CPC Southeast Asia Monitoring</a>
</p>
</body>
</html>"""

    rpt_path.write_text(html, encoding="utf-8")
    log(f"📄 周报已生成: {rpt_path}")
    return rpt_path


# ─── 主入口 ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="东南亚气候监控脚本")
    parser.add_argument("--weekly", action="store_true", help="运行周报模式（下载8张降水图并归档）")
    args = parser.parse_args()

    setup_dirs()
    today_str = date.today().strftime("%Y-%m-%d")
    log(f"===== 东南亚气候监控开始 | {today_str} | mode={'weekly' if args.weekly else 'daily'} =====")

    if args.weekly:
        # 周报模式
        results = download_weekly(today_str)
        rpt = generate_weekly_report(today_str, results)
        success_count = sum(1 for r in results.values() if not r.get("error"))
        summary = {
            "date": today_str,
            "mode": "weekly",
            "total": 8,
            "success": success_count,
            "report": str(rpt),
        }
        (LOG_DIR / f"{today_str}_weekly_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        # 日常日报模式
        results = download_images(today_str)
        alerts  = detect_anomalies(results)

        if alerts:
            log(f"⚠️  发现 {len(alerts)} 条异常信号")
            for a in alerts:
                log(f"  [{a['level']}] {a['msg']}")
        else:
            log("✅ 无异常信号")

        rpt = generate_report(today_str, results, alerts)

        summary = {
            "date": today_str,
            "mode": "daily",
            "run_time": datetime.now().isoformat(),
            "total": len(results),
            "success": sum(1 for r in results.values() if not r["error"]),
            "changed": sum(1 for r in results.values() if r["changed"]),
            "alerts": alerts,
            "report": str(rpt),
        }
        (LOG_DIR / f"{today_str}_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # 发送企微日报
        send_daily_wechat_report(today_str, results, alerts, Path(rpt))

    log(f"===== 监控完成 | 报告: {rpt} =====")
    # 自动推送到 GitHub Pages
    git_push(BASE_DIR)
    return str(rpt)


def git_push(repo_dir: Path):
    """将变更推送到 GitHub（触发 GitHub Pages 自动部署）"""
    GIT_EXE = r"C:\Program Files\Git\cmd\git.exe"
    try:
        # git add
        subprocess.run(
            [GIT_EXE, "-C", str(repo_dir), "add", "-A"],
            capture_output=True, text=True, timeout=30
        )
        # 检查是否有变更
        r2 = subprocess.run(
            [GIT_EXE, "-C", str(repo_dir), "diff", "--cached", "--quiet"],
            capture_output=True, text=True, timeout=10
        )
        if r2.returncode != 0:
            today_str = date.today().strftime("%Y-%m-%d")
            msg = f"Auto-commit {today_str}"
            subprocess.run(
                [GIT_EXE, "-C", str(repo_dir), "commit", "--message", msg],
                capture_output=True, text=True, timeout=30
            )
            r4 = subprocess.run(
                [GIT_EXE, "-C", str(repo_dir), "push", "origin", "main"],
                capture_output=True, text=True, timeout=60
            )
            if r4.returncode == 0:
                print("🚀 GitHub Pages 推送成功！")
            else:
                print(f"⚠️ Git 推送失败: {r4.stderr}")
        else:
            print("ℹ️  无变更，跳过推送")
    except Exception as e:
        print(f"⚠️ Git 推送异常: {e}")


# ─── 企微通知 ─────────────────────────────────────────────
def send_wechat_message(content: str, msg_type: str = "text"):
    """发送企业微信消息"""
    try:
        if msg_type == "markdown":
            data = {"msgtype": "markdown", "markdown": {"content": content}}
        else:
            data = {"msgtype": "text", "text": {"content": content}}
        resp = requests.post(WECHAT_WEBHOOK, json=data, timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            print("[企微] 消息发送成功")
        else:
            print(f"[企微] 发送失败: {result}")
        return result.get("errcode") == 0
    except Exception as e:
        print(f"[企微] 发送异常: {e}")
        return False


def send_wechat_image(image_path: Path) -> bool:
    """发送图片到企微（base64+md5方式）"""
    try:
        import base64
        img_bytes = image_path.read_bytes()
        b64 = base64.b64encode(img_bytes).decode()
        import hashlib
        md5 = hashlib.md5(img_bytes).hexdigest()
        data = {
            "msgtype": "image",
            "image": {"base64": b64, "md5": md5}
        }
        resp = requests.post(WECHAT_WEBHOOK, json=data, timeout=15)
        result = resp.json()
        return result.get("errcode") == 0
    except Exception as e:
        print(f"[企微] 图片发送异常 {image_path.name}: {e}")
        return False


def send_daily_wechat_report(today_str: str, results: dict, alerts: list, report_path: Path):
    """发送日报到企微：文字摘要 + 关键图片"""
    # 文字摘要
    success = sum(1 for r in results.values() if not r.get("error"))
    changed = sum(1 for r in results.values() if r.get("changed"))
    total = len(results)
    alert_count = len(alerts)
    alert_summary = "\n".join([f"> [{a['level']}] {a['msg']}" for a in alerts[:5]]) if alerts else "无"

    summary = f"""**🌏 东南亚气候日报 {today_str}**

**下载状态：** {success}/{total} 张成功
**图像更新：** {changed} 张有变化
**异常信号：** {alert_count} 条
---
{alert_summary if alert_count > 0 else '> ✅ 无异常信号'}
---
📄 报告本地路径已归档"""
    send_wechat_message(summary, msg_type="markdown")

    # 发送关键图片（降水总量 + 降水距平）
    key_images = [
        ("precip_7day_total",  "🌧️ 7天降水总量"),
        ("precip_7day_anom",   "⚡ 7天降水距平"),
        ("precip_15day_anom",   "⚡ 15天降水距平"),
        ("precip_30day_anom",   "⚡ 30天降水距平"),
    ]
    today_img_dir = IMG_DIR / today_str
    for key, label in key_images:
        path = None
        for ext in [".gif", ".png"]:
            p = today_img_dir / f"{key}{ext}"
            if p.exists():
                path = p
                break
        if path:
            ok = send_wechat_image(path)
            print(f"  {'✅' if ok else '❌'} {label} ({path.name})")
        else:
            print(f"  ⏭️  跳过（今日未下载）: {label}")

if __name__ == "__main__":
    report_path = main()
    print(f"\n✅ 完成！报告路径: {report_path}")
