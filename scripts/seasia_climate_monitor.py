"""
东南亚气候周报脚本
来源: NOAA CPC JAWF Monitoring - Southeast Asia
功能:
  1. 下载 CPC 降水分析图 + GFS 降水预报图（共8张）
  2. 生成 HTML 周报
  3. 推送企微通知（可选）
"""

import os
import subprocess
import requests
import hashlib
import json
from datetime import datetime, date
from pathlib import Path

# ─── 配置区 ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent / "seasia_climate_data"
IMG_DIR  = BASE_DIR / "images"
LOG_DIR  = BASE_DIR / "logs"
RPT_DIR  = BASE_DIR / "reports"

BASE_URL = "https://www.cpc.ncep.noaa.gov"

# 企业微信机器人 Webhook
WECHAT_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=809ed264-9ef8-4371-8413-24fb5ae63658"

# ─── 周报图像配置 ──────────────────────────────────────────

WEEKLY_IMAGES = {
    # CPC 降水分析
    "01_CPC_7day_降水总量":   "/products/JAWF_Monitoring/SEAsia/daily/p.7day.figa.gif",
    "02_CPC_7day_降水距平":   "/products/JAWF_Monitoring/SEAsia/daily/p.7day.figb.gif",
    "03_CPC_15day_降水总量":  "/products/JAWF_Monitoring/SEAsia/daily/p.15day.figa.gif",
    "04_CPC_15day_降水距平":  "/products/JAWF_Monitoring/SEAsia/daily/p.15day.figb.gif",
    # GFS 降水预报
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

# ─── 核心下载 ─────────────────────────────────────────────

def download_weekly(today_str: str) -> dict:
    """下载周报所需的8张图像"""
    weekly_dir = BASE_DIR / "weekly_report" / today_str
    weekly_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    headers = {"User-Agent": "Mozilla/5.0 (SEAsia Weekly Report; research use)"}

    import shutil
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

# ─── HTML报告 ─────────────────────────────────────────────

def generate_weekly_report(today_str: str, results: dict) -> Path:
    """生成周报HTML"""
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

# ─── Git 推送 ─────────────────────────────────────────────

def git_push(repo_dir: Path):
    """将变更推送到 GitHub（触发 GitHub Pages 自动部署）"""
    try:
        subprocess.run(["git", "-C", str(repo_dir), "add", "-A"],
                        capture_output=True, text=True, timeout=30)
        r2 = subprocess.run(["git", "-C", str(repo_dir), "diff", "--cached", "--quiet"],
                            capture_output=True, text=True, timeout=10)
        if r2.returncode != 0:
            today_str = date.today().strftime("%Y-%m-%d")
            msg = f"Auto-commit {today_str}"
            subprocess.run(["git", "-C", str(repo_dir), "commit", "--message", msg],
                            capture_output=True, text=True, timeout=30)
            r4 = subprocess.run(["git", "-C", str(repo_dir), "push", "origin", "main"],
                                capture_output=True, text=True, timeout=60)
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

# ─── 主入口 ───────────────────────────────────────────────

def main():
    setup_dirs()
    today_str = date.today().strftime("%Y-%m-%d")
    log(f"===== 东南亚气候周报开始 | {today_str} =====")

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

    log(f"===== 周报完成 | 报告: {rpt} =====")
    git_push(BASE_DIR)
    return str(rpt)


if __name__ == "__main__":
    report_path = main()
    print(f"\n✅ 完成！报告路径: {report_path}")
