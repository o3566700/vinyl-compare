import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

BASE_URL = 'https://www.shsmusic.tw'


def extract_price(text):
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', text)
    return int(digits) if digits else None


def _parse_items(soup, limit=10):
    results = []
    seen_nums = set()

    for item in soup.select('div.item[data-num]'):
        num = item.get('data-num', '')
        if num in seen_nums:
            continue
        seen_nums.add(num)

        title_tw = item.select_one('.title .txt-tw')
        title_en = item.select_one('.title .txt-en')
        author_tw = item.select_one('.author .txt-tw')
        author_en = item.select_one('.author .txt-en')
        price_el = item.select_one('.price b')
        link_el = item.select_one('a.pic')
        img_el = item.select_one('a.pic img')

        name_tw = title_tw.get_text(strip=True) if title_tw else ''
        name_en = title_en.get_text(strip=True) if title_en else ''
        artist_tw = author_tw.get_text(strip=True) if author_tw else ''
        artist_en = author_en.get_text(strip=True) if author_en else ''

        # Build display name: prefer English title if available
        if name_en and artist_en:
            name = f'{artist_en} - {name_en}'
        elif name_en:
            name = name_en
        elif name_tw and artist_tw:
            name = f'{artist_tw} - {name_tw}'
        else:
            name = name_tw or name_en
        if not name:
            continue

        # Full text for relevance filtering (Chinese + English)
        search_text = ' '.join(filter(None, [name_tw, name_en, artist_tw, artist_en]))

        price_text = price_el.get_text(strip=True) if price_el else ''
        price = extract_price(price_text)

        href = link_el.get('href', '') if link_el else ''
        link = href if href.startswith('http') else BASE_URL + href

        img = ''
        if img_el:
            src = img_el.get('data-src') or img_el.get('src') or ''
            img = src if src.startswith('http') else BASE_URL + src

        # 洽詢 (price on request) or no price → treat as out of stock
        in_stock = bool(price)

        results.append({
            'name': name,
            'price': price,
            'link': link,
            'image': img,
            'in_stock': in_stock,
            'search_text': search_text,
        })

        if len(results) >= limit:
            break

    return results


def search(query):
    results = []
    try:
        url = f'{BASE_URL}/tw/product/index.php?kw={requests.utils.quote(query)}'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content.decode('utf-8', errors='replace'), 'html.parser')
        results = _parse_items(soup, limit=10)
    except Exception as e:
        print(f'[山海山] 錯誤: {e}')
    return results


def get_home_items(limit=12):
    """Fetch New Arrivals from the shanhaisan homepage for recommendations."""
    items = []
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content.decode('utf-8', errors='replace'), 'html.parser')
        items = _parse_items(soup, limit=limit)
    except Exception as e:
        print(f'[山海山首頁] 錯誤: {e}')
    return items
