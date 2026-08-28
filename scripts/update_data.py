#!/usr/bin/env python3
import json, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
API="https://api.finmindtrade.com/api/v4/data"
STOCKS=[{"id":"2330","name":"台積電","category":"AI晶片","strategy":"核心","base":88,"logic":"AI算力製造核心"},{"id":"2408","name":"南亞科","category":"高階記憶體","strategy":"等拉回","base":84,"logic":"DRAM＋AI記憶體"},{"id":"2344","name":"華邦電","category":"記憶體","strategy":"等拉回","base":78,"logic":"記憶體景氣循環"},{"id":"8046","name":"南電","category":"ABF載板","strategy":"等拉回","base":86,"logic":"AI高階載板"},{"id":"1303","name":"南亞","category":"電子材料","strategy":"等拉回","base":85,"logic":"CCL/材料"},{"id":"6239","name":"力成","category":"先進封裝","strategy":"核心","base":82,"logic":"先進封裝"},{"id":"2383","name":"台光電","category":"高階CCL","strategy":"等拉回","base":83,"logic":"高速高頻材料"},{"id":"2313","name":"華通","category":"PCB","strategy":"等拉回","base":79,"logic":"HDI/AI伺服器"},{"id":"8358","name":"金居","category":"高階銅箔","strategy":"高波動","base":74,"logic":"高速傳輸材料"},{"id":"3017","name":"奇鋐","category":"散熱","strategy":"等拉回","base":84,"logic":"AI散熱"},{"id":"2308","name":"台達電","category":"電力/電源","strategy":"核心","base":86,"logic":"資料中心電力"},{"id":"3008","name":"大立光","category":"光學/CPO","strategy":"不追高","base":72,"logic":"光學/CPO高波動"}]
def get_json(p,t=""):
 h={"User-Agent":"ai-stock-radar/3.3"}
 if t:h["Authorization"]=f"Bearer {t}"
 with urlopen(Request(API+"?"+urlencode(p),headers=h),timeout=30) as r:return json.loads(r.read().decode())
def rows_for(ds,sid,start,end,t):return get_json({"dataset":ds,"data_id":sid,"start_date":start,"end_date":end},t).get("data",[])
def mean(v):return sum(v)/len(v) if v else None
def technical(prices):
 c=[float(x["close"]) for x in prices];v=[float(x.get("Trading_Volume",0) or 0) for x in prices];sma=lambda n:mean(c[-n:]) if len(c)>=n else None;ma5,ma20,ma60=sma(5),sma(20),sma(60);v20=mean(v[-20:]) if len(v)>=20 else None;vr=mean(v[-5:])/v20 if v20 else None
 g=[];l=[]
 for i in range(1,len(c)):
  d=c[i]-c[i-1];g.append(max(d,0));l.append(max(-d,0))
 rsi=None
 if len(g)>=14:
  ag=mean(g[-14:]);al=mean(l[-14:]);rsi=100 if al==0 else 100-100/(1+ag/al)
 macd_line=macd_signal=hist=None
 if len(c)>=35:
  def ema(a,n):
   k=2/(n+1);e=a[0];o=[e]
   for z in a[1:]:e=z*k+e*(1-k);o.append(e)
   return o
  e12=ema(c,12);e26=ema(c,26);ms=[a-b for a,b in zip(e12[-len(e26):],e26)];ss=ema(ms,9);macd_line=ms[-1];macd_signal=ss[-1];hist=macd_line-macd_signal
 price=c[-1];g20=(price/ma20-1)*100 if ma20 else None;g60=(price/ma60-1)*100 if ma60 else None;trend=(1 if ma20 and price>ma20 else 0)+(1 if ma60 and price>ma60 else 0)+(1 if ma20 and ma60 and ma20>ma60 else 0)
 if rsi is not None:trend+=1 if 50<=rsi<=70 or rsi<35 else -1 if rsi>75 else 0
 if hist is not None and hist>0:trend+=1
 score=max(35,min(98,65+trend*6))
 if g20 is not None and g20>12:score=max(35,score-8)
 if g20 is not None and g20<-8:score=max(35,score-4)
 if vr is not None and vr>=1.5:score=min(98,score+3)
 if rsi is not None and rsi>80:sig_text="過熱"
 elif rsi is not None and ma20 and ma60 and price>ma20 and ma20>ma60 and hist is not None and hist>0:sig_text="偏多／可研究"
 elif rsi is not None and rsi<35 and ma20 and price<ma20:sig_text="超跌觀察"
 elif ma20 and price<ma20:sig_text="等待站回20MA"
 else:sig_text="中性"
 return {"ma5":round(ma5,2) if ma5 else None,"ma20":round(ma20,2) if ma20 else None,"ma60":round(ma60,2) if ma60 else None,"ma20_gap_pct":round(g20,2) if g20 is not None else None,"ma60_gap_pct":round(g60,2) if g60 is not None else None,"rsi14":round(rsi,2) if rsi is not None else None,"macd":round(macd_line,3) if macd_line is not None else None,"macd_signal":round(macd_signal,3) if macd_signal is not None else None,"macd_hist":round(hist,3) if hist is not None else None,"volume_ratio_5d_20d":round(vr,2) if vr is not None else None,"technical_signal":sig_text,"technical_score":score}
