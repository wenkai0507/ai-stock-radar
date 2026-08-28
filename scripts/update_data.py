#!/usr/bin/env python3
import json, os, sys, time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.finmindtrade.com/api/v4/data"
STOCKS = [
    {"id":"2330","name":"台積電","category":"AI晶片","strategy":"核心","base":88,"logic":"AI算力製造核心"},
    {"id":"2408","name":"南亞科","category":"高階記憶體","strategy":"等拉回","base":84,"logic":"DRAM＋AI記憶體"},
    {"id":"2344","name":"華邦電","category":"記憶體","strategy":"等拉回","base":78,"logic":"記憶體景氣循環"},
    {"id":"8046","name":"南電","category":"ABF載板","strategy":"等拉回","base":86,"logic":"AI高階載板"},
    {"id":"1303","name":"南亞","category":"電子材料","strategy":"等拉回","base":85,"logic":"CCL/材料"},
    {"id":"6239","name":"力成","category":"先進封裝","strategy":"核心","base":82,"logic":"先進封裝"},
    {"id":"2383","name":"台光電","category":"高階CCL","strategy":"等拉回","base":83,"logic":"高速高頻材料"},
    {"id":"2313","name":"華通","category":"PCB","strategy":"等拉回","base":79,"logic":"HDI/AI伺服器"},
    {"id":"8358","name":"金居","category":"高階銅箔","strategy":"高波動","base":74,"logic":"高速傳輸材料"},
    {"id":"3017","name":"奇鋐","category":"散熱","strategy":"等拉回","base":84,"logic":"AI散熱"},
    {"id":"2308","name":"台達電","category":"電力/電源","strategy":"核心","base":86,"logic":"資料中心電力"},
    {"id":"3008","name":"大立光","category":"光學/CPO","strategy":"不追高","base":72,"logic":"光學/CPO高波動"},
]

def get_json(params, token=""):
    q = dict(params)
    headers = {"User-Agent": "ai-stock-radar/3.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = API + "?" + urlencode(q)
    req = Request(url, headers=headers)
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_stock(stock, token):
    # Pull a short window so we can calculate today's latest close and daily change.
    start = (datetime.now(timezone.utc) + timedelta(hours=8) - timedelta(days=7)).strftime("%Y-%m-%d")
    payload = get_json({"dataset":"TaiwanStockPrice", "data_id":stock["id"], "start_date":start}, token)
    rows = payload.get("data", [])
    rows = sorted(rows, key=lambda x: x.get("date", ""))
    if len(rows) < 1:
        raise RuntimeError(f"{stock['id']} no price data")
    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else None
    close = float(latest["close"])
    prev_close = float(previous["close"]) if previous else None
    pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else None
    return {
        **stock,
        "price": close,
        "pct": pct,
        "volume": latest.get("Trading_Volume"),
        "date": latest.get("date"),
        "price_source": "FinMind TaiwanStockPrice",
        "pe": None,
    }

def main():
    token = os.environ.get("FINMIND_TOKEN", "").strip()
    output = {"updated_at": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"), "source":"FinMind TaiwanStockPrice", "stocks":[]}
    errors = []
    for s in STOCKS:
        try:
            output["stocks"].append(fetch_stock(s, token))
        except Exception as e:
            errors.append(f"{s['id']}: {e}")
            # Keep the stock in the output so the dashboard never loses the watchlist.
            output["stocks"].append({**s, "price":None, "pct":None, "volume":None, "date":None, "price_source":"unavailable", "pe":None})
        time.sleep(0.25)
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(json.dumps({"updated":len(output["stocks"])-len(errors), "failed":len(errors), "errors":errors}, ensure_ascii=False))
    # Do not fail the whole workflow because one symbol had a transient data issue.
    if len(output["stocks"]) == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
