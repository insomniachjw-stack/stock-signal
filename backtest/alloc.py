"""월 1회 ETF 자산배분(모멘텀 순환) 백테스트. 월말 종가로 판단, lag 거래일 뒤 종가에 체결."""
import numpy as np, pandas as pd
RISK = ["069500", "229200", "133690", "143850", "148070", "132030", "138230"]
SAFE = "153130"
COST = 0.001   # 편도 거래비용 가정 (ETF는 거래세 없음)

def weights(px, top=3):
    m = px.resample("ME").last()
    score = sum(m / m.shift(k) - 1 for k in (1, 3, 6, 12)) / 4
    w = pd.DataFrame(0.0, index=m.index, columns=px.columns)
    for d in m.index:
        s = score.loc[d, RISK].dropna()
        s = s[s > max(score.loc[d, SAFE] if pd.notna(score.loc[d, SAFE]) else 0, 0)].nlargest(top)
        for c in s.index: w.loc[d, c] = 1 / top
        w.loc[d, SAFE] = 1 - w.loc[d].sum()
    # 실제 마지막 거래일 기준으로 맞춤
    last = px.groupby(px.index.to_period("M")).apply(lambda x: x.index[-1])
    w.index = last.values[:len(w)]
    return w

def simulate(px, w, lag=1, start="2015-01-01"):
    r = px.pct_change(fill_method=None).fillna(0)
    tgt = w.reindex(px.index).shift(lag).ffill().fillna(0)
    tgt.loc[tgt.sum(axis=1) == 0, SAFE] = 1
    held = tgt.shift(1).fillna(0)                 # 체결일 종가 이후부터 수익 반영
    turn = (tgt - tgt.shift(1)).abs().sum(axis=1).fillna(0)
    ret = (held * r).sum(axis=1) - turn * COST
    return (1 + ret.loc[start:]).cumprod()
