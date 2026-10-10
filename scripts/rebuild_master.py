"""
종목 마스터 재생성 — data/daily 의 모든 날짜 파일을 훑어
종목별 최신 이름·시장, 최초·최종 관측일을 만든다.

  data/master/tickers.csv : code, name, market, first_seen, last_seen, days, status
  status = LISTED (마지막 거래일에 존재) / GONE (그 이후 사라짐: 상장폐지·이전상장 등)
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vai_arena import krx  # noqa: E402


def main():
    days = krx.saved_days()
    if not days:
        print("저장된 일별 데이터가 없습니다.")
        return 0
    parts = []
    for d in days:
        df = pd.read_csv(krx.daily_path(d), usecols=["date", "code", "name", "market"],
                         dtype=str, compression="gzip")
        parts.append(df)
    allr = pd.concat(parts, ignore_index=True)
    allr = allr.sort_values(["code", "date"])
    g = allr.groupby("code")
    master = pd.DataFrame({
        "name": g["name"].agg(lambda s: s.dropna().iloc[-1] if s.notna().any() else pd.NA),
        "market": g["market"].last(),
        "first_seen": g["date"].first(),
        "last_seen": g["date"].last(),
        "days": g.size(),
    }).reset_index()
    last_day = krx.iso(days[-1])
    master["status"] = (master["last_seen"] == last_day).map({True: "LISTED", False: "GONE"})
    out = krx.DATA / "master" / "tickers.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(out, index=False, encoding="utf-8")
    print(f"마스터 {len(master)}종목 (상장 {int((master.status=='LISTED').sum())} / "
          f"이탈 {int((master.status=='GONE').sum())}) · 기간 {days[0]}~{days[-1]} · {len(days)}일")
    return 0


if __name__ == "__main__":
    sys.exit(main())
