"""매일 장 마감 후 실행: 시세를 받아 신호를 계산하고 docs/data.json 으로 저장한다.
규칙은 backtest/ 에서 검증한 것과 동일하다.
"""
import sys, json, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

ETF_NAMES = {"069500": "KODEX 200", "229200": "KODEX 코스닥150", "133690": "TIGER 미국나스닥100", "143850": "TIGER 미국S&P500선물(H)",
             "148070": "KOSEF 국고채10년", "132030": "KODEX 골드선물(H)", "138230": "KOSEF 미국달러선물", "153130": "KODEX 단기채권"}
ETF_CLASS = {"069500": "코스피200", "229200": "코스닥150", "133690": "나스닥100", "143850": "S&P500(환헤지)",
             "148070": "국고채10년", "132030": "금", "138230": "달러", "153130": "단기채권(안전)"}
RISK = ["069500", "229200", "133690", "143850", "148070", "132030", "138230"]
SAFE = "153130"
P_RISKY = ["069500", "229200", "133690", "143850", "132030"]   # 퇴직연금: 위험자산(70% 한도)
P_BOND = "148070"
PENSION_FUNDS = {
    "069500": {"cls": "코스피200", "funds": ["삼성퇴직연금KOSPI200증권자투자신탁제1호[주식]Ce", "대신 KOSPI200 인덱스 증권 자투자신탁[주식] ClassC-Pe"], "kind": "국내"},
    "229200": {"cls": "코스닥150", "funds": ["KB스타코스닥150인덱스증권자투자신탁(주식-파생형)C-퇴직e"], "kind": "국내"},
    "133690": {"cls": "나스닥100", "funds": ["미래에셋미국나스닥100인덱스증권자투자신탁(주식)(UH) 종류C-P2e", "미래에셋미국나스닥100인덱스증권자투자신탁(주식)(H) 종류C-P2e"], "kind": "해외"},
    "143850": {"cls": "S&P500", "funds": ["신한미국S&P500인덱스증권자투자신탁(H)[주식-파생형](종류C-re)", "신한미국S&P500인덱스증권자투자신탁(UH)[주식-파생형](종류C-re)"], "kind": "해외"},
    "132030": {"cls": "금", "funds": ["미래에셋골드특별자산자투자신탁(금-재간접형) 종류C-P2e"], "kind": "해외"},
    "148070": {"cls": "장기 국채(안전자산)", "funds": ["미래에셋솔로몬장기국공채증권자투자신탁1호(채권) 종류 C-P2e", "삼성ABF코리아장기채권인덱스증권자투자신탁[채권](Cpe(퇴직연금))"], "kind": "국내"},
    "153130": {"cls": "단기채·예금(안전자산)", "funds": ["과학기술인공제회 퇴직연금 New 정기예금 1년", "신한베스트크레딧단기증권자투자신탁[채권](종류C-re)", "키움더드림단기채증권투자신탁[채권] Class C-P2e(퇴직연금)"], "kind": "국내"},
}
PENSION_FIXED = {"069500": 0.20, "133690": 0.20, "143850": 0.15, "132030": 0.15, "148070": 0.15, "153130": 0.15}

def month_scores(s_m):
    """월말 종가 시계열 -> 1·3·6·12개월 수익률 평균"""
    return sum(s_m / s_m.shift(k) - 1 for k in (1, 3, 6, 12)) / 4

def pick(score, cands, top=3):
    s = score[cands].dropna()
    floor = max(score[SAFE] if pd.notna(score.get(SAFE)) else 0, 0)
    return s[s > floor].nlargest(top)

def etf_weights(score, top=3):
    w = {c: round(1 / top, 4) for c in pick(score, RISK, top).index}
    w[SAFE] = round(1 - sum(w.values()), 4)
    return {k: v for k, v in w.items() if v > 0.0001}

def pension_weights(score, top=3):
    w = {c: 1 / top for c in pick(score, P_RISKY + [P_BOND], top).index}
    risky = sum(v for c, v in w.items() if c in P_RISKY)
    if risky > 0.7:
        for c in list(w):
            if c in P_RISKY: w[c] *= 0.7 / risky
    w[SAFE] = 1 - sum(w.values())
    return {k: round(v, 4) for k, v in w.items() if v > 0.0001}