def fetch_stock(s,t):
 today=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)));ps=(today-timedelta(days=150)).strftime("%Y-%m-%d");fs=(today-timedelta(days=430)).strftime("%Y-%m-%d");cs=(today-timedelta(days=35)).strftime("%Y-%m-%d");end=today.strftime("%Y-%m-%d");prices=sorted(rows_for("TaiwanStockPrice",s["id"],ps,end,t),key=lambda x:x.get("date",""))
 if not prices:raise RuntimeError(f"{s['id']} no price data")
 latest=prices[-1];prev=prices[-2] if len(prices)>1 else None;close=float(latest["close"]);pct=round((close-float(prev["close"]))/float(prev["close"])*100,2) if prev else None;tech=technical(prices);per=sorted(rows_for("TaiwanStockPER",s["id"],ps,end,t),key=lambda x:x.get("date",""));per=per[-1] if per else {}
 fin=rows_for("TaiwanStockFinancialStatements",s["id"],fs,end,t);em={}
 for r in fin:
  if r.get("type")=="EPS" and r.get("value") not in (None,""):
   try:em[r.get("date","")]=float(r["value"])
   except:pass
 es=sorted(em.items());eps_latest=es[-1][1] if es else None;eps_ttm=round(sum(x for _,x in es[-4:]),2) if es else None;eps_date=es[-1][0] if es else None;rev=sorted(rows_for("TaiwanStockMonthRevenue",s["id"],fs,end,t),key=lambda x:x.get("date",""));lr=rev[-1] if rev else {};revenue=float(lr["revenue"]) if lr.get("revenue") not in (None,"") else None;ry=lr.get("revenue_year");rm=lr.get("revenue_month");yoy=None
 if revenue is not None and ry and rm:
  for r in reversed(rev[:-1]):
   if r.get("revenue_year")==int(ry)-1 and r.get("revenue_month")==int(rm):
    old=float(r["revenue"]);yoy=round((revenue-old)/old*100,2) if old else None;break
 chips=sorted(rows_for("TaiwanStockInstitutionalInvestorsBuySellWide",s["id"],cs,end,t),key=lambda x:x.get("date",""))[-20:]
 def net(r,p):return float(r.get(p+"_buy",0) or 0)-float(r.get(p+"_sell",0) or 0)
 foreign=sum(net(r,"Foreign_Investor") for r in chips);trust=sum(net(r,"Investment_Trust") for r in chips);dealer=sum(net(r,"Dealer_self")+net(r,"Dealer_Hedging")+net(r,"Dealer") for r in chips);inst=foreign+trust+dealer
 return {**s,"price":close,"pct":pct,"volume":latest.get("Trading_Volume"),"date":latest.get("date"),"price_source":"FinMind TaiwanStockPrice",**tech,"pe":float(per["PER"]) if per.get("PER") not in (None,"") else None,"pbr":float(per["PBR"]) if per.get("PBR") not in (None,"") else None,"dividend_yield":float(per["dividend_yield"]) if per.get("dividend_yield") not in (None,"") else None,"eps_latest":eps_latest,"eps_ttm":eps_ttm,"eps_date":eps_date,"revenue":revenue,"revenue_year":ry,"revenue_month":rm,"revenue_yoy":yoy,"revenue_date":lr.get("date"),"foreign_20d_net":round(foreign),"trust_20d_net":round(trust),"dealer_20d_net":round(dealer),"institution_20d_net":round(inst),"institution_date":chips[-1].get("date") if chips else None,"chips_score":88 if inst>0 else 68,"data_version":"V3.3"}
def empty_stock(s):return {**s,"price":None,"pct":None,"volume":None,"date":None,"price_source":"unavailable","ma5":None,"ma20":None,"ma60":None,"ma20_gap_pct":None,"ma60_gap_pct":None,"rsi14":None,"macd":None,"macd_signal":None,"macd_hist":None,"volume_ratio_5d_20d":None,"technical_signal":"無資料","technical_score":60,"pe":None,"pbr":None,"dividend_yield":None,"eps_latest":None,"eps_ttm":None,"eps_date":None,"revenue":None,"revenue_year":None,"revenue_month":None,"revenue_yoy":None,"revenue_date":None,"foreign_20d_net":None,"trust_20d_net":None,"dealer_20d_net":None,"institution_20d_net":None,"institution_date":None,"chips_score":70,"data_version":"V3.3"}
def main():
 t=os.environ.get("FINMIND_TOKEN","").strip();now=datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)));out={"version":"V3.3","updated_at":now.strftime("%Y-%m-%d %H:%M:%S"),"source":"FinMind","stocks":[]};errors=[]
 with ThreadPoolExecutor(max_workers=6) as pool:
  fs={pool.submit(fetch_stock,s,t):s for s in STOCKS}
  for f in as_completed(fs):
   s=fs[f]
   try:out["stocks"].append(f.result())
   except Exception as e:errors.append(f"{s['id']}: {e}");out["stocks"].append(empty_stock(s))
 out["stocks"].sort(key=lambda x:x["id"])
 with open("data/latest.json","w",encoding="utf-8") as f:json.dump(out,f,ensure_ascii=False,separators=(",",":"));f.write("\n")
 print(json.dumps({"version":out["version"],"updated":len(out["stocks"])-len(errors),"failed":len(errors),"errors":errors},ensure_ascii=False))
 if not out["stocks"]:sys.exit(1)
if __name__=="__main__":main()
