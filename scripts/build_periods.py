#!/usr/bin/env python3
import json, os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API="https://api.finmindtrade.com/api/v4/data"

def get_json(params, token=""):
    headers={"User-Agent":"ai-stock-radar/3.3-periods"}
    if token: headers["Authorization"]=f"Bearer {token}"
    with urlopen(Request(API+"?"+urlencode(params), headers=headers), timeout=30) as r:
        return json.loads(r.read().decode())

def mean(v): return sum(v)/len(v) if v else None

def ema(a,n):
    if not a: return None
    k=2/(n+1); e=a[0]; out=[e]
    for z in a[1:]: e=z*k+e*(1-k); out.append(e)
    return out

def indicators(closes, volumes):
    def sma(n): return mean(closes[-n:]) if len(closes)>=n else None
    ma5,ma20,ma60=sma(5),sma(20),sma(60)
    gains=[]; losses=[]
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]; gains.append(max(d,0)); losses.append(max(-d,0))
    rsi=None
    if len(gains)>=14:
        ag,al=mean(gains[-14:]),mean(losses[-14:]); rsi=100 if al==0 else 100-100/(1+ag/al)
    macd_hist=None
    if len(closes)>=35:
        e12,e26=ema(closes,12),ema(closes,26)
        ms=[a-b for a,b in zip(e12[-len(e26):],e26)]
        ss=ema(ms,9); macd_hist=ms[-1]-ss[-1]
    v20=mean(volumes[-20:]) if len(volumes)>=20 else None
    vr=mean(volumes[-5:])/v20 if v20 else None
    price=closes[-1]
    return {"price":round(price,2),"pct":round((price/closes[-2]-1)*100,2) if len(closes)>=2 else None,"ma5":round(ma5,2) if ma5 is not None else None,"ma20":round(ma20,2) if ma20 is not None else None,"ma60":round(ma60,2) if ma60 is not None else None,"ma20_gap_pct":round((price/ma20-1)*100,2) if ma20 else None,"ma60_gap_pct":round((price/ma60-1)*100,2) if ma60 else None,"rsi14":round(rsi,2) if rsi is not None else None,"macd_hist":round(macd_hist,3) if macd_hist is not None else None,"volume_ratio_5d_20d":round(vr,2) if vr is not None else None}

def bucket(rows, period):
    groups={}
    for r in rows:
        d=datetime.strptime(r["date"], "%Y-%m-%d").date()
        key=f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" if period=="W" else f"{d.year}-{d.month:02d}"
        groups.setdefault(key,[]).append(r)
    return [groups[k][-1] for k in sorted(groups)]

def build_for_stock(prices):
    prices=sorted(prices,key=lambda x:x.get("date","")); out={}
    for p in ("D","W","M"):
        data=prices if p=="D" else bucket(prices,p)
        if len(data)<2: continue
        closes=[float(x["close"]) for x in data]; vols=[float(x.get("Trading_Volume",0) or 0) for x in data]
        x=indicators(closes,vols); x["date"]=data[-1].get("date"); out[p]=x
    return out

def main():
    with open("data/latest.json",encoding="utf-8") as f: doc=json.load(f)
    token=os.environ.get("FINMIND_TOKEN","").strip()
    today=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    start=(today-timedelta(days=900)).strftime("%Y-%m-%d"); end=today.strftime("%Y-%m-%d")
    for s in doc.get("stocks",[]):
        try:
            data=get_json({"dataset":"TaiwanStockPrice","data_id":s["id"],"start_date":start,"end_date":end},token).get("data",[])
            s["periods"]=build_for_stock(data); s["period_data_version"]="V3.3"
        except Exception as e:
            s["periods"]={}; s["period_error"]=str(e)
    with open("data/latest.json","w",encoding="utf-8") as f:
        json.dump(doc,f,ensure_ascii=False,separators=(",",":")); f.write("\n")

if __name__=="__main__": main()
