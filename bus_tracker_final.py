name: バス到着時刻記録（89番糸満線上り）

on:
  schedule:
    # JST 7:00〜10:00（UTC 22:00〜01:00）を30分ごとに起動
    - cron: '0 22 * * *'    # JST 07:00
    - cron: '30 22 * * *'   # JST 07:30
    - cron: '0 23 * * *'    # JST 08:00
    - cron: '30 23 * * *'   # JST 08:30
    - cron: '0 0 * * *'     # JST 09:00
    - cron: '30 0 * * *'    # JST 09:30
    - cron: '0 1 * * *'     # JST 10:00
  workflow_dispatch:         # 手動実行ボタン（テスト用）

# 同時実行を1つに制限（前の実行が終わるまで次を待機）
concurrency:
  group: bus-tracker
  cancel-in-progress: false  # 実行中のジョブはキャンセルせず待機

jobs:
  track:
    runs-on: ubuntu-latest
    timeout-minutes: 29      # 29分で自動停止（次の30分起動と重複しないよう）

    steps:
      - name: リポジトリをチェックアウト
        uses: actions/checkout@v4

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

      - name: 既存のCSVをダウンロード（蓄積用）
        uses: actions/download-artifact@v4
        continue-on-error: true
        with:
          name: bus-arrival-log
          path: .

      - name: CSVを保存（Artifacts）
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: bus-arrival-log
          path: bus_arrival_log.csv
          retention-days: 365    # 1年間保持
          overwrite: true

      - name: CSVをリポジトリにコミット（蓄積）
        if: always()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git pull --rebase origin main || true
          git add bus_arrival_log.csv || true
          git diff --staged --quiet || \
            git commit -m "🚌 バス到着記録 $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')"
          git push || true
