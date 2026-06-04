"""
バスなび沖縄 89番 糸満線（上り）全停留所追跡スクリプト
======================================================
・BusStateTable APIでサーバー判定済みのバス停在席情報を取得
・バスなび時刻表APIで各バス停の定刻を自動取得
・到着時に遅延を自動計算してCSVに記録

インストール:
    pip install requests

実行:
    python bus_tracker_final.py
"""

import requests
import csv
import os
import sys
import time
import math
import re
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(line_buffering=True)
JST = timezone(timedelta(hours=9))

# ============================================================
# 設定
# ============================================================

POLL_INTERVAL = 30
OUTPUT_CSV    = "bus_arrival_log.csv"

# 定刻との許容範囲（分）：この範囲内の定刻を「対応する便」とみなす
SCHEDULE_MATCH_MINUTES = 20

# ============================================================
# API パラメータ
# ============================================================

BASE_URL         = "https://www.busnavi-okinawa.com/top/Location"
TIMETABLE_URL    = "https://www.busnavi-okinawa.com/top/ViewTimeTable"
KEITOU_SID       = "f05ce44e-f2f9-4686-90b4-ff244e1c5813"
COURSE_GROUP_SID = "37e827b7-aab1-4971-afa2-7e3d915e722d"
COURSE_SID       = "AllStations"
COURSE_NAME      = "全停留所表示"

