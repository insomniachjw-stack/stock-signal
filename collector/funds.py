"""공제회 퇴직연금 상품의 기준가·수익률·구성종목을 네이버 증권에서 받아 docs/funds.json, docs/funds/<코드>.json 으로 저장."""
import csv, json, os, re, sys, time, difflib
from concurrent.futures import ThreadPoolExecutor
import requests

B = "https://m.stock.naver.com/front-api"
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36", "Referer": "https://stock.naver.com/"}
S = requests.Session(); S.headers.update(UA)

def get(path, **params):
    for i in range(3):
        try:
            r = S.get(B + path, params=params, timeout=20)
            if r.status_code == 200: return r.json().get("result")
            if r.status_code in (400, 404): return None
        except Exception: pass
        time.sleep(1 + i)
    return None

def norm(s):
    s = s.replace("제 ", "제").replace("Class", "").replace("CLASS", "").replace("클래스", "").replace("종류", "")
    s = re.sub(r"제(\d+)호", r"\1", s); s = re.sub(r"(\d+)호", r"\1", s)
    return re.sub(r"[\s_\-\[\]\(\)\.]", "", s).lower()

def hedge(s):
    return "UH" if re.search(r"\(?UH\)?", s) else ("H" if re.search(r"[\(\]]H[\)\[]|자투자신탁H|투자신탁H|\(H\)", s) else "")

def find_dicts(o, key="fundCode"):
    out = []
    if isinstance(o, dict):
        if key in o and ("fundName" in o or "className" in o): out.append(o)
        for v in o.values(): out += find_dicts(v, key)
    elif isinstance(o, list):
        for v in o: out += find_dicts(v, key)
    return out

def refine(name, m):
    """같은 펀드의 다른 클래스로 잡힌 경우, 클래스 목록에서 정확한 클래스를 찾는다."""
    if not m.get("code") or m["score"] < 0.9: return {"code": None, "match": "none"}
    if hedge(name) != hedge(m["matched"] or ""): return {"code": None, "match": "none"}
    if m["score"] >= 0.985: return {"code": m["code"], "match": "exact", "matched": m["matched"]}
    best = (m["score"], m["code"], m["matched"])
    for d in find_dicts(get("/fund/class/list/return", fundCode=m["code"]) or {}):
        nm = d.get("fundName") or ""
        sc = difflib.SequenceMatcher(None, norm(name), norm(nm)).ratio()
        if sc > best[0] and hedge(nm) == hedge(name): best = (sc, d["fundCode"], nm)
    return {"code": best[1], "match": "exact" if best[0] >= 0.985 else "class", "matched": best[2]}

def one(row, m):
    code = m["code"]; base = {"name": row["name"], "risk": int(row["risk"]), "risk_name": row["risk_name"], "company": row["company"],
                             "asset": row["asset"], "hedge": row["hedge"], "limit": float(row["limit"]), "code": code, "match": m["match"]}
    if not code: return base, None
    d = get("/fund/detail", fundCode=code)
    if not d: base["match"] = "none"; base["code"] = None; return base, None
    per = get("/fund/return/period", fundCode=code) or {}
    rets = {x["term"]: (None if x.get("fundReturn") is None else round(x["fundReturn"], 2)) for x in per.get("returns", [])}
    base.update({"nav": float(d["basePrice"]), "nav_date": d.get("tradeDate"), "chg": d.get("changePrice"),
                 "chg_pct": None if d.get("returnIndex") is None else round(d["returnIndex"], 2), "ret": rets,
                 "bm": d.get("benchmarkName"), "group": d.get("peerGroupName"), "matched": m.get("matched")})
    chart = get("/fund/basePrice/chart", fundCode=code, term="1y")
    term = get("/fund/term/list", fundCode=code) or {}
    alloc = get("/fund/portfolio/allocation", fundCode=code) or {}
    hold = alloc.get("result") if isinstance(alloc, dict) else alloc
    hold = [{"code": h.get("itemCode"), "name": h.get("itemName"), "w": round(h.get("weight") or 0, 4)} for h in (hold or [])][:15]
    asset = (get("/fund/asset/allocation", fundCode=code) or {}).get("assetTypes") or []
    tot = sum(a.get("weight") or 0 for a in asset) or 1
    detail = {"code": code, "name": row["name"], "chart_raw": chart, "holdings": hold,
              "assets": [{"name": a.get("assetTypeName"), "w": round((a.get("weight") or 0) / tot, 4)} for a in asset],
              "terms": {k: term.get(k) for k in ("standardTime", "buyStandardDaysBefore", "buyStandardDaysAfter", "redeemStandardDaysBefore", "redeemStandardDaysAfter", "redeemPaymentDaysBefore", "redeemPaymentDaysAfter")},
              "info": term.get("infoObject")}
    base["buy_days"] = term.get("buyStandardDaysAfter"); base["sell_days"] = term.get("redeemStandardDaysAfter"); base["pay_days"] = term.get("redeemPaymentDaysAfter")
    base["top"] = hold[:5]
    return base, detail

def chart_points(raw):
    """차트 응답에서 [날짜, 기준가] 목록을 뽑는다(응답 구조가 바뀌어도 견디도록 탐색)."""
    pts = []
    def walk(o):
        if isinstance(o, dict):
            dk = next((k for k in ("tradeDate", "date", "localDate") if k in o), None); pk = next((k for k in ("basePrice", "price", "value") if k in o), None)
            if dk and pk and o[pk] is not None:
                try: pts.append([str(o[dk])[:10], float(o[pk])])
                except Exception: pass
            else:
                for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(raw); pts.sort(); return pts

if __name__ == "__main__":
    rows = list(csv.DictReader(open("collector/sema_funds.csv", encoding="utf-8")))
    if len(sys.argv) > 1: rows = rows[:int(sys.argv[1])]
    codes = json.load(open("collector/fund_codes.json", encoding="utf-8"))
    cache_p = "collector/fund_map.json"; cache = json.load(open(cache_p, encoding="utf-8")) if os.path.exists(cache_p) else {}
    for r in rows:
        if r["name"] not in cache: cache[r["name"]] = refine(r["name"], codes.get(r["name"], {"code": None, "score": 0}))
    json.dump(cache, open(cache_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.makedirs("docs/funds", exist_ok=True)
    with ThreadPoolExecutor(5) as ex: res = list(ex.map(lambda r: one(r, cache[r["name"]]), rows))
    funds = []
    for i, (b, d) in enumerate(res):
        if d:
            if i == 0: print("SAMPLE chart_raw:", json.dumps(d["chart_raw"], ensure_ascii=False)[:600])
            d["chart"] = chart_points(d.pop("chart_raw")); b["n_chart"] = len(d["chart"])
            json.dump(d, open(f"docs/funds/{b['code']}.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        funds.append(b)
    ok = [f for f in funds if f.get("nav")]
    if len(ok) < len(funds) * 0.6: raise SystemExit(f"수집 성공 {len(ok)}/{len(funds)} - 저장하지 않음")
    json.dump({"asof": max(f["nav_date"] for f in ok), "funds": funds}, open("docs/funds.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    from collections import Counter
    print("funds", len(funds), "ok", len(ok), Counter(f["match"] for f in funds), "chart pts", Counter(min(f.get("n_chart", 0), 300) // 50 * 50 for f in ok))
    print("SAMPLE", json.dumps(ok[0], ensure_ascii=False)[:900])
    print("NONE", [f["name"] for f in funds if not f.get("nav")])
