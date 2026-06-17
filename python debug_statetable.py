"""
BusStateTable のHTML構造を確認するデバッグスクリプト
======================================================
実際のレスポンスHTMLをファイルに保存し、
バスアイコンの構造を解析して表示します。

実行:
    python debug_statetable.py
"""

import requests
import time
import re

BASE_URL = "https://www.busnavi-okinawa.com/top/Location"
KEITOU_SID = "f05ce44e-f2f9-4686-90b4-ff244e1c5813"
COURSE_GROUP_SID = "37e827b7-aab1-4971-afa2-7e3d915e722d"

HEADERS = {
    "Referer": "https://www.busnavi-okinawa.com/top/Location",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

params = {
    "datetime": "28",
    "keitouSid": KEITOU_SID,
    "courseGroupSid": COURSE_GROUP_SID,
    "courseSid": "AllStations",
    "courseName": "全停留所表示",
    "_": int(time.time() * 1000),
}

print("BusStateTable を取得中...")
resp = requests.get(f"{BASE_URL}/BusStateTable", params=params, headers=HEADERS, timeout=30)
print(f"Status: {resp.status_code}")
print(f"レスポンス長: {len(resp.text)} 文字")

# ファイルに保存
with open("statetable_dump.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
print("→ statetable_dump.html に保存しました\n")

html = resp.text

# 1. icon系の画像タグを全部抽出
print("=" * 60)
print("【icon画像タグ一覧】")
print("=" * 60)
img_tags = re.findall(r'<img[^>]+>', html)
icon_imgs = [t for t in img_tags if 'icon' in t.lower()]
for t in icon_imgs[:20]:
    print(f"  {t}")
print(f"  ...(全{len(icon_imgs)}件)")

# 2. getStationNoの出現数を確認
print("\n" + "=" * 60)
print("【getStationNo 呼び出し数】")
print("=" * 60)
station_calls = re.findall(r'getStationNo\([^)]+\)', html)
print(f"  {len(station_calls)}件")
if station_calls:
    print(f"  例: {station_calls[0]}")

# 3. 現在の正規表現でマッチするか確認
print("\n" + "=" * 60)
print("【現在の正規表現でのマッチ結果】")
print("=" * 60)
stop_blocks = re.findall(
    r'onclick=["\']getStationNo\(["\']([^"\']+)["\']["\'][^>]*>([^<]+)</a>(.*?)(?=onclick=["\']getStationNo|$)',
    html, re.DOTALL
)
print(f"  マッチ件数: {len(stop_blocks)}")
bus_count = sum(1 for _, _, block in stop_blocks if "icon_busNow.png" in block)
print(f"  バスあり判定: {bus_count}件")

# 4. 30番台のバス停（赤嶺駅前など）周辺のHTMLを生で表示
print("\n" + "=" * 60)
print("【赤嶺駅前 周辺のHTML（生）】")
print("=" * 60)
idx = html.find("赤嶺駅前")
if idx > 0:
    print(html[max(0,idx-200):idx+800])
else:
    print("「赤嶺駅前」が見つかりません")

print("\n" + "=" * 60)
print("【旭橋・那覇バスターミナル 周辺のHTML（生）】")
print("=" * 60)
idx2 = html.find("旭橋")
if idx2 > 0:
    print(html[max(0,idx2-200):idx2+800])
else:
    print("「旭橋」が見つかりません")
