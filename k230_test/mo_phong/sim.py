# -*- coding: utf-8 -*-
"""Mo phong offline vong dieu khien TILT/PAN cua WeedLaser K230.
Nhieu detect lay THANG tu log that (giu nguyen bien do + tu tuong quan).
Vat ly cum: lenh toc do -> di PX_KHUNG_NAC px/khung; lenh vi tri -> di dung
so xung roi khoa truc trong thoi gian thuc thi. Do tre duong ong = LAT khung.
"""
import json, random

MSTEP=64
CHU_KY=0.096
DO_NAC_GIAY=(30000.0/(MSTEP*200))*6
XUNG_MOI_DO=(MSTEP*200)/360.0
VI_TRI_NAC=6
VI_TRI_XUNG_GIAY=VI_TRI_NAC*(30000.0/(MSTEP*200))/60*(MSTEP*200)
VI_TRI_BIEN_MS=60
EMA_NUM,EMA_DEN=7,10

NOISE=json.load(open("noise.json"))

class Cfg:
    def __init__(s,**kw):
        s.DEADZONE=20; s.KHOI_DONG=50; s.GAIN=0.060; s.PX_MOI_NAC=20.0
        s.PX_KHUNG_NAC=9.72; s.XUNG_MOI_PX=4.94; s.MAX_SPEED=10
        s.NGUONG_VI_TRI=120; s.VI_TRI_HE_SO=0.85; s.VI_TRI_BAT=True
        s.YEN_CAN=4; s.V_DUNG_YEN=6.0; s.VI_TRI_TRUOC=False  # thu tu nhanh
        s.MEDIAN=1; s.LAT=1
        s.__dict__.update(kw)

def chay_sim(cfg, noise, n_khung, bearing_fn, seed=0):
    rnd=random.Random(seed)
    off=rnd.randrange(len(noise))
    turret=0.0
    ema=None; chay=False; sp_truoc=0; yen=0; e_truoc=None
    khoa_den=-1          # khung ma lenh vi tri ket thuc
    lich=[]              # do tre duong ong: hang doi (bearing,turret) da chup
    buf=[]               # bo dem median
    log=[]
    for k in range(n_khung):
        bearing=bearing_fn(k)
        # --- cum chuyen dong theo lenh dang chay (tu khung truoc) ---
        # (da cap nhat o cuoi vong lap truoc)
        # --- camera chup: err tai thoi diem chup, tre LAT khung ---
        lich.append(bearing-turret+noise[(off+k)%len(noise)])
        if len(lich)>cfg.LAT+1: lich.pop(0)
        err_do=lich[0]
        buf.append(err_do)
        if len(buf)>cfg.MEDIAN: buf.pop(0)
        err=sorted(buf)[len(buf)//2] if cfg.MEDIAN>1 else err_do
        ema=err if ema is None else (EMA_NUM*err+(EMA_DEN-EMA_NUM)*ema)/EMA_DEN

        ranh = sp_truoc==0 and k>=khoa_den
        if e_truoc is not None and ranh:
            yen = yen+1 if abs(err-e_truoc)<cfg.V_DUNG_YEN else 0
        else: yen=0
        e_truoc=err

        if abs(ema)>cfg.KHOI_DONG: chay=True
        elif abs(ema)<=cfg.DEADZONE: chay=False

        sp=0; vt=0
        du_dk_vt = (cfg.VI_TRI_BAT and abs(ema)<=cfg.NGUONG_VI_TRI
                    and sp_truoc==0 and k>=khoa_den and yen>=cfg.YEN_CAN)
        if k<khoa_den:
            pass                              # dang thuc thi lenh vi tri
        elif cfg.VI_TRI_TRUOC and chay and du_dk_vt:
            vt=int(abs(ema)*cfg.XUNG_MOI_PX*cfg.VI_TRI_HE_SO)   # NHANH VI TRI TRUOC
        elif not chay:
            pass                              # trong deadzone -> dung
        elif du_dk_vt:
            vt=int(abs(ema)*cfg.XUNG_MOI_PX*cfg.VI_TRI_HE_SO)   # nhanh vi tri (thu tu cu)
        else:
            sp=int(abs(ema)*cfg.GAIN)
            sp=max(1,min(cfg.MAX_SPEED,sp))
            s_phanh=int((abs(ema)-cfg.DEADZONE)/cfg.PX_MOI_NAC)
            sp=max(1,min(sp,s_phanh))

        huong=1 if ema>0 else -1
        if vt>=20:
            turret+=huong*vt/cfg.XUNG_MOI_PX
            giay=vt/VI_TRI_XUNG_GIAY+VI_TRI_BIEN_MS/1000.0
            khoa_den=k+max(1,int(giay/CHU_KY+0.999))
            sp_truoc=0
        elif sp>0:
            turret+=huong*sp*cfg.PX_KHUNG_NAC
            sp_truoc=sp
        else:
            sp_truoc=0
        log.append((bearing-turret, sp, vt))
    return log

def cham_diem(log,cfg,ten):
    n=len(log); dur=n*CHU_KY
    e=[abs(r[0]) for r in log]
    es=sorted(e)
    # burst = chuoi khung lien tiep co ra lenh
    bursts=0; dang=False; ov=0; sgn_truoc=0
    for r in log:
        act = r[1]>0 or r[2]>0
        if act and not dang: bursts+=1; dang=True; sgn_truoc=(r[0]>0)-(r[0]<0)
        elif not act and dang:
            dang=False
            if sgn_truoc and ((r[0]>0)-(r[0]<0))==-sgn_truoc: ov+=1
    trong=sum(1 for v in e if v<=cfg.DEADZONE)
    # khoa lien tuc dai nhat (giay) khi luon trong deadzone
    best=0;cur=0
    for v in e:
        cur = cur+1 if v<=cfg.DEADZONE else 0
        best=max(best,cur)
    return dict(ten=ten,burst100=100*bursts/dur,median=es[n//2],p90=es[int(n*.9)],
                p99=es[int(n*.99)],trong=100*trong/n,vuot=100*ov/max(1,bursts),
                khoa=best*CHU_KY,nvt=sum(1 for r in log if r[2]>0))

def bang(rs):
    print("%-34s %8s %7s %7s %7s %8s %7s %7s"%("cau hinh","burst/100s","|e|med","|e|p90","|e|p99","%trong dz","%vuot","khoa_s"))
    for r in rs:
        print("%-34s %8.1f %7.0f %7.0f %7.0f %8.1f %7.0f %7.1f"%(
            r['ten'],r['burst100'],r['median'],r['p90'],r['p99'],r['trong'],r['vuot'],r['khoa']))
