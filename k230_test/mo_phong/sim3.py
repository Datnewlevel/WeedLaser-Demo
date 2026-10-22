# -*- coding: utf-8 -*-
"""Mo phong v3 - plant hieu chuan tu log that: DELAY=3, PXK=7.50, TAU=0.45.
Co day du ca che do toc do lan lenh vi tri 0xFD."""
CHU_KY=0.096
MSTEP=64
VI_TRI_NAC=6
VT_XUNG_GIAY=VI_TRI_NAC*(30000.0/(MSTEP*200))/60*(MSTEP*200)   # 3000 xung/s
class C:
    def __init__(s,**kw):
        s.DZ=20; s.KD=50; s.GAIN=0.060; s.PXNAC=20.0; s.PXK=7.50; s.MAX=10
        s.MEDIAN=3; s.DELAY=3; s.TAU=0.45; s.EMA=(7,10)
        s.VT=False; s.VT_NGUONG=120; s.VT_HESO=0.85; s.XUNG_PX=4.94; s.VT_BIEN_MS=60
        s.__dict__.update(kw)

def chay(c,nhieu,n,bearing,seed=0):
    import random
    rnd=random.Random(seed); off=rnd.randrange(len(nhieu)) if nhieu else 0
    turret=0.0; v=0.0; ema=0.0; chay_=False; buf=[]; hang=[]; log=[]
    khoa=-1
    for k in range(n):
        b=bearing(k)
        turret += v*c.PXK
        hang.append(b-turret+(nhieu[(off+k)%len(nhieu)] if nhieu else 0.0))
        if len(hang)>c.DELAY+1: hang.pop(0)
        do=hang[0]
        buf.append(do)
        if len(buf)>c.MEDIAN: buf.pop(0)
        e=sorted(buf)[len(buf)//2] if c.MEDIAN>1 else do
        a,d=c.EMA; ema=(a*e+(d-a)*ema)/d
        if abs(ema)>c.KD: chay_=True
        elif abs(ema)<=c.DZ: chay_=False
        sp=0; vt=0
        if k<khoa:
            v=0.0                     # dang thuc thi lenh vi tri: bo qua vong ngoai
            log.append((b-turret,0,ema)); continue
        if not chay_: sp=0
        elif c.VT and abs(ema)<=c.VT_NGUONG and abs(v)<0.01:
            vt=int(abs(ema)*c.XUNG_PX*c.VT_HESO)
        else:
            sp=max(1,min(c.MAX,int(abs(ema)*c.GAIN)))
            sp=max(1,min(sp,int((abs(ema)-c.DZ)/c.PXNAC)))
        if vt>=20:
            turret += (1 if ema>0 else -1)*vt/c.XUNG_PX     # driver tu chay, chinh xac
            giay=vt/VT_XUNG_GIAY+c.VT_BIEN_MS/1000.0
            khoa=k+max(1,int(giay/CHU_KY+0.999))
            v=0.0
        else:
            lenh=sp*(1 if ema>0 else -1)
            v += (lenh-v)*c.TAU
        log.append((b-turret,sp,ema))
    return log

def diem(log,c):
    n=len(log); e=[abs(r[0]) for r in log]; es=sorted(e)
    b=0;dang=False
    for r in log:
        if r[1]>0:
            if not dang: b+=1;dang=True
        else: dang=False
    best=0;cur=0
    for val in e:
        cur=cur+1 if val<=c.DZ else 0; best=max(best,cur)
    nua=e[n//2:]
    return dict(gat=100*b/(n*CHU_KY),med=es[n//2],p90=es[int(n*.9)],p99=es[int(n*.99)],
                trong=100*sum(1 for val in e if val<=c.DZ)/n,khoa=best*CHU_KY,
                on_dinh=max(nua))
