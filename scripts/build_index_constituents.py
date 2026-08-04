"""
indices.json kataloğundan hono worker'ı için kompakt endeks bileşen haritası üretir.

Çıktı: hono/src/lib/index-constituents.json
Format: { "XU100": ["AEFES", "AKBNK", ...], ... }

Veri kaynağı KAP "Endeksler Listesi" CSV'sidir (build_kap_catalog.py ile derlenir);
bu script yalnızca hono'nun gömülü kopyasını yeniden üretir.
"""
import json
import os

BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(BASE, "data", "indices.json")
OUT = os.path.normpath(os.path.join(BASE, "..", "hono", "hono", "src", "lib", "index-constituents.json"))


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    out = {}
    total = 0
    for code, info in catalog.items():
        members = info.get("members") or []
        codes = [m.get("code") if isinstance(m, dict) else m for m in members if m]
        out[code] = codes
        total += len(codes)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    sizes = sorted((len(v) for v in out.values()), reverse=True)[:3]
    print(f"{len(out)} endeks, {total} bileşen -> {OUT}")
    print(f"En büyük 3: {sizes}")


if __name__ == "__main__":
    main()
