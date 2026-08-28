#!/usr/bin/env python3
import json, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    headers={"User-Agent":"ai-stock-radar/3.3"}
    if token: headers["Authorization"]=f"Bearer {token}"
    req=Request(API+"?"+urlencode(dict(params)),headers=headers)
    with urlopen(req,timeout=30) as r: return json.loads(r.read().decode("utf-8"))

def rows_for(dataset, stock_id, start, end, token):
    return get_json({"dataset":dataset,"data_id":stock_id,"start_date":start,"end_date":end},token).get("data",[])

def mean(vals): return sum(vals)/len(vals) if vals else None

def technical(prices):
    closes=[float(x["close"]) for x in prices]
    vols=[float(x.get("Trading_Volume",0) or 0) for x in prices]
    def sma(n): return mean(closes[-n:]) if len(closes)>=n else None
    ma5,ma20,ma60=sma(5),sma(20),sma(60)
    ma20v=mean(vols[-20:]) if len(vols)>=20 else None
    volume_ratio=(vols[-5] if len(vols)>=5 else None)
    volume_ratio=(mean(vols[-5:])/ma20v) if ma20v else None
    gains=[]; losses=[]
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]; gains.append(max(d,0)); losses.append(max(-d,0))
    rsi=None
    if len(gains)>=14:
        ag=mean(gains[-14:]); al=mean(losses[-14:]); rsi=100 if al==0 else 100-(100/(1+ag/al))
    macd=None; signal=None; hist=None
    if len(closes)>=35:
        def ema_series(vals,n):
            a=2/(n+1); e=vals[0]; out=[e]
            for v in vals[1:]: e=v*a+e*(1-a); out.append(e)
            return out
        e12=ema_series(closes,12); e26=ema_series(closes,26)
        macd_series=[a-b for a,b in zip(e12[-len(e26):],e26)]
        sig=ema_series(macd_series,9)
        macd=macd_series[-1]; signal=sig[-1]; hist=macd-signal
    price=closes[-1]
    ma20_gap=(price/ma20-1)*100 if ma20 else None
    ma60_gap=(price/ma60-1)*100 if ma60 else None
    trend=0
    if ma20 and price>ma20: trend+=1
    if ma60 and price>ma60: trend+=1
    if ma20 and ma60 and ma20>ma60: trend+=1
    if rsi is not None:
        if 50<=rsi<=70: trend+=1
        elif rsi<35: trend+=1
        elif rsi>75: trend-=1
    if hist is not None and hist>0: trend+=1
    tech_score=max(35,min(98,65+trend*6))
    if ma20_gap is not None and ma20_gap>12: tech_score=max(35,tech_score-8)
    if ma20_gap is not None and ma20_gap<-8: tech_score=max(35,tech_score-4)
    if volume_ratio is not None and volume_ratio>=1.5: tech_score=min(98,tech_score+3)
    if rsi is not None and rsi>80: signal="過熱"
    elif rsi is not None and price>ma20 and ma20 and ma60 and ma20>ma60 and hist is not None and hist>0: signal="偏多／可研究"
    elif rsi is not None and rsi<35 and ma20 and price<ma20: signal="超跌觀察"
    elif ma20 and price<ma20: signal="等待站回20MA"
    else: signal="中性"
    return {"ma5":round(ma5,2) if ma5 else None,"ma20":round(ma20,2) if ma20 else None,"ma60":round(ma60,2) if ma60 else None,"ma20_gap_pct":round(ma20_gap,2) if ma20_gap is not None else None,"ma60_gap_pct":round(ma60_gap,2) if ma60_gap is not None else None,"rsi14":round(rsi,2) if rsi is not None else None,"macd":round(macd,3) if macd is not None else None,"macd_signal":round(signal if isinstance(signal,(int,float)) else 0,3) if macd is not None else None,"macd_hist":round(hist,3) if hist is not None else None,"volume_ratio_5d_20d":round(volume_ratio,2) if volume_ratio is not None else None,"technical_signal":signal,"technical_score":tech_score}

