"""공제회 상품명을 네이버 증권 펀드 코드와 대응시킨다(이름 유사도 기준)."""
import csv, json, re, time, difflib, urllib.parse as up, requests
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36", "Referer": "https://stock.naver.com/"}
S = requests.Session(); S.headers.update(UA)
def norm(s):
    s = s.replace("제 ", "제").replace("Class", "").replace("CLASS", "").replace("클래스", "").replace("종류", "")
    s = re.sub(r"제(\d+)호", r"\1", s); s = re.sub(r"(\d+)호", r"\1", s)
    return re.sub(r"[\s_\-\[\]\(\)\.]", "", s).lower()
def ac(q):
    for i in range(3):
        try:
            r = S.get("https://ac.stock.naver.com/ac?target=fund&q=" + up.quote(q), timeout=15); return [(x["code"], x["name"]) for x in r.json().get("items", []) if x.get("typeCode") == "fund"]
        except Exception: time.sleep(1)
    return []
out = {}
for row in csv.DictReader(open("collector/sema_funds.csv", encoding="utf-8")):
    name = row["name"]; target = norm(name); cands = {}
    qs = [name, name.replace("제1호", " 1").replace("제 1호", " 1"), re.sub(r"\s+", "", name)]
    base = re.split(r"[\[\(]", name)[0].strip()
    qs += [base, base.replace("제1호", "").replace("1호", "").strip()]
    for L in (len(base), 16, 12, 9, 7, 5):
        qs.append(name[:L])
    best = (0, None, None)
    for q in dict.fromkeys(q for q in qs if len(q) >= 4):
        for code, nm in ac(q):
            sc = difflib.SequenceMatcher(None, target, norm(nm)).ratio()
            if sc > best[0]: best = (sc, code, nm)
        if best[0] >= 0.985: break
    out[name] = {"code": best[1], "matched": best[2], "score": round(best[0], 3)}
    print(round(best[0], 2), "|", name, "=>", best[2], flush=True)
json.dump(out, open("collector/fund_codes.json", "w"), ensure_ascii=False, indent=1)
sc = [v["score"] for v in out.values()]; print("TOTAL", len(sc), ">=0.985:", sum(s >= 0.985 for s in sc), ">=0.9:", sum(s >= 0.9 for s in sc), "none:", sum(v["code"] is None for v in out.values()))
