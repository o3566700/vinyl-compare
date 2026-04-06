import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

BASE_URL = 'https://www.candlelightrecords.tw'


def extract_price(text):
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', text)
    return int(digits) if digits else None


def _parse_items(soup, limit=10):
    results = []
    seen_hrefs = set()

    for card in soup.select('a.pt_items_block[href]'):
        href = card.get('href', '')
        if not href or href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        # Name from .pt_title or .pt_photo title attribute
        title_el = card.select_one('.pt_title')
        photo_el = card.select_one('.pt_photo')
        name = ''
        if title_el:
            name = title_el.get_text(strip=True)
        elif photo_el:
            name = photo_el.get('title', '').strip()
        if not name:
            continue

        # Price from .pt_forsale .js_origin_price (in-stock items)
        price_el = card.select_one('.js_origin_price, .pt_origin, [class*=pt_price]')
        price = extract_price(price_el.get_text(strip=True)) if price_el else None

        # Fallback: extract price from gtag onclick data
        if not price:
            onclick = card.get('onclick', '')
            m = re.search(r"'price'\s*:\s*'([\d.]+)'", onclick)
            if m:
                price = int(float(m.group(1)))

        # Sold-out check
        soldout_el = card.select_one('.pt_soldout b')
        in_stock = not (soldout_el and '已售完' in soldout_el.get_text())

        # Image from .pt_photo background-image style
        img = ''
        if photo_el:
            style = photo_el.get('style', '')
            m = re.search(r'url\(([^)]+)\)', style)
            if m:
                img = m.group(1).strip('"\'')

        link = href if href.startswith('http') else BASE_URL + href

        results.append({
            'name': name,
            'price': price,
            'link': link,
            'image': img,
            'in_stock': in_stock,
        })

        if len(results) >= limit:
            break

    return results


def search(query):
    results = []
    try:
        url = f'{BASE_URL}/search/{requests.utils.quote(query)}'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        results = _parse_items(soup, limit=10)
    except Exception as e:
        print(f'[燭光唱片] 錯誤: {e}')
    return results


def get_home_items(limit=12):
    """Fetch featured products from the candlelight homepage for recommendations."""
    items = []
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = _parse_items(soup, limit=limit)
    except Exception as e:
        print(f'[燭光首頁] 錯誤: {e}')
    return items
