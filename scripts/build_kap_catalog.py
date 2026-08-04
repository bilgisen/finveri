"""
KAP "Endeksler Listesi" (endeksler.csv) dosyasindan Is Yatirim endekslerinin
bilesen listelerini cikarip `data/indices.json`'i yeniden uretir.

Is Yatirim endeks listesi: https://jetborsa.com/api/market/indices (54 kod).
KAP CSV: `endeksler.csv` (cp1254, ';' ayrimli) — KAP "Endeksler Listesi"
dokumaninin duz metin disa aktarimidir. Excel ile birebir aynidir.

Uretici yalnizca 54 IY kodunu kapsar; KAP bilesenleri authoritative'dir.
X100S / X030S (agirlik sinirli varyantlar) KAP'ta ayri bolum olarak gecmez;
uyeleri sirayla XU100 / XU030 ile aynidir, onlardan turetilir.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import unicodedata

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
KAP_CSV_DEFAULT = r"C:\Users\ASUS\hp\endeksler.csv"
OUT_JSON = os.path.join(BASE, "data", "indices.json")

# Is Yatirim endeks listesi (https://jetborsa.com/api/market/indices).
IY_CODES = [
    "XU100", "X100S", "XYUZO", "XU030", "X030S", "XU050",
    "XSADA", "XBANA", "XSANK", "XSANT", "XSBAL", "XBANK", "XBLSM", "XSBUR",
    "XSDNZ", "XELKT", "XFINK", "XGMYO", "XGIDA", "XHARZ", "XUHIZ", "XHOLD",
    "XILTM", "XINSA", "XSIST", "XSIZM", "XSKAY", "XKMYA", "XKOBI", "XSKOC",
    "XSKON", "XKURY", "XMADN", "XUMAL", "XYORT", "XMANA", "XMESY", "XKAGT",
    "XSGRT", "XUSIN", "XSPOR", "XUSRD", "XTAST", "XSTKR", "XUTEK", "XTEKS",
    "XTMTU", "XTM25", "XTCRT", "XUTUM", "XTUMY", "XTRZM", "XULAS", "XYLDZ",
]

# KAP bolum adi (normallestirilmis) -> kod. Katalogdaki endeks adi KAP adi ile
# normallestirmeden sonra eslesmeyenler icin (kisaltma / farkli ad).
NORM_OVERRIDES = {
    "BANKA": "XBANK",  # katalog: "BIST Bankacilik Endeksi"
    "GAYRIMENKUL YAT ORT": "XGMYO",  # katalog: "GAYRIMENKUL YO"
    "MENKUL KIYM Y O": "XYORT",  # katalog: "MENKUL KIYM YO"
}

# X100S / X030S, KAP'ta ayri bolum olmadigindan kaynak endeksten turetilir.
DERIVED = {"X100S": "XU100", "X030S": "XU030"}


def norm(name: str) -> str:
    """Endeks adini karsilastirma icin normallestirir."""
    s = unicodedata.normalize("NFD", name.upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("ENDEKSI", "").replace("ENDEKS", "")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("BIST "):
        s = s[5:].strip()
    return s


def parse_kap_csv(path: str):
    """KAP CSV'yi bolum bazli okur: {bolum_adi: [ticker, ...]}."""
    text = open(path, "rb").read().decode("cp1254")
    if text.startswith("\ufeff"):
        text = text[1:]
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=";")
            if any((c or "").strip() for c in r)]
    sections = {}
    cur = None
    for r in rows:
        a = (r[0] or "").strip() if len(r) > 0 else ""
        b = (r[1] or "").strip() if len(r) > 1 else ""
        if b == "Kod" or a == "Sira" or a == "Endeksler Listesi":
            cur = None
            continue
        if not b and a:
            cur = a
            sections[cur] = []
            continue
        if cur is not None and b:
            sections[cur].append(b)
    return sections