def compute(px, uni):
    px = px.copy()
    for c in ("open", "high", "low"): px.loc[px[c] <= 0, c] = np.nan
    C = px.pivot(index="date", columns="code", values="close").sort_index()
    V = px.pivot(index="date", columns="code", values="volume").sort_index()
    asof = C.index[-1]
    # ---- 시장 필터 ----
    k = C["KOSPI"].dropna(); ma60, ma200 = k.rolling(60).mean().iloc[-1], k.rolling(200).mean().iloc[-1]
    market = {"kospi": round(float(k.iloc[-1]), 2), "ma60": round(float(ma60), 2), "ma200": round(float(ma200), 2),
              "on": bool(k.iloc[-1] > ma60 and k.iloc[-1] > ma200)}
    # ---- ETF 자산배분 ----
    E = C[[c for c in ETF_NAMES if c in C.columns]].ffill()
    m = E.resample("ME").last()
    cur_month = asof.to_period("M")
    done = m[m.index.to_period("M") < cur_month]                       # 지난달까지 = 확정
    sc_done = month_scores(done).iloc[-1]
    prov = pd.concat([done, E.iloc[[-1]]]); sc_prov = month_scores(prov).iloc[-1]   # 오늘 종가 기준 = 잠정
    last_done_day = E[E.index.to_period("M") < cur_month].index[-1]
    etf = {"assets": [{"code": c, "name": ETF_NAMES[c], "cls": ETF_CLASS[c], "close": float(E[c].iloc[-1]),
                       "score": None if pd.isna(sc_done[c]) else round(float(sc_done[c]) * 100, 1),
                       "score_now": None if pd.isna(sc_prov[c]) else round(float(sc_prov[c]) * 100, 1)} for c in E.columns],
           "confirmed": {"date": str(last_done_day.date()), "weights": etf_weights(sc_done)},
           "provisional": {"date": str(asof.date()), "weights": etf_weights(sc_prov)}}
    pension = {"confirmed": {"date": str(last_done_day.date()), "weights": pension_weights(sc_done)},
               "provisional": {"date": str(asof.date()), "weights": pension_weights(sc_prov)},
               "fixed": PENSION_FIXED, "funds": PENSION_FUNDS}
    # ---- 개별 종목 ----
    S = C.drop(columns=[c for c in list(ETF_NAMES) + ["KOSPI", "KOSDAQ"] if c in C.columns]); SV = V[S.columns]
    ma20, ma60s, ma200s = S.rolling(20).mean().iloc[-1], S.rolling(60).mean().iloc[-1], S.rolling(200).mean().iloc[-1]
    hi250 = S.rolling(250).max().iloc[-1]; vol20 = SV.rolling(20).mean().iloc[-1]; val20 = (S * SV).rolling(20).mean().iloc[-1]
    last, prev = S.iloc[-1], S.iloc[-2]; chg = last / prev - 1; mom120 = last / S.shift(120).iloc[-1] - 1
    up = (last > ma200s) & (ma60s > ma200s) & (val20 >= 2e9)
    ent = up & (last >= hi250) & (SV.iloc[-1] > 1.5 * vol20) & (chg < 0.15)
    names = dict(zip(uni["code"], uni["name"])); mkts = dict(zip(uni["code"], uni["market"]))
    cands = [{"code": c, "name": names.get(c, c), "market": mkts.get(c, ""), "close": float(last[c]), "stop": float(np.floor(last[c] * 0.92)),
              "mom120": round(float(mom120[c]) * 100, 1), "volx": round(float(SV.iloc[-1][c] / vol20[c]), 1), "chg": round(float(chg[c]) * 100, 1)}
             for c in mom120[ent].sort_values(ascending=False).index[:10]]
    stocks = {c: [names.get(c, c), float(last[c]), None if pd.isna(ma20[c]) else round(float(ma20[c]), 1), None if pd.isna(chg[c]) else round(float(chg[c]) * 100, 1)]
              for c in S.columns if pd.notna(last[c])}
    for a in etf["assets"]:
        c = a["code"]; stocks[c] = [a["name"], a["close"], round(float(E[c].rolling(20).mean().iloc[-1]), 1), round(float(E[c].iloc[-1] / E[c].iloc[-2] - 1) * 100, 1)]
    return {"asof": str(asof.date()), "generated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"),
            "market": market, "etf": etf, "pension": pension, "candidates": cands, "n_signals": int(ent.sum()), "stocks": stocks}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--local":              # 저장된 parquet으로 시험
        px = pd.read_parquet(sys.argv[2]); uni = pd.read_csv(sys.argv[3], dtype={"code": str})
    else:
        import fetch_history as fh
        fh.START = (dt.date.today() - dt.timedelta(days=600)).strftime("%Y%m%d")
        uni = fh.universe(); codes = list(uni["code"].head(600)) + ["KOSPI", "KOSDAQ"] + list(ETF_NAMES)
        def job(c):
            try: return fh.history(c)
            except Exception as e: print("fail", c, str(e)[:80]); return None
        with ThreadPoolExecutor(6) as ex: out = [d for d in ex.map(job, codes) if d is not None and len(d)]
        px = pd.concat(out, ignore_index=True); px["date"] = pd.to_datetime(px["date"].astype(str))
        for c in ("open", "high", "low", "close", "volume"): px[c] = pd.to_numeric(px[c], errors="coerce")
        if px["code"].nunique() < 500: raise SystemExit("수집 종목 수 부족 - 저장하지 않음")
    data = compute(px, uni)
    json.dump(data, open("docs/data.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print(data["asof"], data["market"], "후보", len(data["candidates"]), "ETF", data["etf"]["confirmed"], "연금", data["pension"]["confirmed"])
