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
    headers = {"User-Agent": "ai-stock-radar/3.2"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = API + "?" + urlencode(q)
    req = Request(url, headers=headers)
    with urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def rows_for(dataset, stock_id, start, end, token):
    payload = get_json({"dataset": dataset, "data_id": stock_id, "start_date": start, "end_date": end}, token)
    return payload.get("data", [])

def fetch_stock(stock, token):
    today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    price_start = (today - timedelta(days=10)).strftime("%Y-%m-%d")
    fundamental_start = (today - timedelta(days=430)).strftime("%Y-%m-%d")
    chip_start = (today - timedelta(days=35)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    prices = sorted(rows_for("TaiwanStockPrice", stock["id"], price_start, end, token), key=lambda x: x.get("date", ""))
    if not prices:
        raise RuntimeError(f"{stock['id']} no price data")
    latest = prices[-1]
    previous = prices[-2] if len(prices) >= 2 else None
    close = float(latest["close"])
    prev_close = float(previous["close"]) if previous else None
    pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else None

    per_rows = sorted(rows_for("TaiwanStockPER", stock["id"], price_start, end, token), key=lambda x: x.get("date", ""))
    per = per_rows[-1] if per_rows else {}

    fin_rows = rows_for("TaiwanStockFinancialStatements", stock["id"], fundamental_start, end, token)
    eps_map = {}
    for r in fin_rows:
        if r.get("type") == "EPS" and r.get("value") not in (None, ""):
            try:
                eps_map[r.get("date", "")] = float(r["value"])
            except (TypeError, ValueError):
                pass
    eps_sorted = sorted(eps_map.items())
    eps_latest = eps_sorted[-1][1] if eps_sorted else None
    eps_ttm = round(sum(v for _, v in eps_sorted[-4:]), 2) if eps_sorted else None
    eps_date = eps_sorted[-1][0] if eps_sorted else None

    rev_rows = sorted(rows_for("TaiwanStockMonthRevenue", stock["id"], fundamental_start, end, token), key=lambda x: x.get("date", ""))
    latest_rev = rev_rows[-1] if rev_rows else {}
    revenue = float(latest_rev["revenue"]) if latest_rev.get("revenue") not in (None, "") else None
    revenue_year = latest_rev.get("revenue_year")
    revenue_month = latest_rev.get("revenue_month")
    yoy = None
    if revenue is not None and revenue_year and revenue_month:
        for r in reversed(rev_rows[:-1]):
            if r.get("revenue_year") == int(revenue_year) - 1 and r.get("revenue_month") == int(revenue_month):
                old = float(r["revenue"])
                if old:
                    yoy = round((revenue - old) / old * 100, 2)
                break

    chip_rows = rows_for("TaiwanStockInstitutionalInvestorsBuySellWide", stock["id"], chip_start, end, token)
    chip_rows = sorted(chip_rows, key=lambda x: x.get("date", ""))[-20:]
    def net(r, prefix):
        return float(r.get(prefix + "_buy", 0) or 0) - float(r.get(prefix + "_sell", 0) or 0)
    foreign_20 = sum(net(r, "Foreign_Investor") for r in chip_rows)
    trust_20 = sum(net(r, "Investment_Trust") for r in chip_rows)
    dealer_20 = sum(net(r, "Dealer_self") + net(r, "Dealer_Hedging") + net(r, "Dealer") for r in chip_rows)
    institution_20 = foreign_20 + trust_20 + dealer_20
    chip_date = chip_rows[-1].get("date") if chip_rows else None
    chip_score = 88 if institution_20 > 0 else 68

    return {
        **stock, "price": close, "pct": pct, "volume": latest.get("Trading_Volume"), "date": latest.get("date"),
        "price_source": "FinMind TaiwanStockPrice",
        "pe": float(per["PER"]) if per.get("PER") not in (None, "") else None,
        "pbr": float(per["PBR"]) if per.get("PBR") not in (None, "") else None,
        "dividend_yield": float(per["dividend_yield"]) if per.get("dividend_yield") not in (None, "") else None,
        "eps_latest": eps_latest, "eps_ttm": eps_ttm, "eps_date": eps_date,
        "revenue": revenue, "revenue_year": revenue_year, "revenue_month": revenue_month,
        "revenue_yoy": yoy, "revenue_date": latest_rev.get("date"),
        "foreign_20d_net": round(foreign_20, 0), "trust_20d_net": round(trust_20, 0),
        "dealer_20d_net": round(dealer_20, 0), "institution_20d_net": round(institution_20, 0),
        "institution_date": chip_date, "chips_score": chip_score, "data_version": "V3.2",
    }

def main():
    token = os.environ.get("FINMIND_TOKEN", "").strip()
    now_tw = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    output = {"version": "V3.2", "updated_at": now_tw.strftime("%Y-%m-%d %H:%M:%S"), "source": "FinMind", "stocks": []}
    errors = []
    for s in STOCKS:
        try:
            output["stocks"].append(fetch_stock(s, token))
        except Exception as e:
            errors.append(f"{s['id']}: {e}")
            output["stocks"].append({**s, "price": None, "pct": None, "volume": None, "date": None, "price_source": "unavailable", "pe": None, "pbr": None, "dividend_yield": None, "eps_latest": None, "eps_ttm": None, "eps_date": None, "revenue": None, "revenue_year": None, "revenue_month": None, "revenue_yoy": None, "revenue_date": None, "foreign_20d_net": None, "trust_20d_net": None, "dealer_20d_net": None, "institution_20d_net": None, "institution_date": None, "chips_score": 70, "data_version": "V3.2"})
        time.sleep(0.20)
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(json.dumps({"version": output["version"], "updated": len(output["stocks"]) - len(errors), "failed": len(errors), "errors": errors}, ensure_ascii=False))
    if len(output["stocks"]) == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
