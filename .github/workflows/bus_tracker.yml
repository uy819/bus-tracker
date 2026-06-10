name: バス到着時刻記録（89番糸満線上り）

on:
  schedule:
    # JST = UTC+9 なので JST時刻からマイナス9時間がUTC
    # JST 07:30 = UTC 22:30（前日）→ 月〜金に実行するため曜日指定は前日基準
    # 月曜JST07:30 = 日曜UTC22:30 → UTC曜日は0(日)〜4(木)で月〜金をカバー
    - cron: '30 22 * * 0-4'   # JST 月〜金 07:30
    - cron: '0 23 * * 0-4'    # JST 月〜金 08:00
    - cron: '30 23 * * 0-4'   # JST 月〜金 08:30
    - cron: '0 0 * * 1-5'     # JST 月〜金 09:00（UTC日付は翌日=1-5）
    - cron: '30 0 * * 1-5'    # JST 月〜金 09:30（UTC日付は翌日=1-5）
  workflow_dispatch:           # 手動実行ボタン（テスト用）

# 同時実行を1つに制限
concurrency:
  group: bus-tracker
  cancel-in-progress: false

jobs:
  track:
    runs-on: ubuntu-latest
    timeout-minutes: 29
    permissions:
      contents: write

    steps:
      - name: リポジトリをチェックアウト
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Python セットアップ
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: ライブラリインストール
        run: pip install requests

      - name: バス到着記録を実行
        run: python -u bus_tracker_final.py
        env:
          TZ: Asia/Tokyo

      - name: CSVをリポジトリにコミット
        if: always()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git pull --rebase origin main || true
          git add bus_arrival_log.csv || true
          git diff --staged --quiet || \
            git commit -m "🚌 バス到着記録 $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')"
          git push || true
