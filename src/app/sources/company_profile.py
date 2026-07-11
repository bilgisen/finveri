"""
İş Yatırım — Şirket Künyesi ve Ortaklık Yapısı scraper (on-demand).

Sayfa: sirket-karti.aspx?hisse={TICKER}
Şirket Künyesi: table.companyTag içinde th/td çiftleri
Ortaklık Yapısı:  OrtaklikYapisidata = [{name: '...', y: ...}] JS değişkeni
"""
import html
import json
import logging
import re
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.isyatirim.com.tr/",
}

_COMPANY_CARD_URL = "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx"


def fetch_company_profile(ticker: str) -> Optional[dict]:
    """
    İş Yatırım şirket kartı sayfasından künye ve ortaklık yapısını çeker.

    Returns:
        {
            "ticker": "AKBNK",
            "unvan": "Akbank",
            "kurulus": "27.12.1947",
            "faaliyet": "...",
            "telefon": "...",
            "faks": "...",
            "adres": "...",
            "shareholders": [{"name": "...", "share_pct": 32.15}, ...],
            "source": "isyatirim"
        }
    """
    code = ticker.upper().strip()
    if not code:
        return None

    url = f"{_COMPANY_CARD_URL}?hisse={code}"

    try:
        with httpx.Client(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            verify=False,
            headers=_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()

        # Is Yatirim sayfası ISO-8859-9 (Latin5) veya windows-1254 gönderebilir
        content_type = resp.headers.get("content-type", "")
        if "iso-8859-9" in content_type or "windows-1254" in content_type:
            page_text = resp.content.decode("iso-8859-9")
        else:
            page_text = resp.text

        kunye = _parse_kunye(page_text)
        shareholders = _parse_shareholders(page_text)

        return {
            "ticker": code,
            "unvan": kunye.get("unvan"),
            "kurulus": kunye.get("kurulus"),
            "faaliyet": kunye.get("faaliyet"),
            "telefon": kunye.get("telefon"),
            "faks": kunye.get("faks"),
            "adres": kunye.get("adres"),
            "shareholders": shareholders or None,
            "source": "isyatirim",
        }

    except httpx.HTTPStatusError as e:
        logger.warning("[company_profile] HTTP %s: %s", e.response.status_code, code)
        return None
    except httpx.HTTPError as e:
        logger.error("[company_profile] HTTP hatası (%s): %s", code, e)
        return None
    except Exception as e:
        logger.error("[company_profile] Beklenmeyen hata (%s): %s", code, e, exc_info=True)
        return None


def _parse_kunye(page_text: str) -> dict:
    raw = _parse_company_tag_table(page_text)
    if not raw:
        raw = _try_parse_escaped_company_tag(page_text)

    if not raw:
        return {}

    normalized = {}
    for k, v in raw.items():
        key = " ".join(str(k).split()).strip()
        if key:
            normalized[key] = v

    unvan = normalized.get("Ünvanı") or normalized.get("Ünvan")
    kurulus = normalized.get("Kuruluş") or normalized.get("Kurulus")
    faaliyet = (
        normalized.get("Faal Alanı")
        or normalized.get("Faaliyet Alanı")
        or normalized.get("Faal Alani")
    )
    telefon = normalized.get("Telefon")
    faks = normalized.get("Faks") or normalized.get("Fax")
    adres = normalized.get("Adres")

    return {
        "unvan": unvan,
        "kurulus": kurulus,
        "faaliyet": faaliyet,
        "telefon": telefon,
        "faks": faks,
        "adres": adres,
    }


def _parse_company_tag_table(page_text: str) -> dict:
    """Parse <table class="companyTag"> from raw HTML."""
    m = re.search(
        r'<table\s+class=["\']companyTag["\'][^>]*>(.*?)</table>',
        page_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return {}

    rows = re.findall(
        r'<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>',
        m.group(1),
        re.DOTALL,
    )
    result = {}
    for th, td in rows:
        key = re.sub(r'<[^>]+>', '', th).strip()
        val = re.sub(r'<[^>]+>', '', td).strip()
        if key and val:
            result[key] = val
    return result


def _try_parse_escaped_company_tag(page_text: str) -> dict:
    """
    Bazen sayfa içinde table HTML entity olarak gömülü gelir.
    Örn: &lt;table class="companyTag"&gt;...&lt;/table&gt;
    """
    spans = re.findall(
        r'(<span[^>]*>.*?(?:&lt;|<)table\s+class=["\']companyTag["\'].*?(?:&lt;|<)/table>.*?</span>)',
        page_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not spans:
        return {}

    for span_text in spans:
        m = re.search(
            r'((?:&lt;|<)table\s+class=["\']companyTag["\'][^>]*(?:&gt;|>).*?(?:&lt;|<)/table(?:&gt;|>))',
            span_text,
            re.DOTALL | re.IGNORECASE,
        )
        if m:
            table_html = html.unescape(m.group(1))
            return _parse_company_tag_table(table_html)
    return {}


def _parse_shareholders(page_text: str) -> list:
    """Parse OrtaklikYapisidata JS variable from page."""
    m = re.search(
        r"OrtaklikYapisidata\s*=\s*\[(.*?)\]\s*;",
        page_text,
        re.DOTALL,
    )
    if not m:
        return []

    inner = m.group(1)
    items = []
    for name, y in re.findall(
        r"\{\s*name\s*:\s*'([^']+)'\s*,\s*y\s*:\s*([-0-9.,]+)\s*\}",
        inner,
    ):
        clean_name = " ".join(name.split()).strip()
        if not clean_name:
            continue
        pct = _parse_float_tr(y)
        items.append({"name": clean_name, "share_pct": pct})
    return items


def _parse_float_tr(val: str) -> Optional[float]:
    """Parse number. Supports Turkish format (1.234,56) and standard dot format (40.75)."""
    if not val:
        return None
    try:
        clean = val.strip()
        if ',' in clean:
            clean = clean.replace(".", "").replace(",", ".")
        return float(clean)
    except (ValueError, TypeError):
        return None
