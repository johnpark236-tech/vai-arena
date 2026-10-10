"""
매일 전체 업데이트 (평일 18:10 KST, GitHub Actions)

1) 오늘 시세 수집 (실패 시 10분 간격 재시도)
2) 최근 15거래일 중 빠진 날이 있으면 자동으로 다시 받아 메움 (자가 복구)
3) 종목 마스터 재생성
4) AI용 최신 요약(data/latest/) 재생성
5) 결과를 data/_status/last_collect.json 에 기록

  python scripts/collect_daily.py               # 오늘
  python scripts/collect_daily.py --date 20261012
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from vai_arena import krx  # noqa: E402

GAP_DAYS = 15


def status(payload):
    p = krx.DATA / "_status" / "last_collect.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    payload["finished_at"] = krx.now_kst().isoformat(timespec="seconds")
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(script):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], text=True)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--wait", type=int, default=600)
    a = ap.parse_args()
    today = (a.date or krx.now_kst().strftime("%Y%m%d")).replace("-", "")

    krx.preload_names(krx.DATA / "master" / "tickers.csv")
    result = {"date": today, "today": None, "repaired": [], "repair_failed": [], "notes": []}

    # 1) 오늘
    for i in range(1, a.retries + 1):
        try:
            result["today"] = krx.collect_one(today)
            break
        except Exception as ex:
            result["notes"].append(f"시도 {i}: {str(ex)[:200]}")
            print(f"[오늘] 실패 {i}/{a.retries}: {ex}", flush=True)
            if i < a.retries:
                time.sleep(a.wait)
    print(f"[오늘] {today}: {result['today']}", flush=True)

    # 2) 빠진 날 메우기
    start = (pd.Timestamp(krx.iso(today)) - timedelta(days=GAP_DAYS * 2)).strftime("%Y%m%d")
    for d in krx.candidate_days(start, today):
        if d == today or krx.daily_path(d).exists() or d in krx.known_holidays():
            continue
        try:
            r = krx.collect_one(d, allow_fdr_today=False)
            if r == "saved":
                result["repaired"].append(d)
                print(f"[복구] {d} 저장", flush=True)
        except Exception as ex:
            result["repair_failed"].append(d)
            print(f"[복구] {d} 실패: {ex}", flush=True)

    # 3) 마스터, 4) 최신 요약
    if result["today"] in ("saved", "exists") or result["repaired"]:
        run("rebuild_master.py")
        run("build_latest.py")

    ok = result["today"] in ("saved", "exists", "holiday")
    result["ok"] = ok
    status(result)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
