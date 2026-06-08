"""
Scraper for BCV (Banco Central de Venezuela) exchange rates.
Extracts official USD, EUR, CNY, TRY, RUB rates from bcv.org.ve
"""

import json
import os
import ssl
import urllib.request
from datetime import datetime, timezone

URL = "https://www.bcv.org.ve/"
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rates.json")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def fetch_html():
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=30, context=ssl_ctx)
    return resp.read().decode("utf-8")


def extract_between(text, start_marker, end_marker, from_pos=0):
    start = text.find(start_marker, from_pos)
    if start == -1:
        return None, -1
    content_start = start + len(start_marker)
    end = text.find(end_marker, content_start)
    if end == -1:
        return None, -1
    return text[content_start:end].strip(), end


def parse_rates(html):
    rates = {}
    currencies = {"EUR": "EUR ", "CNY": "CNY ", "TRY": "TRY", "RUB": "RUB", "USD": "USD"}

    for code, span_text in currencies.items():
        span_marker = f"<span> {span_text}</span>"
        idx = html.find(span_marker)
        if idx == -1:
            continue

        strong_marker = '<strong class="strong-tb">'
        strong_idx = html.find(strong_marker, idx)
        if strong_idx == -1:
            continue

        value_str, _ = extract_between(html, strong_marker, "</strong>", strong_idx)
        if value_str:
            rates[code] = float(value_str.replace(",", "."))

    date_str = None
    date_marker = "Fecha Valor:"
    date_idx = html.find(date_marker)
    if date_idx >= 0:
        span_start = html.find("<span", date_idx)
        if span_start >= 0:
            content_start = html.find(">", span_start) + 1
            span_end = html.find("</span>", content_start)
            if span_end >= 0:
                date_str = html[content_start:span_end].strip()

    return rates, date_str


def save_rates(rates, effective_date):
    data = {
        **rates,
        "effective_date": effective_date,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


def scrape():
    print(f"[{datetime.now().isoformat()}] Scraping BCV...")
    html = fetch_html()
    rates, effective_date = parse_rates(html)
    if not rates:
        print("ERROR: No rates found!")
        return False

    data = save_rates(rates, effective_date)
    print(f"USD: {data.get('USD', 'N/A')}")
    print(f"EUR: {data.get('EUR', 'N/A')}")
    print(f"Effective: {effective_date}")
    print(f"Saved to {DATA_FILE}")
    return True


if __name__ == "__main__":
    scrape()
