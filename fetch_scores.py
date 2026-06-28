#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROBOT TỰ LẤY TỈ SỐ — Hội Cựu KT3 AASC · WC2026
Chạy định kỳ trên GitHub Actions. Lấy tỉ số vòng bảng từ openfootball,
ghi vào Firebase (chỉ các trận chưa có tỉ số — KHÔNG đè trận đã nhập tay).

Không cần mở app, không cần đăng nhập admin. Robot ghi thẳng qua REST API
bằng FIREBASE_SECRET (lưu trong GitHub Secrets, không lộ ra ngoài).
"""
import json, sys, urllib.request, urllib.error, os

# ===== CẤU HÌNH (khớp với app) =====
FIREBASE_DB = "https://wc2026-cuu-kt3aasc-default-rtdb.asia-southeast1.firebasedatabase.app"
API_URL     = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
SECRET      = os.environ.get("FIREBASE_SECRET", "").strip()  # lấy từ GitHub Secrets

# app -> tên phía openfootball (giống NAME_MAP trong app)
NAME_MAP = {"Czechia":"Czech Republic","Korea Republic":"South Korea",
            "Türkiye":"Turkey","United States":"USA"}
def api_name(t): return NAME_MAP.get(t, t)

# Danh sách trận vòng bảng: [số_trận, đội_nhà, đội_khách] — trích từ app
GM = [
 [1,"Mexico","South Africa"],[2,"Korea Republic","Czechia"],[3,"Canada","Bosnia & Herzegovina"],[4,"United States","Paraguay"],
 [5,"Qatar","Switzerland"],[6,"Brazil","Morocco"],[7,"Haiti","Scotland"],[8,"Australia","Türkiye"],
 [9,"Germany","Curaçao"],[10,"Ivory Coast","Ecuador"],[11,"Netherlands","Japan"],[12,"Sweden","Tunisia"],
 [13,"Belgium","Egypt"],[14,"Iran","New Zealand"],[15,"Spain","Cape Verde"],[16,"Saudi Arabia","Uruguay"],
 [17,"France","Senegal"],[18,"Iraq","Norway"],[19,"Argentina","Algeria"],[20,"Austria","Jordan"],
 [21,"Portugal","DR Congo"],[22,"Uzbekistan","Colombia"],[23,"England","Croatia"],[24,"Ghana","Panama"],
 [25,"Czechia","South Africa"],[26,"Mexico","Korea Republic"],[27,"Switzerland","Bosnia & Herzegovina"],[28,"Canada","Qatar"],
 [29,"Scotland","Morocco"],[30,"Brazil","Haiti"],[31,"United States","Australia"],[32,"Türkiye","Paraguay"],
 [33,"Germany","Ivory Coast"],[34,"Ecuador","Curaçao"],[35,"Netherlands","Sweden"],[36,"Tunisia","Japan"],
 [37,"Belgium","Iran"],[38,"New Zealand","Egypt"],[39,"Spain","Saudi Arabia"],[40,"Uruguay","Cape Verde"],
 [41,"France","Iraq"],[42,"Norway","Senegal"],[43,"Argentina","Austria"],[44,"Jordan","Algeria"],
 [45,"Portugal","Uzbekistan"],[46,"Colombia","DR Congo"],[47,"England","Ghana"],[48,"Panama","Croatia"],
 [49,"Czechia","Mexico"],[50,"South Africa","Korea Republic"],[51,"Switzerland","Canada"],[52,"Bosnia & Herzegovina","Qatar"],
 [53,"Scotland","Brazil"],[54,"Morocco","Haiti"],[55,"Türkiye","United States"],[56,"Paraguay","Australia"],
 [57,"Curaçao","Ivory Coast"],[58,"Ecuador","Germany"],[59,"Japan","Sweden"],[60,"Tunisia","Netherlands"],
 [61,"Egypt","Iran"],[62,"New Zealand","Belgium"],[63,"Cape Verde","Saudi Arabia"],[64,"Uruguay","Spain"],
 [65,"Norway","France"],[66,"Senegal","Iraq"],[67,"Jordan","Argentina"],[68,"Algeria","Austria"],
 [69,"Colombia","Portugal"],[70,"DR Congo","Uzbekistan"],[71,"Panama","England"],[72,"Croatia","Ghana"]
]

def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent":"wc2026-robot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def fb_get(path):
    url = f"{FIREBASE_DB}/{path}.json?auth={SECRET}"
    try:
        return http_get_json(url)
    except urllib.error.HTTPError as e:
        print(f"  [cảnh báo] đọc {path} lỗi {e.code}"); return None

def fb_put(path, value):
    url = f"{FIREBASE_DB}/{path}.json?auth={SECRET}"
    data = json.dumps(value).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT",
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status

def main():
    if not SECRET:
        print("✗ Thiếu FIREBASE_SECRET (chưa cấu hình GitHub Secret)."); sys.exit(1)

    # 1) lấy dữ liệu openfootball -> map (đội1|đội2) -> tỉ số ft
    print("→ Đang tải openfootball...")
    try:
        data = http_get_json(API_URL)
    except Exception as e:
        print(f"✗ Không tải được openfootball: {e}"); sys.exit(0)  # thoát êm, lần sau thử lại
    idx = {}
    knum = {}   # trận knockout: num -> ft (openfootball đánh số num trùng số trận app: 73-104)
    for m in data.get("matches", []):
        ft = (m.get("score") or {}).get("ft")
        if not ft: continue
        idx[f'{m.get("team1")}|{m.get("team2")}'] = ft
        n = m.get("num")
        if n is not None:
            try: knum[int(n)] = ft
            except (TypeError, ValueError): pass
    print(f"  nguồn có {len(idx)} trận đã có kết quả ({len(knum)} trận có num/KO).")

    # 2) đọc các tỉ số đã có trên Firebase (để KHÔNG đè trận đã nhập tay)
    existing = fb_get("game/sc") or {}
    def done(num):
        return str(num) in existing or num in existing

    # 3a) VÒNG BẢNG: map theo cặp tên đội
    filled = 0
    for num, home, away in GM:
        if done(num): continue
        ft = idx.get(f"{api_name(home)}|{api_name(away)}")
        if not ft: continue
        try:
            fb_put(f"game/sc/{num}", [int(ft[0]), int(ft[1])])
            print(f"  ✓ Trận {num} (bảng): {home} {ft[0]}-{ft[1]} {away}")
            filled += 1
        except Exception as e:
            print(f"  ✗ Ghi trận {num} lỗi: {e}")

    # 3b) KNOCKOUT (trận 73-104): map theo num — KHÔNG cần tên đội.
    # Lưu ý: ft là tỉ số 90 phút. Nếu hòa phải đá luân lưu thì admin tự chọn
    # đội thắng luân lưu trong app (robot chỉ ghi tỉ số 90 phút).
    for num in range(73, 105):
        if done(num): continue
        ft = knum.get(num)
        if not ft: continue
        try:
            fb_put(f"game/sc/{num}", [int(ft[0]), int(ft[1])])
            note = " (hòa 90' — admin chọn đội thắng luân lưu trong app)" if int(ft[0])==int(ft[1]) else ""
            print(f"  ✓ Trận {num} (KO): {ft[0]}-{ft[1]}{note}")
            filled += 1
        except Exception as e:
            print(f"  ✗ Ghi trận {num} lỗi: {e}")
    print(f"→ Xong. Đã điền {filled} trận mới.")

if __name__ == "__main__":
    main()
