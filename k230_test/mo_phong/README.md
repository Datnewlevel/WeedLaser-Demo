# Mo phong offline vong tracking

Chay tren PC, khong can phan cung. Dung de so sanh thuat toan truoc khi nap the.

## Quy trinh

1. `python rut_nhieu_sach.py` — doc `G:\run_log.txt`, rut vet nhieu detect that
   ra `noise_moi.json`. **Dung ban nay**, khong dung `rut_nhieu.py` (ban cu, loc sai).
2. `python sim3.py` — thu vien. Goi `chay(cfg, nhieu, n_khung, bearing_fn, seed)`
   roi `diem(log, cfg)`. **Dung ban nay**, khong dung `sim.py` (ban cu, do tre sai).

`sim.py` va `rut_nhieu.py` giu lai lam lich su. Chung dan den ba ket luan SAI.

---

## Nguyen tac song con

**Bat mo hinh tai hien duoc LOI THAT truoc khi dung no tim loi giai.**

Ban 10/09 khong lam viec nay: toi doan do tre = 1 khung trong khi that la 3-4.
Moi ket luan rut ra deu lech. Ban 11/09 hieu chuan `(DELAY, px/nac, TAU)` de khop
chu ky va bien do dao dong do duoc (mo phong 2.30s/157px vs that 2.10s/200px)
roi moi quet tham so.

---

## Nam cai bay khi rut vet nhieu — da mac DU CA NAM

**1. Log ghi EMA, khong phai sai so tho.**
Cot `err_x/err_y` la `ema_x/ema_y`. Rut nhieu tu do la lay tin hieu DA loc roi
lai loc them lan nua trong sim. Nghich dao duoc: `e[k] = (10*ema[k] - 3*ema[k-1])/7`.
Tu 10/09 log co them cot `tho_x/tho_y` ghi sai so chua loc -> khoi can nghich dao.

**2. Phai doi cum DUNG HAN >= 3 khung, khong phai 1 khung.**
Do tre 3-4 khung nghia la lenh = 0 mot khung thi cum VAN dang chay. Doi 1 khung
cho p99 = 69px; doi 3 khung cho p99 = 15px. **Toan bo 69px kia la cum tu chay.**

**3. Nhiem cheo giua hai truc.**
Do troi TILT khi chi TILT dung im nhung PAN dang quay ra -3.72 px/s (trong y nhu
tut do trong luc). Bat CA HAI truc cung dung im thi con -0.64 px/s, t = -0.2,
khong co y nghia thong ke. Khong he co hien tuong tut do trong luc.

**4. Thien lech cat duoi.**
Chi lay doan truc dung im = chi lay doan nhieu chua du lon de kich motor. Phai
giu ca khung KICH HOAT thi duoi phan bo moi dung.

**5. Do do tre phai dung `nac` CO DAU.**
`nac` trong log la do lon khong dau, chieu nam o dau cua `ema`. Hoi quy thang vao
`nac` cho R2 = 0 o moi do tre — trong nhu he thong vo ly, thuc ra cong thuc sai.
Dung `nac * sign(ema)` thi R2 len 0.86.

---

## Ket qua 11/09/2026 (model tag)

### Plant do duoc

```
do tre vong lap   3-4 khung (~0.35s)   R2 0.86 khi co dao dong
px moi nac/khung  TILT 7.5   PAN 4.79  (ly thuyet 9.72 / 6.21)
chu ky khung      0.096-0.099 s (10.1-10.4 fps)
nhieu detect that TILT p90 2  p99 15   PAN p90 3  p99 15
```

### Hai quy tac thiet ke

```
1)  deadzone  >  so_khung_tre x toc_do_nho_nhat
    TILT: 3 x 7.5 = 22.5 px  ->  deadzone 20 cu VI PHAM  ->  dao dong vo han

2)  GAIN x px_moi_nac  <=  0.22
    TILT cu: 0.060 x 7.5 = 0.45  ->  vuot gan gap doi
```

### Cai KHONG an

**Lenh vi tri `0xFD`** lam moi chi so te di, moi bien the, ca hai truc. No HO MACH
suot thoi gian thuc thi: chot quang duong tu MOT mau do roi di het, khong xem lai.
Che do toc do quyet dinh lai moi khung nen tu sua sai. Do phan giai 0.2px/xung
khong phai nut that — nhieu do va do tre moi la.

**Median 3 khung** khong dang gia: nhieu detect that chi p99 15px, ma bo loc cong
them 1 khung tre. Da tat (`LOC_N = 1`). Dau hieu canh bao bi bo qua luc do: kich
ban "nhay buoc 250px" cho p99 nhay tu 51 len 129.

**Ha KHOI_DONG** tren nhieu tho dung thi lam gat NHIEU hon, khong it di.

### Cai an

```
DEADZONE_Y  20 -> 30      GAIN_Y  0.060 -> 0.030      PX_MOI_NAC_Y  20 -> 38
```

Ket qua may that: nac dinh TILT 8-9 -> 4, vuot tam 9%, khoa lien tuc 25.1s,
laser ban tron mot phat 15s. Nguoi dung xac nhan het gat.

---

## Khi doi sang model co

Chay mot luot, roi lam dung thu tu nay:

1. `rut_nhieu_sach.py` -> vet nhieu moi
2. Do lai do tre bang tuong quan cheo (`nac` co dau!)
3. Kiem tra hai quy tac tren voi so moi
4. Quet tham so bang `sim3.py`

Tham so hien tai hieu chuan theo **model tag**. Nhieu, kich thuoc box va phan bo
confidence cua model co se khac.