HEADERS = {
    "Referer": "https://www.busnavi-okinawa.com/top/Location",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

API_PARAMS = {
    "datetime": "28",
    "keitouSid": KEITOU_SID,
    "courseGroupSid": COURSE_GROUP_SID,
    "courseSid": COURSE_SID,
    "courseName": COURSE_NAME,
}

# ============================================================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def fetch_with_retry(url, params, retries=3, timeout=30):
    for attempt in range(1, retries + 1):
        try:
            p = {**params, "_": int(time.time() * 1000)}
            resp = requests.get(url, params=p, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            print(f"\n  ⚠ 取得失敗({attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(5 * attempt)
    return None

def fetch_timetable(station_sid, bus_stop_code):
    """
    バスなび時刻表APIから指定バス停の上り時刻表を取得。
    {便インデックス: "HH:MM"} の辞書を返す。
    """
    try:
        params = {
            "selectLang": "ja",
            "parentCompanyCode": "9000",
            "stationSid": station_sid,
            "busStopCode": bus_stop_code,
            "_": int(time.time() * 1000),
        }
        resp = requests.get(TIMETABLE_URL, params=params,
                           headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        html = resp.text

        # 時刻表HTMLから上り89番の時刻を抽出
        # 例: <td class="time">07</td><td>05</td>
        times = []
        hour_blocks = re.findall(
            r'<td[^>]*class=["\']?time["\']?[^>]*>(\d{1,2})</td>(.*?)(?=<td[^>]*class=["\']?time|</table)',
            html, re.DOTALL
        )
        for hour_str, block in hour_blocks:
            hour = int(hour_str)
            mins = re.findall(r'<td[^>]*>(\d{2})</td>', block)
            for m in mins:
                t = f"{hour:02d}:{m}"
                if 7 <= hour <= 10:
                    times.append(t)
        return times
    except Exception as e:
        return []

def fetch_stations_with_timetable():
    """
    GetStations APIで全バス停情報を取得し、
    各バス停の時刻表も合わせて返す。
    """
    p = {**API_PARAMS, "_": int(time.time()*1000)}
    resp = requests.get(f"{BASE_URL}/GetStations", params=p,
                       headers=HEADERS, timeout=30)
    stations_raw = resp.json()

    stations = {}
    for s in stations_raw:
        sid = s.get("Sid", "")
        pos = s.get("Position", {})
        bus_stop_code = s.get("BusStopCode", "") or s.get("Code", "")

        # 時刻表を取得（7〜10時のみ）
        timetable = []
        if bus_stop_code:
            timetable = fetch_timetable(sid, bus_stop_code)

        stations[sid] = {
            "name":      s.get("Name", ""),
            "short":     s.get("ShortName", ""),
            "lat":       pos.get("Latitude"),
            "lon":       pos.get("Longitude"),
            "timetable": timetable,
        }
    return stations

def fetch_bus_state_table():
    """
    BusStateTable: サーバー側判定済みの「どのバス停にバスがいるか」を取得。
    {sid: {"name": ..., "has_bus": bool}} を返す。
    """
    resp = fetch_with_retry(f"{BASE_URL}/BusStateTable", API_PARAMS)
    if not resp:
        return None

    html = resp.text
    result = {}
    stop_blocks = re.findall(
        r'onclick=["\']getStationNo\(["\']([^"\']+)["\']["\'][^>]*>([^<]+)</a>(.*?)(?=onclick=["\']getStationNo|$)',
        html, re.DOTALL
    )
    for sid, name, block in stop_blocks:
        result[sid] = {
            "name":    name.strip(),
            "has_bus": "icon_busNow.png" in block,
        }
    return result

def fetch_bus_location():
    """BusLocation: 各バスのGPS座標・ナンバー・会社名を取得"""
    resp = fetch_with_retry(f"{BASE_URL}/BusLocation", API_PARAMS)
    if not resp:
        return None
    return resp.json()

def get_nearest_schedule(timetable, now_hhmm):
    """時刻表から現在時刻に最も近い定刻と遅延分を返す"""
    if not timetable:
        return "", None

    now = datetime.strptime(now_hhmm, "%H:%M")
    best_sched, best_delay = "", None
    best_abs = float("inf")

    for t in timetable:
        try:
            sched = datetime.strptime(t, "%H:%M")
            diff  = int((now - sched).total_seconds() / 60)
            if -5 <= diff <= SCHEDULE_MATCH_MINUTES and abs(diff) < best_abs:
                best_abs   = abs(diff)
                best_sched = t
                best_delay = diff
        except Exception:
            pass
    return best_sched, best_delay

def judge_status(delay):
    if delay is None: return "定刻不明"
    if -1 <= delay <= 3: return "定時"
    if delay > 3: return f"遅延 +{delay}分"
    return f"早着 {delay}分"

def match_bus_to_stop(buses, stop_lat, stop_lon):
    """バス停に最も近いバスのナンバーと会社を返す"""
    if not buses or not stop_lat:
        return "", ""
    best_dist = float("inf")
    best_plate, best_company = "", ""
    for bus_data in buses:
        pos = bus_data.get("Position", {})
        lat, lon = pos.get("Latitude"), pos.get("Longitude")
        if not lat or not lon:
            continue
        dist = haversine(float(lat), float(lon), float(stop_lat), float(stop_lon))
        if dist < best_dist:
            best_dist    = dist
            bus          = bus_data.get("Bus", {})
            best_plate   = bus.get("NumberPlate", "")
            best_company = bus.get("Company", {}).get("Name", "")
    return best_plate, best_company

def save_record(rec):
    exists = os.path.exists(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[
            "日付", "到着時刻", "定刻", "遅延(分)", "状況",
            "系統", "バス停名", "ナンバー", "バス会社"
        ])
        if not exists:
            w.writeheader()
        w.writerow(rec)
    status = rec['状況']
    print(f"  💾 {rec['バス停名']}  着:{rec['到着時刻']} 定刻:{rec['定刻']} [{status}]")

def main():
    print("=" * 60)
    print("  バスなび沖縄 89番 糸満線（上り）全停留所追跡")
    print("=" * 60)
    print(f"  現在時刻(JST): {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  更新間隔    : {POLL_INTERVAL}秒")
    print(f"  記録先     : {OUTPUT_CSV}")
    print("=" * 60)

    # バス停リスト＋時刻表を取得
    print("\nバス停リスト・時刻表を取得中...")
    try:
        stations = fetch_stations_with_timetable()
        print(f"  {len(stations)}件のバス停を取得")
        for sid, s in list(stations.items())[:5]:
            tt = s['timetable']
            print(f"  {s['name'][:20]:20s} 時刻表:{len(tt)}件 {tt[:3]}")
        print("  ...")
    except Exception as e:
        print(f"  取得失敗: {e}")
        stations = {}

    print(f"\n監視開始（Ctrl+C で停止）\n")

    prev_state = {}
    count = 0

    while True:
        count += 1
        now = datetime.now(JST)

        # 平日7〜10時以外はスキップ
        is_monitoring_hour = 7 <= now.hour < 10

        # ★ テスト中は土日も動作。本番は下2行のコメントを外す
        # if now.weekday() >= 5:
        #     print(f"[{now.strftime('%H:%M:%S')}] 土日のため監視しません")
        #     time.sleep(60); continue

        if not is_monitoring_hour:
            print(f"[{now.strftime('%H:%M:%S')}] 監視時間外 — 60秒待機")
            time.sleep(60)
            continue

        print(f"[#{count}] {now.strftime('%H:%M:%S')} 取得中...", end=" ", flush=True)

        state = fetch_bus_state_table()
        if state is None:
            print("取得失敗 — 再試行待機")
            time.sleep(POLL_INTERVAL)
            continue

        buses = fetch_bus_location()

        active = [v["name"] for v in state.values() if v["has_bus"]]
        print(f"バスあり {len(active)}停留所" + (f": {active[0][:10]}..." if active else ""))

        for sid, info in state.items():
            was_there = prev_state.get(sid, False)
            is_there  = info["has_bus"]

            if is_there and not was_there:
                # 到着検知
                now_hhmm  = now.strftime("%H:%M")
                st        = stations.get(sid, {})
                timetable = st.get("timetable", [])
                sched, delay = get_nearest_schedule(timetable, now_hhmm)
                status    = judge_status(delay)
                lat, lon  = st.get("lat"), st.get("lon")
                plate, company = match_bus_to_stop(buses, lat, lon)

                rec = {
                    "日付":    now.strftime("%Y/%m/%d"),
                    "到着時刻": now_hhmm,
                    "定刻":    sched,
                    "遅延(分)": delay if delay is not None else "",
                    "状況":    status,
                    "系統":    "89",
                    "バス停名": info["name"],
                    "ナンバー": plate,
                    "バス会社": company,
                }
                print(f"\n  🚌 到着: {info['name']}")
                save_record(rec)

            elif not is_there and was_there:
                print(f"  → 離脱: {info['name']}")

        prev_state = {sid: v["has_bus"] for sid, v in state.items()}
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