def fetch_stock(stock,token):
    today=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    price_start=(today-timedelta(days=150)).strftime("%Y-%m-%d"); fundamental_start=(today-timedelta(days=430)).strftime("%Y-%m-%d"); chip_start=(today-timedelta(days=35)).strftime("%Y-%m-%d"); end=today.strftime("%Y-%m-%d")
    prices=sorted(rows_for("TaiwanStockPrice",stock["id"],price_start,end,token),key=lambda x:x.get("date",""))
    if not prices: raise RuntimeError(f"{stock['id']} no price data")
    latest=prices[-1]; previous=prices[-2] if len(prices)>=2 else None; close=float(latest["close"]); prev=float(previous["close"]) if previous else None
    pct=round((close-prev)/prev*100,2) if prev else None
    tech=technical(prices)
    per_rows=sorted(rows_for("TaiwanStockPER",stock["id"],price_start,end,token),key=lambda x:x.get("date","")); per=per_rows[-1] if per_rows else {}
    fin_rows=rows_for("TaiwanStockFinancialStatements",stock["id"],fundamental_start,end,token); eps_map={}
    for r in fin_rows:
        if r.get("type")=="EPS" and r.get("value") not in (None,""):
            try: eps_map[r.get("date","")]=float(r["value"])
            except (TypeError,ValueError): pass
    eps_sorted=sorted(eps_map.items()); eps_latest=eps_sorted[-1][1] if eps_sorted else None; eps_ttm=round(sum(v for _,v in eps_sorted[-4:]),2) if eps_sorted else None; eps_date=eps_sorted[-1][0] if eps_sorted else None
    rev_rows=sorted(rows_for("TaiwanStockMonthRevenue",stock["id"],fundamental_start,end,token),key=lambda x:x.get("date","")); latest_rev=rev_rows[-1] if rev_rows else {}; revenue=float(latest_rev["revenue"]) if latest_rev.get("revenue") not in (None,"") else None; ry=latest_rev.get("revenue_year"); rm=latest_rev.get("revenue_month"); yoy=None
    if revenue is not None and ry and rm:
        for r in reversed(rev_rows[:-1]):
            if r.get("revenue_year")==int(ry)-1 and r.get("revenue_month")==int(rm):
                old=float(r["revenue"]); yoy=round((revenue-old)/old*100,2) if old else None; break
    chip_rows=sorted(rows_for("TaiwanStockInstitutionalInvestorsBuySellWide",stock["id"],chip_start,end,token),key=lambda x:x.get("date",""))[-20:]
    def net(r,p): return float(r.get(p+"_buy",0) or 0)-float(r.get(p+"_sell",0) or 0)
    foreign=sum(net(r,"Foreign_Investor") for r in chip_rows); trust=sum(net(r,"Investment_Trust") for r in chip_rows); dealer=sum(net(r,"Dealer_self")+net(r,"Dealer_Hedging")+net(r,"Dealer") for r in chip_rows); inst=foreign+trust+dealer
    chip_score=88 if inst>0 else 68
    return {**stock,"price":close,"pct":pct,"volume":latest.get("Trading_Volume"),"date":latest.get("date"),"price_source":"FinMind TaiwanStockPrice",**tech,"pe":float(per["PER"]) if per.get("PER") not in (None,"") else None,"pbr":float(per["PBR"]) if per.get("PBR") not in (None,"") else None,"dividend_yield":float(per["dividend_yield"]) if per.get("dividend_yield") not in (None,"") else None,"eps_latest":eps_latest,"eps_ttm":eps_ttm,"eps_date":eps_date,"revenue":revenue,"revenue_year":ry,"revenue_month":rm,"revenue_yoy":yoy,"revenue_date":latest_rev.get("date"),"foreign_20d_net":round(foreign),"trust_20d_net":round(trust),"dealer_20d_net":round(dealer),"institution_20d_net":round(inst),"institution_date":chip_rows[-1].get("date") if chip_rows else None,"chips_score":chip_score,"data_version":"V3.3"}

def empty_stock(s):
    return {**s,"price":None,"pct":None,"volume":None,"date":None,"price_source":"unavailable","ma5":None,"ma20":None,"ma60":None,"ma20_gap_pct":None,"ma60_gap_pct":None,"rsi14":None,"macd":None,"macd_signal":None,"macd_hist":None,"volume_ratio_5d_20d":None,"technical_signal":"無資料","technical_score":60,"pe":None,"pbr":None,"dividend_yield":None,"eps_latest":None,"eps_ttm":None,"eps_date":None,"revenue":None,"revenue_year":None,"revenue_month":None,"revenue_yoy":None,"revenue_date":None,"foreign_20d_net":None,"trust_20d_net":None,"dealer_20d_net":None,"institution_20d_net":None,"institution_date":None,"chips_score":70,"data_version":"V3.3"}

def main():
    token=os.environ.get("FINMIND_TOKEN","").strip(); now=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))); output={"version":"V3.3","updated_at":now.strftime("%Y-%m-%d %H:%M:%S"),"source":"FinMind","stocks":[]}; errors=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(fetch_stock,s,token):s for s in STOCKS}
        for f in as_completed(futures):
            s=futures[f]
            try: output["stocks"].append(f.result())
            except Exception as e: errors.append(f"{s['id']}: {e}"); output["stocks"].append(empty_stock(s))
    output["stocks"].sort(key=lambda x:x["id"])
    with open("data/latest.json","w",encoding="utf-8") as f: json.dump(output,f,ensure_ascii=False,separators=(",",":")); f.write("\n")
    print(json.dumps({"version":output["version"],"updated":len(output["stocks"])-len(errors),"failed":len(errors),"errors":errors},ensure_ascii=False))
    if not output["stocks"]: sys.exit(1)
if __name__=="__main__": main()
