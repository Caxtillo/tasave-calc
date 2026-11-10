"""
Scraper for BCV (Banco Central de Venezuela) and Binance P2P exchange rates.
Extracts official USD, EUR, CNY, TRY, RUB rates from bcv.org.ve
and the Binance (P2P) dollar price from exchangemonitor.net.
"""

import json
import os
import re
import ssl
import urllib.request
from datetime import datetime, timezone

URL = "https://www.bcv.org.ve/"
URL_BINANCE = "https://exchangemonitor.net/venezuela/dolar-binance"
URL_DOLARAPI = "https://ve.dolarapi.com/v1/dolares"
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rates.json")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def fetch_html(url, retries=3):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            resp = urllib.request.urlopen(req, timeout=30, context=ssl_ctx)
            return resp.read().decode("utf-8")
        except Exception as exc:
            last_exc = exc
            print(f"WARN: fetch attempt {attempt}/{retries} failed: {exc}")
    raise last_exc


def parse_number(value_str):
    """BCV uses Venezuelan format: 1.006,60742688 -> 1006.60742688"""
    value_str = value_str.strip().replace(" ", "")
    if "," in value_str:
        value_str = value_str.replace(".", "").replace(",", ".")
    return float(value_str)


def parse_rates(html):
    # BCV cambia el markup con frecuencia: los <span> de la divisa ahora llevan
    # atributos inline (style="..."), así que buscamos por el id del bloque.
    blocks = {"USD": "dolar", "EUR": "euro", "CNY": "yuan", "TRY": "lira", "RUB": "rublo"}
    rates = {}

    for code, block_id in blocks.items():
        match = re.search(
            r'<div[^>]*\bid="%s"[^>]*>.*?<strong class="strong-tb">\s*([0-9.,]+)\s*</strong>'
            % block_id,
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            # Respaldo: buscar por el texto de la divisa antes del valor.
            match = re.search(
                r"<span[^>]*>\s*%s\s*</span>.*?<strong class=\"strong-tb\">\s*([0-9.,]+)\s*</strong>"
                % code,
                html,
                re.DOTALL | re.IGNORECASE,
            )
        if not match:
            print(f"WARN: rate for {code} not found in BCV page")
            continue

        try:
            rates[code] = parse_number(match.group(1))
        except ValueError as exc:
            print(f"WARN: could not parse {code} value {match.group(1)!r}: {exc}")

    date_str = None
    date_marker = "Fecha Valor:"
    date_idx = html.find(date_marker)
    if date_idx >= 0:
        span_start = html.find("<span", date_idx)
        if span_start >= 0:
            content_start = html.find(">", span_start) + 1
            span_end = html.find("</span>", content_start)
            if span_end >= 0:
                date_str = ' '.join(html[content_start:span_end].split())

    return rates, date_str


def parse_binance(html):
    """Extract Binance P2P dollar price (VES/USD) from exchangemonitor.net."""
    match = re.search(
        r"<meta name=\"description\" content=\"[^\"]*?es de ([0-9]+(?:\.[0-9]{3})*,[0-9]{2}) VES/USD",
        html,
        re.IGNORECASE,
    )
    if not match:
        return None
    return float(match.group(1).replace(".", "").replace(",", "."))


def parse_dolarapi(text):
    """Extract the parallel (Binance-like) dollar price from dolarapi.com."""
    data = json.loads(text)
    for item in data:
        if item.get("fuente") != "paralelo":
            continue
        value = item.get("promedio") or item.get("venta") or item.get("compra")
        if value:
            return round(float(value), 2)
    return None


def save_rates(rates, effective_date, binance=None):
    data = {
        **rates,
        "effective_date": effective_date,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if binance is not None:
        data["BINANCE"] = binance

    # Si los datos son idénticos al archivo actual, no se reescribe: evita un
    # commit (y un deploy de Vercel) cada 20 minutos cuando la tasa no cambia.
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            previous = json.load(f)
    except (OSError, ValueError):
        previous = {}
    if {k: v for k, v in previous.items() if k != "updated_at"} == {
        k: v for k, v in data.items() if k != "updated_at"
    }:
        print("Sin cambios respecto a rates.json (no se reescribe)")
        return previous

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


def scrape():
    print(f"[{datetime.now().isoformat()}] Scraping BCV...")
    html = fetch_html(URL)
    rates, effective_date = parse_rates(html)
    if "USD" not in rates:
        print("ERROR: USD rate not found, aborting (BCV markup may have changed)")
        return False

    binance = None
    # exchangemonitor bloquea con 403 a las IPs de GitHub Actions, así que
    # dolarapi.com es la fuente principal y exchangemonitor el respaldo.
    for url, parser in ((URL_DOLARAPI, parse_dolarapi), (URL_BINANCE, parse_binance)):
        try:
            print(f"[{datetime.now().isoformat()}] Scraping Binance via {url}...")
            binance = parser(fetch_html(url, retries=2))
            if binance is not None:
                break
            print(f"WARN: Binance price not found on {url}")
        except Exception as exc:
            print(f"WARN: Binance scrape failed on {url}: {exc}")

    data = save_rates(rates, effective_date, binance)
    print(f"USD: {data.get('USD', 'N/A')}")
    print(f"EUR: {data.get('EUR', 'N/A')}")
    print(f"Binance: {data.get('BINANCE', 'N/A')}")
    print(f"Effective: {effective_date}")
    print(f"Saved to {DATA_FILE}")
    return True


if __name__ == "__main__":
    import sys

    # Importante: salir con error para que el workflow de GitHub Actions se
    # marque en rojo si el scraping falla (antes quedaba en verde sin datos).
    sys.exit(0 if scrape() else 1)
