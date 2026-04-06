"""
Ranking scrapers for additional vinyl record stores.

Provides top-10 lists from:
  - Candlelight Records new vinyl  (燭光唱片 全新黑膠)
  - Candlelight Records used vinyl (燭光唱片 二手老膠)
  - SHS Music hot vinyl            (山海山 黑膠唱片 熱門)

ESLite ranking is handled by scrapers/eslite_ranking.py.
"""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

CANDLELIGHT_BASE = 'https://www.candlelightrecords.tw'
SHSMUSIC_BASE = 'https://www.shsmusic.tw'

CANDLELIGHT_NEW_URL = f'{CANDLELIGHT_BASE}/category/163420'
CANDLELIGHT_USED_URL = f'{CANDLELIGHT_BASE}/category/163537'
SHSMUSIC_HOT_URL = f'{SHSMUSIC_BASE}/tw/product/index.php?kind=9&order=hot'


def _digits(text):
    s = re.sub(r'[^\d]', '', text)
    return int(s) if s else None


# ---------------------------------------------------------------------------
# Candlelight Records — HTML scraping
# ---------------------------------------------------------------------------
def _candlelight_price(item):
    """Parse the displayed price from a .pt_items_block element."""
    for sel in ('.js_sale_price', '.pt_sale', '.js_origin_price', '.pt_origin'):
        el = item.select_one(sel)
        if el:
            v = _digits(el.get_text())
            if v:
                return v
    return None


def _candlelight_scrape(url, label):
    results = []
    try:
        headers = {**HEADERS, 'Referer': CANDLELIGHT_BASE + '/'}
        r = requests.get(url, headers=headers, timeout=15)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')

        for item in soup.select('.pt_items_block')[:10]:
            name_el = item.select_one('.pt_title')
            name = name_el.get_text(strip=True) if name_el else ''
            if not name:
                continue

            price = _candlelight_price(item)

            photo = item.select_one('.pt_photo')
            img = ''
            if photo:
                m = re.search(r'url\(([^)]+)\)', photo.get('style', ''))
                if m:
                    img = m.group(1).strip('"\'')

            in_stock = item.select_one('.pt_sold_out') is None

            results.append({
                'name': name,
                'price': price,
                'image': img,
                'link': item.get('href', ''),
                'in_stock': in_stock,
            })
    except Exception as e:
        print(f'[燭光{label}] 錯誤: {e}')
    return results


def candlelight_new_ranking():
    """燭光唱片 — 全新黑膠 綜合排行 top 10."""
    return _candlelight_scrape(CANDLELIGHT_NEW_URL, '全新黑膠')


def candlelight_used_ranking():
    """燭光唱片 — 二手老膠 綜合排行 top 10."""
    return _candlelight_scrape(CANDLELIGHT_USED_URL, '二手老膠')


# ---------------------------------------------------------------------------
# SHS Music (山海山) — HTML scraping
# ---------------------------------------------------------------------------
def shanhaisan_ranking():
    """山海山 — 黑膠唱片 熱門 top 10."""
    results = []
    try:
        headers = {**HEADERS, 'Referer': SHSMUSIC_BASE + '/'}
        r = requests.get(SHSMUSIC_HOT_URL, headers=headers, timeout=15)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')

        pro_list = soup.select_one('.pro-list')
        if not pro_list:
            return results

        for item in pro_list.select('.item')[:10]:
            title_tw = item.select_one('.title .txt-tw')
            title_en = item.select_one('.title .txt-en')
            name = (title_tw.get_text(strip=True) if title_tw else '') or \
                   (title_en.get_text(strip=True) if title_en else '')
            if not name:
                continue

            pic_el = item.select_one('a.pic')
            href = pic_el.get('href', '') if pic_el else ''
            link = (SHSMUSIC_BASE + href) if href.startswith('/') else href

            img_el = item.select_one('a.pic img')
            img = ''
            if img_el:
                src = img_el.get('src', '')
                img = (SHSMUSIC_BASE + src) if src.startswith('/') else src

            # Prefer 特價 over 售價
            price = None
            for pel in item.select('.list-unstyled li'):
                text = pel.get_text(strip=True)
                v = _digits(text)
                if v and ('特價' in text or '售價' in text):
                    price = v
                    if '特價' in text:
                        break

            results.append({
                'name': name,
                'price': price,
                'image': img,
                'link': link,
                'in_stock': True,
            })
    except Exception as e:
        print(f'[山海山排行] 錯誤: {e}')
    return results
