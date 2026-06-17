"""
バスなび沖縄 89番 糸満線（上り）全停留所追跡スクリプト
======================================================
・BusStateTable APIでサーバー判定済みのバス停在席情報を取得
・各バス停の定刻を時刻表から照合して遅延を自動計算

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
import json
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(line_buffering=True)
JST = timezone(timedelta(hours=9))

LIVE_JSON = "bus_live_position.json"  # リアルタイム地図用の最新バス位置ファイル

# ============================================================
# 設定
# ============================================================

POLL_INTERVAL          = 30   # 秒
SCHEDULE_MATCH_MINUTES = 20   # 定刻との照合許容範囲（分）
OUTPUT_CSV             = "bus_arrival_log.csv"

# ============================================================
# 各バス停の定刻（平日 7〜10時）
# 出典: https://www.kotsu-okinawa.org/time/89/up1.html
# ============================================================

TIMETABLE = {
    "糸満バスターミナル":  ['07:05','07:10','07:25','07:40','07:55','08:10','08:30','08:50','09:15','09:40','09:55','10:10'],
    "糸満市役所入口":     ['07:05','07:10','07:25','07:41','07:55','08:10','08:31','08:50','09:15','09:40','09:55','10:10'],
    "糸満市場入口":      ['07:06','07:11','07:26','07:42','07:56','08:11','08:32','08:51','09:16','09:41','09:56'],
    "糸満ロータリー":     ['07:07','07:12','07:26','07:43','07:57','08:12','08:32','08:52','09:17','09:42','09:57'],
    "糸満西区":         ['07:08','07:13','07:27','07:44','07:58','08:13','08:33','08:52','09:17','09:42','09:57'],
    "白銀堂前":         ['07:08','07:13','07:27','07:44','07:58','08:13','08:33','08:53','09:18','09:43','09:58'],
    "糸満入口":         ['07:09','07:15','07:28','07:45','07:59','08:14','08:34','08:54','09:19','09:44','09:59'],
    "西崎入口":         ['07:11','07:17','07:30','07:47','08:01','08:16','08:36','08:56','09:21','09:46','10:01'],
    "西崎小学校入口":     ['07:18','08:18'],
    "工業団地入口":      ['07:19','08:19'],
    "西崎二丁目":       ['07:20','08:20'],
    "西崎第二団地前":     ['07:22','08:22'],
    "西崎運動公園前":     ['07:23','08:23'],
    "西崎中学校入口":     ['07:25','08:25'],
    "潮平":           ['07:13','07:31','07:48','08:02','08:37','08:57','09:22','09:47','10:02'],
    "阿波根":           ['07:15','07:26','07:33','07:50','08:04','08:27','08:39','08:59','09:24','09:49','10:04'],
    "翁長":            ['07:00','07:16','07:27','07:34','07:51','08:05','08:28','08:40','09:00','09:25','09:50','10:05'],
    "翁長入口":          ['07:01','07:17','07:28','07:35','07:52','08:06','08:29','08:41','09:01','09:26','09:51','10:06'],
    "豊見城南高校前":     ['07:02','07:18','07:29','07:37','07:54','08:08','08:31','08:42','09:02','09:27','09:52','10:07'],
    "与根入口":          ['07:03','07:19','07:30','07:38','07:56','08:10','08:33','08:44','09:04','09:29','09:54','10:09'],
    "座安入口":          ['07:03','07:19','07:30','07:38','07:57','08:11','08:34','08:45','09:04','09:29','09:54','10:09'],
    "伊良波":           ['07:04','07:20','07:31','07:39','07:58','08:12','08:35','08:46','09:05','09:30','09:55','10:10'],
    "我那覇":           ['07:05','07:21','07:32','07:40','07:59','08:13','08:36','08:47','09:06','09:31','09:56'],
    "名嘉地":           ['07:06','07:23','07:34','07:42','08:01','08:15','08:38','08:49','09:08','09:32','09:57'],
    "高良":            ['07:08','07:25','07:37','07:45','08:03','08:17','08:40','08:51','09:10','09:35','10:00'],
    "宇栄原入口":        ['07:09','07:26','07:38','07:46','08:05','08:18','08:41','08:52','09:11','09:36','10:01'],
    "新町入口":          ['07:09','07:26','07:38','07:46','08:06','08:19','08:42','08:52','09:11','09:36','10:01'],
    "第二ゲート":        ['07:10','07:28','07:40','07:47','08:07','08:20','08:43','08:53','09:12','09:37','10:02'],
    "赤嶺駅前":          ['07:11','07:30','07:42','07:49','08:08','08:22','08:44','08:54','09:13','09:38','10:03'],
    "赤嶺安里原":        ['07:13','07:32','07:44','07:51','08:10','08:24','08:46','08:56','09:15','09:39','10:04'],
    "小禄駅前":          ['07:01','07:15','07:35','07:47','07:54','08:12','08:26','08:48','08:58','09:17','09:41','10:06'],
    "田原":            ['07:02','07:16','07:36','07:48','07:55','08:13','08:27','08:49','08:59','09:18','09:42','10:07'],
    "那覇西高校前":       ['07:03','07:17','07:37','07:49','07:56','08:15','08:29','08:51','09:01','09:19','09:43','10:08'],
    "航空隊前":          [],
    "金城":            ['07:05','07:19','07:39','07:51','07:58','08:17','08:31','08:53','09:03','09:21','09:45','10:10'],
    "軍桟橋前":          ['07:07','07:21','07:42','07:54','08:01','08:20','08:33','08:55','09:05','09:23','09:47'],
    "公園前":           ['07:08','07:23','07:45','07:57','08:04','08:22','08:35','08:57','09:06','09:24','09:48'],
    # 那覇バスターミナルは経由により複数回登場するため定刻リストを統合
    "那覇バスターミナル":   ['07:01','07:11','07:17','07:27','07:29','07:46','07:50','08:02','08:09','08:12','08:20',
                          '08:27','08:28','08:41','08:46','09:01','09:01','09:09','09:21','09:27','09:29','09:47','09:51'],
    "旭町":            ['07:03','07:13','07:29','07:53','08:04','08:11','08:29','08:43','09:03','09:11','09:29','09:53'],
    "西壺川":           ['07:04','07:15','07:31','07:55','08:05','08:13','08:31','08:44','09:04','09:12','09:31','09:55'],
    "壺川":            ['07:05','07:16','07:32','07:56','08:06','08:14','08:32','08:45','09:05','09:13','09:32','09:56'],
    "農協会館前":        ['07:06','07:18','07:34','07:58','08:07','08:16','08:34','08:47','09:07','09:15','09:34','09:58'],
    "与儀小学校前":       ['07:07','07:19','07:35','07:59','08:08','08:17','08:35','08:48','09:08','09:17','09:36','10:00'],
    "与儀十字路":        ['07:08','07:20','07:37','08:01','08:09','08:19','08:37','08:50','09:10','09:19','09:38','10:02'],
    "開南":            ['07:10','07:23','07:40','08:04','08:12','08:21','08:39','08:53','09:13','09:22','09:40','10:04'],
    "那覇高校前":        ['07:12','07:25','07:41','08:06','08:14','08:23','08:41','08:55','09:15','09:24','09:42','10:06'],
    "県庁南口":          ['07:14','07:26','07:43','08:08','08:16','08:24','08:42','08:57','09:17','09:25','09:43','10:07'],
    "上泉":            ['07:15','07:27','07:44','08:10','08:18','08:25','08:43','08:58','09:18','09:26','09:44','10:08'],
}

# ============================================================
# API パラメータ
# ============================================================

BASE_URL         = "https://www.busnavi-okinawa.com/top/Location"
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

def fetch_bus_state_table():
    """
    BusStateTable: サーバー側判定済みの「どのバス停にバスがいるか」を取得。
    レスポンスはJSON文字列としてエスケープされているため resp.json() でデコードする。

    <dt>タグの出現位置で区切ったセグメント単位で解析する
    （</dd>への非貪欲マッチは入れ子構造で誤動作するため、dt位置分割が確実）。

    構造は2パターン:
      A) <dt>番号</dt> ... バス停名・Sid・(あれば)icon_bus.png ...
         → そのバス停に滞在中のバス
      B) <dt class="iconBusDT"></dt> ... icon_busNow.png ...
         → 直前のバス停(Aの最後に見つかったバス停)を出発し移動中のバス

    {sid: {"name": ..., "has_bus": bool}} を返す。
    """
    resp = fetch_with_retry(f"{BASE_URL}/BusStateTable", API_PARAMS)
    if not resp:
        return None

    try:
        html = resp.json()  # JSON文字列としてデコード（\uXXXXエスケープを解決）
        if not isinstance(html, str):
            html = resp.text
    except Exception:
        html = resp.text

    result = {}
    last_name, last_sid = None, None

    # <dt>タグの出現位置で区切る（通常版と iconBusDT 版の両方にマッチ）
    dt_positions = [m.start() for m in re.finditer(r'<dt(?:\s+class="iconBusDT")?>', html)]
    segments = []
    for i, pos in enumerate(dt_positions):
        end = dt_positions[i + 1] if i + 1 < len(dt_positions) else len(html)
        segments.append(html[pos:end])

    for seg in segments:
        num_m = re.match(r'<dt(?:\s+class="iconBusDT")?>(\d*)</dt>', seg)
        num = num_m.group(1) if num_m else ""
        has_bus = "icon_bus" in seg  # icon_bus.png / icon_busNow.png 両対応

        if num != "":
            # パターンA: 通常のバス停セグメント
            name_m = re.search(r'busstopClickPopUpInfo\(\d+\);?\s*>([^<]+)</a>', seg)
            sid_m  = re.search(r"getStationNo\(['\"]([^'\"]+)['\"]\)", seg)

            if name_m and sid_m:
                last_name = name_m.group(1).strip()
                last_sid  = sid_m.group(1)
            else:
                if os.environ.get("DEBUG_STATETABLE") == "1":
                    print(f"  [DEBUG] num={num} 名前/Sid抽出失敗 seg={seg[:400]!r}")
                # 名前/Sidの抽出に失敗した場合でも、バス停番号をキーにして
                # has_bus フラグだけは必ず記録する（バス検知の取りこぼし防止）
                last_name = f"停留所#{num}（名称取得失敗）"
                last_sid  = f"unknown-{num}"

            result[last_sid] = {"name": last_name, "has_bus": has_bus}
        else:
            # パターンB: 移動中バス → 直前のバス停に紐づける
            if has_bus and last_sid:
                result[last_sid] = {"name": last_name, "has_bus": True}

    if os.environ.get("DEBUG_STATETABLE") == "1":
        print(f"  [DEBUG] segments: {len(segments)}")
        print(f"  [DEBUG] icon_bus in html: {html.count('icon_bus')}")
        print(f"  [DEBUG] result has_bus count: {sum(1 for v in result.values() if v['has_bus'])}")

    return result

def fetch_bus_location():
    resp = fetch_with_retry(f"{BASE_URL}/BusLocation", API_PARAMS)
    if not resp:
        return None
    return resp.json()

def get_nearest_schedule(stop_name, now_hhmm):
    """バス停名で時刻表を引いて最も近い定刻と遅延分を返す（部分一致）"""
    timetable = []
    for key, times in TIMETABLE.items():
        if key in stop_name or stop_name in key:
            timetable = times
            break
    if not timetable:
        return "", None

    now = datetime.strptime(now_hhmm, "%H:%M")
    best_sched, best_delay = "", None
    best_abs = float("inf")

    for t in timetable:
        sched = datetime.strptime(t, "%H:%M")
        diff  = int((now - sched).total_seconds() / 60)
        if -5 <= diff <= SCHEDULE_MATCH_MINUTES and abs(diff) < best_abs:
            best_abs   = abs(diff)
            best_sched = t
            best_delay = diff
    return best_sched, best_delay

def judge_status(delay):
    if delay is None: return "定刻不明"
    if -1 <= delay <= 3: return "定時"
    if delay > 3: return f"遅延 +{delay}分"
    return f"早着 {delay}分"

def match_bus_to_stop(buses, stop_lat, stop_lon):
    if not buses or not stop_lat:
        return "", ""
    best_dist = float("inf")
    best_plate, best_company = "", ""
    for bus_data in buses:
        pos = bus_data.get("Position", {})
        lat, lon = pos.get("Latitude"), pos.get("Longitude")
        if not lat or not lon:
            continue
        R = 6371000
        p1, p2 = math.radians(float(stop_lat)), math.radians(float(lat))
        dp = math.radians(float(lat) - float(stop_lat))
        dl = math.radians(float(lon) - float(stop_lon))
        a  = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
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
    print(f"  💾 {rec['バス停名'][:15]:15s} 着:{rec['到着時刻']} 定刻:{rec['定刻']:5s} [{rec['状況']}]")

def save_live_positions(buses, now):
    """リアルタイム地図表示用に、現在のバス位置をJSONファイルへ書き出す"""
    items = []
    if buses:
        for b in buses:
            pos = b.get("Position", {})
            bus = b.get("Bus", {})
            lat, lon = pos.get("Latitude"), pos.get("Longitude")
            if not lat or not lon:
                continue
            items.append({
                "lat": lat,
                "lon": lon,
                "plate": bus.get("NumberPlate", ""),
                "company": bus.get("Company", {}).get("Name", ""),
            })
    payload = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "route": "89番 糸満線（上り）",
        "buses": items,
    }
    with open(LIVE_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def push_live_json():
    """bus_live_position.json をその都度コミット・プッシュしてリアルタイム性を持たせる"""
    try:
        os.system('git config user.name "github-actions[bot]"')
        os.system('git config user.email "github-actions[bot]@users.noreply.github.com"')
        os.system(f"git add {LIVE_JSON}")
        os.system('git commit -m "live update" --quiet')
        os.system("git pull --rebase --quiet origin main")
        os.system("git push --quiet")
    except Exception as e:
        print(f"  ⚠ push失敗: {e}")

def main():
    print("=" * 60)
    print("  バスなび沖縄 89番 糸満線（上り）全停留所追跡")
    print("=" * 60)
    print(f"  現在時刻(JST): {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  時刻表バス停数: {len(TIMETABLE)}停留所")
    print(f"  更新間隔    : {POLL_INTERVAL}秒")
    print(f"  記録先     : {OUTPUT_CSV}")
    print("=" * 60)

    # バス停座標を取得（ナンバー照合用）
    print("\nバス停座標を取得中...")
    station_coords = {}
    try:
        p = {**API_PARAMS, "_": int(time.time()*1000)}
        resp = requests.get(f"{BASE_URL}/GetStations", params=p, headers=HEADERS, timeout=30)
        for s in resp.json():
            pos = s.get("Position", {})
            station_coords[s.get("Sid", "")] = {
                "lat": pos.get("Latitude"),
                "lon": pos.get("Longitude"),
            }
        print(f"  {len(station_coords)}件取得")
    except Exception as e:
        print(f"  取得失敗: {e}")

    print(f"\n監視開始（Ctrl+C で停止）\n")

    prev_state = {}
    count = 0

    while True:
        count += 1
        now = datetime.now(JST)

        # ★ テスト中は土日も動作。本番は下2行のコメントを外す
        # if now.weekday() >= 5:
        #     print(f"[{now.strftime('%H:%M:%S')}] 土日のため監視しません")
        #     time.sleep(60); continue

        # IGNORE_TIME_CHECK=1 を設定すると時間帯チェックを無視して即座に監視開始
        # （手動テスト実行用。本番のcronでは設定しない）
        ignore_time_check = os.environ.get("IGNORE_TIME_CHECK", "0") == "1"

        if not ignore_time_check and not (7 <= now.hour < 10):
            print(f"[{now.strftime('%H:%M:%S')}] 監視時間外 — 60秒待機")
            time.sleep(60)
            continue

        print(f"[#{count}] {now.strftime('%H:%M:%S')} 取得中...", end=" ", flush=True)

        state = fetch_bus_state_table()
        if state is None:
            print("取得失敗 — 再試行待機")
            time.sleep(POLL_INTERVAL)
            continue

        buses  = fetch_bus_location()
        save_live_positions(buses, now)  # リアルタイム地図用JSONを更新
        # 3回（約90秒）に1回だけGitHubにpushしてレート制限を回避
        if count % 3 == 0:
            push_live_json()
        active = [v["name"] for v in state.values() if v["has_bus"]]
        print(f"バスあり {len(active)}停留所" + (f": {active[0][:12]}..." if active else ""))

        for sid, info in state.items():
            was_there = prev_state.get(sid, False)
            is_there  = info["has_bus"]

            if is_there and not was_there:
                now_hhmm = now.strftime("%H:%M")
                name     = info["name"]
                sched, delay = get_nearest_schedule(name, now_hhmm)
                status   = judge_status(delay)
                coords   = station_coords.get(sid, {})
                plate, company = match_bus_to_stop(buses, coords.get("lat"), coords.get("lon"))

                rec = {
                    "日付":    now.strftime("%Y/%m/%d"),
                    "到着時刻": now_hhmm,
                    "定刻":    sched,
                    "遅延(分)": delay if delay is not None else "",
                    "状況":    status,
                    "系統":    "89",
                    "バス停名": name,
                    "ナンバー": plate,
                    "バス会社": company,
                }
                print(f"\n  🚌 到着: {name}")
                save_record(rec)

            elif not is_there and was_there:
                print(f"  → 離脱: {info['name']}")

        prev_state = {sid: v["has_bus"] for sid, v in state.items()}
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
