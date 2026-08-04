"""
Endeks kataloğu seed script'i.

KAP "Endeksler Listesi" (endeksler.csv) dokümanından 54 İş Yatırım endeksinin
bileşenlerini çıkarıp data/indices.json'a yazar. Mynet kullanılmaz.

Kullanım:
    python seed_indices.py            # dosyayı yazar
    python seed_indices.py --dry-run  # yazmaz, sadece rapor basar
    python seed_indices.py --csv <yol>
"""
import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Endeks kataloğu seed script'i (KAP)")
    parser.add_argument("--csv", default=None, help="KAP endeksler.csv yolu (varsayılan: C:\\Users\\ASUS\\hp\\endeksler.csv)")
    parser.add_argument("--dry-run", action="store_true", help="Dosyaya yazmaz, sadece özet basar")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))

    from build_kap_catalog import KAP_CSV_DEFAULT, main as build_main

    csv_path = args.csv or KAP_CSV_DEFAULT
    sys.argv = [sys.argv[0], "--csv", csv_path]
    if not args.dry_run:
        sys.argv += ["--write"]
    return build_main()


if __name__ == "__main__":
    raise SystemExit(main())
