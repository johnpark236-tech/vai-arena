"""
AI가 바로 읽을 수 있는 최신 요약 생성 — data/latest/

  snapshot.csv        오늘 전 종목 + 주요 파생지표 (거래대금 큰 순)
  market_summary.md   오늘 시장 요약 (지수, 상승·하락 수, 거래대금·급등·거래량 급증 상위)
  index_recent.csv    최근 120거래일 KOSPI·KOSDAQ 지수
  meta.json           기준일, 종목 수, 보유 데이터 기간

ChatGPT·Gemini는 수백 MB 원본 대신 이 폴더를 읽고 전략을 세운다.
파생지표는 원본가 기준이므로 액면분할·증자 직후 종목은 등락률이 왜곡될 수 있다.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vai_arena import krx  # noqa: E402

LOOKBACK = 260
OUT = krx.DATA / "latest"


def load_panel(days):
    parts = []
    for d in days:
        parts.append(pd.read_csv(krx.daily_path(d), compression="gzip", dtype={"code": str},
                                 usecols=["date", "code", "high", "close", "volume", "value"]))
    df = pd.concat(parts, ignore_index=True)
    return {c: df.pivot(index="date", columns="code", values=c).sort_index()
            for c in ("high", "close", "volume", "value")}


def pct(a, b):
    return (a / b - 1) * 100


def main():
    days = krx.saved_days()
    if not days:
        print("데이터 없음")
        return 0
    last = days[-1]
    today = krx.read_day(last)
    P = load_panel(days[-LOOKBACK:])
    C, H, V, A = P["close"], P["high"], P["volume"], P["value"]
    n = len(C)

    def back(k):
        return C.iloc[-1 - k] if n > k else pd.Series(np.nan, index=C.columns)

    feat = pd.DataFrame({
        "chg_5d": pct(C.iloc[-1], back(5)),
        "chg_20d": pct(C.iloc[-1], back(20)),
        "chg_60d": pct(C.iloc[-1], back(60)),
        "vol_ratio20": V.iloc[-1] / V.iloc[-21:-1].mean() if n > 20 else np.nan,
        "value_ma20": A.iloc[-21:-1].mean() if n > 20 else np.nan,
        "ma20": C.iloc[-20:].mean(),
        "ma60": C.iloc[-60:].mean() if n >= 60 else np.nan,
        "high_250": H.iloc[-251:-1].max() if n > 1 else np.nan,
    })
    feat["dist_ma20_pct"] = pct(C.iloc[-1], feat["ma20"])
    feat["dist_high250_pct"] = pct(C.iloc[-1], feat["high_250"])
    feat.index.name = "code"
    feat = feat.reset_index()

    snap = today.merge(feat, on="code", how="left")
    num = ["chg_5d", "chg_20d", "chg_60d", "vol_ratio20", "dist_ma20_pct", "dist_high250_pct"]
    snap[num] = snap[num].round(2)
    snap[["value_ma20", "ma20", "ma60", "high_250"]] = snap[["value_ma20", "ma20", "ma60", "high_250"]].round(0)
    snap = snap.drop(columns=["source"]).sort_values("value", ascending=False)

    OUT.mkdir(parents=True, exist_ok=True)
    snap.to_csv(OUT / "snapshot.csv", index=False, encoding="utf-8")

    # 지수
    idx_files = sorted((krx.DATA / "index").glob("*.csv"))
    idx = pd.concat([pd.read_csv(p) for p in idx_files]) if idx_files else pd.DataFrame()
    if not idx.empty:
        idx = idx.drop_duplicates(["date", "market"], keep="last").sort_values(["date", "market"])
        keep = sorted(idx["date"].unique())[-120:]
        idx[idx["date"].isin(keep)].to_csv(OUT / "index_recent.csv", index=False)

    # 요약 문서
    liq = snap[snap["value_ma20"] >= 1e9]
    up = int((today["change_pct"] > 0).sum())
    dn = int((today["change_pct"] < 0).sum())
    lines = [f"# 시장 요약 — {krx.iso(last)}", "",
             f"- 종목 수: {len(today):,} (KOSPI {int((today.market=='KOSPI').sum()):,} / "
             f"KOSDAQ {int((today.market=='KOSDAQ').sum()):,})",
             f"- 상승 {up:,} · 하락 {dn:,} · 보합 {len(today)-up-dn:,}",
             f"- 52주(250일) 신고가 종목: {int((snap['dist_high250_pct'] > 0).sum()):,}",
             f"- 보유 데이터: {krx.iso(days[0])} ~ {krx.iso(last)} ({len(days):,}거래일)", ""]
    if not idx.empty:
        lines += ["## 지수", "", "| 지수 | 종가 | 전일 대비 |", "|---|---|---|"]
        for mkt in ("KOSPI", "KOSDAQ"):
            s = idx[idx.market == mkt].tail(2)
            if len(s) == 2:
                c0, c1 = s["close"].iloc[0], s["close"].iloc[1]
                lines.append(f"| {mkt} | {c1:,.2f} | {pct(c1, c0):+.2f}% |")
        lines.append("")

    TEXT = {"code", "name", "market"}

    def cell(col, v):
        if col in TEXT:
            return "-" if pd.isna(v) else str(v)
        if pd.isna(v):
            return "-"
        if col == "value":
            return f"{v / 1e8:,.0f}"  # 억원
        return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}"

    def table(title, df, extra):
        cols = [("코드", "code"), ("종목", "name"), ("시장", "market"),
                ("종가", "close"), ("등락%", "change_pct")] + extra
        out = [f"## {title}", "", "| " + " | ".join(h for h, _ in cols) + " |", "|" + "---|" * len(cols)]
        for _, r in df.iterrows():
            out.append("| " + " | ".join(cell(c, r[c]) for _, c in cols) + " |")
        return out + [""]

    lines += table("거래대금 상위 20", snap.head(20), [("거래대금(억)", "value")])
    lines += table("상승률 상위 20 (20일 평균 거래대금 10억 이상)",
                   liq.sort_values("change_pct", ascending=False).head(20), [("거래량배수20", "vol_ratio20")])
    lines += table("거래량 급증 상위 20 (직전 20일 평균 대비)",
                   liq.sort_values("vol_ratio20", ascending=False).head(20), [("거래량배수20", "vol_ratio20")])
    lines += table("하락률 상위 20", liq.sort_values("change_pct").head(20), [("20일등락%", "chg_20d")])
    lines += ["---", "전 종목 상세는 `snapshot.csv`, 지수 추이는 `index_recent.csv` 참고.",
              "가격은 수정 전 원본가입니다. 액면분할·증자 직후 종목의 기간 등락률은 왜곡될 수 있습니다."]
    (OUT / "market_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    (OUT / "meta.json").write_text(json.dumps({
        "as_of": krx.iso(last), "stocks": len(today), "history_start": krx.iso(days[0]),
        "history_days": len(days), "generated_at": krx.now_kst().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"latest 생성: {krx.iso(last)} · {len(today)}종목 · 지표 {LOOKBACK}일 기준")
    return 0


if __name__ == "__main__":
    sys.exit(main())
