import json
rows=[]
for L in open(r"G:\run_log.txt"):
    L=L.strip()
    if not L or L.startswith("#"): continue
    p=L.split(",")
    if len(p)<22: continue
    try: rows.append(dict(co=int(p[2]),ex=int(p[3]),ey=int(p[4]),nx=int(p[5]),ny=int(p[6]),
                          vx=int(p[20]),vy=int(p[21])))
    except: pass

# Log ghi EMA (7/10), khong phai sai so tho. Nghich dao lai:
#   ema[k] = (7*e[k] + 3*ema[k-1])/10  ->  e[k] = (10*ema[k] - 3*ema[k-1])/7
def go_ema(seq): return [(10*seq[i]-3*seq[i-1])/7.0 for i in range(1,len(seq))]

res={}
for name,ek,nk,vk in (("x","ex","nx","vx"),("y","ey","ny","vy")):
    segs=[];cur=[]
    for i in range(1,len(rows)):
        a,b=rows[i-1],rows[i]
        if not(a['co'] and b['co']): 
            if len(cur)>=14: segs.append(cur)
            cur=[];continue
        a_idle=a[nk]==0 and a[vk]==0
        if a_idle and b[nk]==0 and b[vk]==0: cur.append(b[ek])
        elif a_idle:
            cur.append(b[ek])
            if len(cur)>=14: segs.append(cur)
            cur=[]
        else:
            if len(cur)>=14: segs.append(cur)
            cur=[]
    if len(cur)>=14: segs.append(cur)
    nz=[]
    for s in segs:
        raw=go_ema(s)                     # ve sai so THO
        for i,v in enumerate(raw):
            w=raw[max(0,i-5):i+6]
            nz.append(v-sorted(w)[len(w)//2])
    a=sorted(abs(v) for v in nz); n=len(a); m=sum(nz)/n
    num=sum((nz[i]-m)*(nz[i+1]-m) for i in range(n-1)); den=sum((v-m)**2 for v in nz)
    print("%s THO: n=%d  p90 %.0f  p99 %.0f  max %.0f  sigma %.1f  r1 %+.2f"%(
        name.upper(),n,a[int(n*.9)],a[int(n*.99)],a[-1],(den/n)**.5,num/den))
    res[name]=nz
# so voi ban cu (da qua EMA)
print("\n(truoc khi sua, do tren tin hieu da qua EMA: X sigma 7.0  Y sigma 8.9)")
json.dump(res,open("noise_raw.json","w"))
print("Da ghi noise_raw.json")
