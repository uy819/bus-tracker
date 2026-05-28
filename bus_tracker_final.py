"""
バスなび沖縄 89番 糸満線（上り）到着記録スクリプト
====================================================
Selenium不要・requests のみで動作します。
GitHub Actions でそのまま使えます。

インストール:
    pip install requests

実行:
    python bus_tracker_final.py
"""

import requests
import json
import csv
import os
import time
from datetime import datetime

# ============================================================
# 設定（ここを変えてください）
# ============================================================

# 監視するバス停（那覇バスターミナル = 上り終点）
TARGET_STOP_SID  = ""  # 起動時に自動取得
TARGET_STOP_NAME = "旭橋・那覇バスターミナル"  # 部分一致で検索

# 到着判定の距離（メートル）
ARRIVAL_METERS = 150

# 那覇バスターミナル着 平日時刻表（7〜10時）
# 出典: https://www.kotsu-okinawa.org/time/89/up1.html
# 糸満BT発 → 那覇BT着（約47分）
SCHEDULED_TIMES = [
    "07:47",  # 糸満BT 07:00発
    "07:52",  # 糸満BT 07:05発（西崎経由）
    "08:09",  # 糸満BT 07:10発（西崎経由）
    "08:12",  # 糸満BT 07:25発
    "08:28",  # 糸満BT 07:40発
    "08:41",  # 糸満BT 07:55発
    "09:01",  # 糸満BT 08:10発
    "09:21",  # 糸満BT 08:30発（西崎経由）
    "09:27",  # 糸満BT 08:50発
    "09:51",  # 糸満BT 09:15発
    "10:16",  # 糸満BT 09:40発
    "10:31",  # 糸満BT 09:55発
]

# 定刻との対応付け許容範囲（分）
SCHEDULE_MATCH_MINUTES = 25

# 何秒ごとにAPIを叩くか
POLL_INTERVAL = 30

# 記録ファイル
OUTPUT_CSV = "bus_arrival_log.csv"

# ============================================================
# API パラメータ（固定）
# ============================================================

BASE_URL        = "https://www.busnavi-okinawa.com/top/Location"
KEITOU_SID      = "f05ce44e-f2f9-4686-90b4-ff244e1c5813"   # 89番系統
COURSE_GROUP_SID = "37e827b7-aab1-4971-afa2-7e3d915e722d"  # 上り
COURSE_SID      = "AllStations"
COURSE_NAME     = "全停留所表示"

HEADERS = {
    "Referer": "https://www.busnavi-okinawa.com/top/Location",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# ============================================================

import math

def haversine(lat1, lon1, lat2, lon2):
    """2点間の距離をメートルで返す"""
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def fetch_bus_location():
    """BusLocation APIを叩いてバス一覧を返す"""
    ts = int(time.time() * 1000)
    url = f"{BASE_URL}/BusLocation"
    params = {
        "datetime": "28",
        "keitouSid": KEITOU_SID,
        "courseGroupSid": COURSE_GROUP_SID,
        "courseSid": COURSE_SID,
        "courseName": COURSE_NAME,
        "_": ts,
    }
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()

def fetch_stations():
    """GetStations APIでバス停一覧（座標付き）を返す"""
    ts = int(time.time() * 1000)
    url = f"{BASE_URL}/GetStations"
    params = {
        "datetime": "28",
        "keitouSid": KEITOU_SID,
        "courseGroupSid": COURSE_GROUP_SID,
        "courseSid": COURSE_SID,
        "courseName": COURSE_NAME,
        "_": ts,
    }
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()

def get_target_station_pos(stations):
    """監視バス停の座標を返す（名前の部分一致で検索）"""
    for s in stations:
        if TARGET_STOP_NAME in s.get("Name", "") or TARGET_STOP_NAME in s.get("ShortName", ""):
            pos = s.get("Position", {})
            sid = s.get("Sid", "")
            return pos.get("Latitude"), pos.get("Longitude"), sid
    return None, None, None

def get_nearest_schedule(now_hhmm):
    """
    現在時刻に最も近い定刻を返す。
    現在時刻より前の定刻（バスが出発済み）を優先し、
    許容範囲内で最も近いものを選ぶ。
    """
    now = datetime.strptime(now_hhmm, "%H:%M")
    best = None
    best_abs = None
    for s in SCHEDULED_TIMES:
        sched = datetime.strptime(s, "%H:%M")
        diff = int((now - sched).total_seconds() / 60)  # プラス=遅延、マイナス=早着
        # 許容範囲内（-5分〜+SCHEDULE_MATCH_MINUTES分）
        if -5 <= diff <= SCHEDULE_MATCH_MINUTES:
            if best_abs is None or abs(diff) < best_abs:
                best_abs = abs(diff)
                best = (s, diff)
    return best

def judge_status(delay):
    if delay is None: return "定刻不明"
    if -1 <= delay <= 3: return "定時"
    if delay > 3: return f"遅延 +{delay}分"
    return f"早着 {delay}分"

def save_record(rec):
    exists = os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[
            "日付", "到着時刻", "定刻", "遅延(分)", "状況", "系統", "バス停", "ナンバー", "バス会社"
        ])
        if not exists:
            w.writeheader()
        w.writerow(rec)
    print(f"  💾 保存完了: {OUTPUT_CSV}")

