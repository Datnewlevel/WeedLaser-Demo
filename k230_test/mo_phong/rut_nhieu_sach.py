import json
R=[]
for L in open(r"G:\run_log.txt"):
    L=L.strip()
    if not L or L.startswith("#"): continue
    p=L.split(",")
    if len(p)<24: continue
    try: R.append(dict(co=int(p[2]),nx=int(p[5]),ny=int(p[6]),vx=int(p[20]),vy=int(p[21]),
                       tx=int(p[22]),ty=int(p[23])))
    except: pass
res={}
for k,ten in (('tx','x'),('ty','y')):
    segs=[];cur=[];yen=0
    for i in range(len(R)):
        a=R[i]
        if a['nx']==0 and a['ny']==0 and a['vx']==0 and a['vy']==0 and a['co']:
            yen+=1
            if yen>=3: cur.append(a[k])
        else:
            yen=0
            if len(cur)>=14: segs.append(cur)
            cur=[]
    if len(cur)>=14: segs.append(cur)
    nz=[]
    for s in segs:
        for i,v in enumerate(s):
            w=s[max(0,i-5):i+6]
            nz.append(float(v-sorted(w)[len(w)//2]))
    a=sorted(abs(v) for v in nz); n=len(a); m=sum(nz)/n
    num=sum((nz[i]-m)*(nz[i+1]-m) for i in range(n-1)); den=sum((v-m)**2 for v in nz)
    print("%s: %d doan, %d mau | p90 %.0f p99 %.0f max %.0f | sigma %.2f | r1 %+.2f"%(
        ten.upper(),len(segs),n,a[int(n*.9)],a[int(n*.99)],a[-1],(den/n)**.5,num/den))
    res[ten]=nz
json.dump(res,open("noise_sach.json","w"))
print("\n(truoc day toi dung: X sigma 7.7  Y sigma 9.9 - bi lan chuyen dong cum)")