def load_catalog(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def resolve_kap_members(sections: dict, catalog: dict) -> dict:
    """54 IY koduna KAP bilesenlerini esler. Returns {code: [tickers]}."""
    by_norm = {norm(name): members for name, members in sections.items()}
    result = {}
    for code in IY_CODES:
        if code in DERIVED:
            src = DERIVED[code]
            result[code] = result.get(src, [])
            continue
        cat_name = (catalog.get(code, {}).get("name") or code)
        n = norm(cat_name)
        members = by_norm.get(n)
        if members is None:
            # Katalog adi normallestirmede KAP ile eslesmedi; override dene.
            for raw, mem in sections.items():
                if NORM_OVERRIDES.get(norm(raw)) == code:
                    members = mem
                    break
        if members is None:
            raise ValueError(f"{code} icin KAP bolumu bulunamadi (ad: {cat_name!r}, norm: {n!r})")
        result[code] = members
    return result


def build_new_catalog(catalog: dict, kap_members: dict) -> dict:
    new = {}
    for code in IY_CODES:
        rec = dict(catalog.get(code, {}))
        rec["code"] = code
        rec["name"] = rec.get("name", code)
        rec.pop("mynet_url", None)
        rec["members"] = sorted(set(kap_members[code]))
        rec["member_count"] = len(rec["members"])
        new[code] = rec
    return new


def diff_report(old: dict, new: dict) -> None:
    print(f"{'code':6} {'name':34} {'kap':>4} {'old':>4} {'+':>3} {'-':>3}")
    total_kap = total_old = 0
    for code in IY_CODES:
        rec = new[code]
        old_members = set((old.get(code, {}).get("members") or []))
        new_members = set(rec["members"])
        added = sorted(new_members - old_members)
        removed = sorted(old_members - new_members)
        total_kap += len(new_members)
        total_old += len(old_members)
        flag = ""
        if added or removed:
            flag = "  <--"
        print(f"{code:6} {rec['name'][:32]:34} {len(new_members):4} {len(old_members):4} "
              f"{len(added):3} {len(removed):3}{flag}")
        for t in added[:8]:
            print(f"      + {t}")
        for t in removed[:8]:
            print(f"      - {t}")
    print(f"\n54 endeks: kap toplam {total_kap} / eski toplam {total_old}")


def main() -> int:
    ap = argparse.ArgumentParser(description="KAP bilesenleriyle 54 IY endeks katalogu uret")
    ap.add_argument("--csv", default=KAP_CSV_DEFAULT, help="KAP endeksler.csv yolu")
    ap.add_argument("--out", default=OUT_JSON, help="Cikti data/indices.json yolu")
    ap.add_argument("--write", action="store_true", help="Dosyayi gercekten yaz")
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        print(f"KAP CSV bulunamadi: {args.csv}", file=sys.stderr)
        return 1

    sections = parse_kap_csv(args.csv)
    print(f"KAP bolumleri: {len(sections)}")

    old = load_catalog(args.out)
    print(f"Mevcut katalog: {len(old)} endeks")

    kap_members = resolve_kap_members(sections, old)
    new = build_new_catalog(old, kap_members)

    # Beklenen kilit sayilar
    checks = {"XU100": 100, "XU030": 30, "XU050": 50, "XUTUM": 578, "XBANK": 12, "XTMTU": 101}
    ok = True
    for code, expect in checks.items():
        got = len(new.get(code, {}).get("members", []))
        status = "OK" if got == expect else f"BEKLENMEDI (expect {expect})"
        if got != expect:
            ok = False
        print(f"  check {code}: {got} {status}")
    if not ok:
        print("Kilit sayilar tutmadi; dosya yazilmayacak.", file=sys.stderr)
        return 2

    diff_report(old, new)

    if args.write:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, indent=2)
        print(f"\nYazildi: {args.out} ({len(new)} endeks)")
    else:
        print("\n(--write verilmedi; dosya yazilmadi)")

    # Hangi endekslerin eski katalogda olup da artik olmadigini raporla
    dropped = sorted(set(old.keys()) - set(IY_CODES))
    if dropped:
        print(f"\nKatalogdan dusen kodlar ({len(dropped)}): {dropped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