def main():
    print("=" * 55)
    print("  バスなび沖縄 89番 糸満線（上り）到着記録")
    print("=" * 55)
    print(f"  監視バス停 : {TARGET_STOP_NAME}")
    print(f"  到着判定  : バス停から {ARRIVAL_METERS}m 以内")
    print(f"  更新間隔  : {POLL_INTERVAL}秒")
    print(f"  記録先   : {OUTPUT_CSV}")
    print("=" * 55)

    # バス停の座標を取得
    print("\nバス停座標を取得中...")
    try:
        stations = fetch_stations()
        target_lat, target_lon, found_sid = get_target_station_pos(stations)
        if target_lat:
            print(f"  {TARGET_STOP_NAME}: 緯度={target_lat:.6f} 経度={target_lon:.6f} Sid={found_sid}")
        else:
            print(f"  ⚠ {TARGET_STOP_NAME} が見つかりません。全バス停:")
            for s in stations:
                print(f"    {s.get('Name')} / {s.get('ShortName')}")
            # 旭橋・那覇バスターミナル のりば10 のフォールバック座標
            target_lat = 26.2155
            target_lon = 127.6797
    except Exception as e:
        print(f"  バス停取得エラー: {e}")
        target_lat = 26.1247
        target_lon = 127.6651

    print(f"\n監視開始（Ctrl+C で停止）\n")

    last_arrived_buses = {}  # bus_id → 最後に記録したtimestamp
    count = 0

    while True:
        count += 1
        now = datetime.now()
        now_hhmm = now.strftime("%H:%M")

        # 7〜10時以外はスリープ（GitHub Actions 時間外対策）
        if not (7 <= now.hour < 10):
            print(f"[{now.strftime('%H:%M:%S')}] 監視時間外（7〜10時のみ） — 60秒待機")
            time.sleep(60)
            continue

        print(f"[#{count}] {now.strftime('%H:%M:%S')} バス位置を取得中...", end=" ", flush=True)

        try:
            buses = fetch_bus_location()
        except Exception as e:
            print(f"取得エラー: {e}")
            time.sleep(POLL_INTERVAL)
            continue

        if not buses:
            print("バスなし（運行情報なし）")
            time.sleep(POLL_INTERVAL)
            continue

        arrived = []
        for bus_data in buses:
            bus = bus_data.get("Bus", {})
            pos = bus_data.get("Position", {})
            bus_id = str(bus.get("Id", ""))
            plate  = bus.get("NumberPlate", "")
            company = bus.get("Company", {}).get("Name", "")
            lat = pos.get("Latitude")
            lon = pos.get("Longitude")

            if lat is None or lon is None:
                continue

            dist = haversine(float(lat), float(lon), target_lat, target_lon)

            if dist <= ARRIVAL_METERS:
                arrived.append({
                    "id": bus_id,
                    "plate": plate,
                    "company": company,
                    "dist": dist,
                })

        if arrived:
            print(f"{len(arrived)}台到着中")
            for bus in arrived:
                cur_time = time.time()
                last_time = last_arrived_buses.get(bus["id"], 0)

                if cur_time - last_time < 600:  # 10分以内は同一到着とみなす
                    print(f"  → バスID={bus['id']} ({bus['plate']}) 記録済みスキップ（{int(cur_time - last_time)}秒前に記録）")
                    continue

                last_arrived_buses[bus["id"]] = cur_time
                sched = get_nearest_schedule(now_hhmm)
                sched_time = sched[0] if sched else ""
                delay      = sched[1] if sched else None
                status     = judge_status(delay)

                rec = {
                    "日付":    now.strftime("%Y/%m/%d"),
                    "到着時刻": now_hhmm,
                    "定刻":    sched_time,
                    "遅延(分)": delay if delay is not None else "",
                    "状況":    status,
                    "系統":    "89",
                    "バス停":   TARGET_STOP_NAME,
                    "ナンバー":  bus["plate"],
                    "バス会社":  bus["company"],
                }
                print(f"\n  🚌 到着！ {bus['plate']} ({bus['company']}) "
                      f"バス停まで{bus['dist']:.0f}m [{status}]")
                save_record(rec)
        else:
            # 近くにいるバスの状況を表示
            near = []
            for bus_data in buses:
                pos = bus_data.get("Position", {})
                bus = bus_data.get("Bus", {})
                lat = pos.get("Latitude")
                lon = pos.get("Longitude")
                if lat and lon:
                    dist = haversine(float(lat), float(lon), target_lat, target_lon)
                    near.append((dist, bus.get("NumberPlate", "?")))
            near.sort()
            if near:
                closest = near[0]
                print(f"バスなし（最近接: {closest[1]} {closest[0]:.0f}m先）")
            else:
                print("バスなし")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
