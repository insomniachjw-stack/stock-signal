"""일봉 기반 스윙 규칙 백테스터. 신호는 종가로 판단하고 다음 거래일 시가에 체결한다."""
import sys, json
import numpy as np, pandas as pd

FEE = 0.0015      # 편도 수수료+슬리피지 가정
TAX = 0.0020      # 매도 시 거래세 가정
INDEX = ["KOSPI", "KOSDAQ", "069500", "229200", "133690", "143850", "148070", "132030", "138230", "153130"]

def load(path):
    px = pd.read_parquet(path)
    W = {c: px.pivot(index="date", columns="code", values=c).sort_index() for c in ("open", "high", "low", "close", "volume")}
    for k in ("open", "high", "low"): W[k] = W[k].where(W[k] > 0)   # 거래정지일의 0 가격 제거
    idx = W["close"][[c for c in INDEX if c in W["close"].columns]]
    for k in W: W[k] = W[k].drop(columns=[c for c in INDEX if c in W[k].columns])
    return W, idx

def rsi(close, n):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))

def indicators(W, idx):
    c, v = W["close"], W["volume"]
    I = {"ma5": c.rolling(5).mean(), "ma20": c.rolling(20).mean(), "ma60": c.rolling(60).mean(), "ma200": c.rolling(200).mean(),
         "rsi2": rsi(c, 2), "hi60": c.rolling(60).max(), "val20": (c * v).rolling(20).mean(),
         "vol20": v.rolling(20).mean(), "mom120": c / c.shift(120) - 1}
    k = idx["KOSPI"]
    I["mkt_on"] = (k > k.rolling(200).mean())
    return I

def run(W, idx, I, rule, start="2015-01-01", end=None, max_pos=10, stop=0.07, max_hold=None, mkt_filter=True, cash0=10_000_000, min_val=2e9, mkt2d=None):
    o, h, l, c = (W[k] for k in ("open", "high", "low", "close"))
    dates = c.loc[start:end].index
    cols = c.columns; ci = {k: i for i, k in enumerate(cols)}
    O, H, L, C = (x.values for x in (o, h, l, c))
    di = {d: i for i, d in enumerate(c.index)}
    up = ((c > I["ma200"]) & (I["ma60"] > I["ma200"]) & (I["val20"] >= min_val)).values
    if rule == "pullback":      # 상승추세 속 단기 급락 후 매수, 5일선 회복 시 매도
        ent = up & (I["rsi2"] < 10).values; rank = -I["rsi2"].values
        ext = (c > I["ma5"]).values
    elif rule == "breakout":    # 60일 신고가 + 거래량 증가, 20일선 이탈 시 매도
        ent = up & (c >= I["hi60"]).values & (W["volume"] > 1.5 * I["vol20"]).values & (c.pct_change() < 0.15).values
        rank = I["mom120"].values; ext = (c < I["ma20"]).values
    elif rule == "trend":       # 20일선 위로 복귀(눌림 후 반등), 60일선 이탈 시 매도
        ent = up & (c > I["ma20"]).values & (c.shift(1) <= I["ma20"].shift(1)).values & (I["ma20"] > I["ma60"]).values
        rank = I["mom120"].values; ext = (c < I["ma60"]).values
    mkt = I["mkt_on"].reindex(c.index).fillna(False).values
    if mkt2d is not None: ent = ent & mkt2d            # 종목별(시장별) 필터
    cash, pos, eq, trades = cash0, {}, [], []
    pend_buy, pend_sell = [], set()
    for d in dates:
        t = di[d]
        # 1) 전일 신호 체결 (시가)
        for j in list(pend_sell):
            if j in pos and not np.isnan(O[t, j]):
                p = pos.pop(j); px = O[t, j]; cash += p["sh"] * px * (1 - FEE - TAX)
                trades.append((cols[j], p["d"], d, p["px"], px, "신호"))
        pend_sell = set()
        if pend_buy:
            equity = cash + sum(p["sh"] * (C[t - 1, j] if not np.isnan(C[t - 1, j]) else p["px"]) for j, p in pos.items())
            for j in pend_buy:
                if len(pos) >= max_pos or j in pos or np.isnan(O[t, j]) or O[t, j] <= 0: continue
                if O[t, j] / C[t - 1, j] - 1 > 0.05: continue          # 갭 상승 5% 초과 시 추격 금지
                budget = min(equity / max_pos, cash / (1 + FEE)); sh = int(budget // O[t, j])
                if sh < 1: continue
                cash -= sh * O[t, j] * (1 + FEE); pos[j] = {"sh": sh, "px": O[t, j], "d": d, "n": 0}
        pend_buy = []
        # 2) 장중 손절
        for j in list(pos):
            p = pos[j]; p["n"] += 1
            sp = p["px"] * (1 - stop)
            if not np.isnan(L[t, j]) and L[t, j] <= sp and p["d"] != d:
                px = min(O[t, j], sp); cash += p["sh"] * px * (1 - FEE - TAX)
                trades.append((cols[j], p["d"], d, p["px"], px, "손절")); pos.pop(j)
        # 3) 종가 기준 신호
        for j, p in pos.items():
            if ext[t, j] or (max_hold and p["n"] >= max_hold): pend_sell.add(j)
        if (mkt2d is not None or mkt[t] or not mkt_filter):
            free = max_pos - len(pos) + len(pend_sell)
            if free > 0:
                cand = [j for j in np.where(ent[t])[0] if j not in pos]
                cand.sort(key=lambda j: -rank[t, j] if not np.isnan(rank[t, j]) else 1e9)
                pend_buy = cand[:free]
        eq.append(cash + sum(p["sh"] * (C[t, j] if not np.isnan(C[t, j]) else p["px"]) for j, p in pos.items()))
    return pd.Series(eq, index=dates), pd.DataFrame(trades, columns=["code", "in", "out", "pin", "pout", "why"])

def stats(eq, tr=None):
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    r = eq.pct_change().dropna()
    s = {"CAGR%": round(((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1) * 100, 1), "MDD%": round((eq / eq.cummax() - 1).min() * 100, 1),
         "변동성%": round(r.std() * 252 ** 0.5 * 100, 1), "최악의해%": round(eq.resample("YE").last().pct_change().min() * 100, 1)}
    if tr is not None and len(tr):
        net = tr["pout"] * (1 - FEE - TAX) / (tr["pin"] * (1 + FEE)) - 1
        s.update({"거래수": len(tr), "승률%": round((net > 0).mean() * 100, 1), "평균손익%": round(net.mean() * 100, 2),
                  "평균이익%": round(net[net > 0].mean() * 100, 2), "평균손실%": round(net[net <= 0].mean() * 100, 2),
                  "평균보유일": round(((tr["out"] - tr["in"]).dt.days).mean(), 1)})
    return s
