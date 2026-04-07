"""
Ranking scrapers for additional vinyl record stores.

Provides top-10 lists from:
  - Candlelight Records new vinyl  (燭光唱片 全新黑膠)
  - Candlelight Records used vinyl (燭光唱片 二手老膠)
  - Candlelight Records 7-inch EP  (燭光唱片 7吋EP)
  - SHS Music hot vinyl            (山海山 黑膠唱片 熱門)

ESLite ranking is handled by scrapers/eslite_ranking.py.
"""
import re
import time
import traceback
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Browser-realistic headers
# ---------------------------------------------------------------------------
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': (
        'text/html,application/xhtml+xml,application/xml;q=0.9,'
        'image/avif,image/webp,image/apng,*/*;q=0.8,'
        'application/signed-exchange;v=b3;q=0.7'
    ),
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

CANDLELIGHT_BASE = 'https://www.candlelightrecords.tw'
SHSMUSIC_BASE = 'https://www.shsmusic.tw'

CANDLELIGHT_NEW_URL = f'{CANDLELIGHT_BASE}/category/163420'
CANDLELIGHT_USED_URL = f'{CANDLELIGHT_BASE}/category/163537'
CANDLELIGHT_EP_URL = f'{CANDLELIGHT_BASE}/category/163853'
SHSMUSIC_HOT_URL = f'{SHSMUSIC_BASE}/tw/product/index.php?kind=9&order=hot'


def _session_with_retry():
    """Return a requests.Session with automatic retry on transient errors."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


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
        session = _session_with_retry()
        r = session.get(url, headers=headers, timeout=20)
        r.encoding = 'utf-8'
        print(f'[燭光{label}] HTTP {r.status_code}, content length: {len(r.text)}')
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

            in_stock = item.select_one('.pt_soldout') is None

            results.append({
                'name': name,
                'price': price,
                'image': img,
                'link': item.get('href', ''),
                'in_stock': in_stock,
            })
        print(f'[燭光{label}] 解析到 {len(results)} 筆')
    except Exception as e:
        print(f'[燭光{label}] 錯誤: {e}')
        print(traceback.format_exc())
    return results


def candlelight_new_ranking():
    """燭光唱片 — 全新黑膠 綜合排行 top 10."""
    return _candlelight_scrape(CANDLELIGHT_NEW_URL, '全新黑膠')


def candlelight_used_ranking():
    """燭光唱片 — 二手老膠 綜合排行 top 10."""
    return _candlelight_scrape(CANDLELIGHT_USED_URL, '二手老膠')


def candlelight_ep_ranking():
    """燭光唱片 — 7吋黑膠 EP 排行 top 10."""
    return _candlelight_scrape(CANDLELIGHT_EP_URL, '7吋EP')


# ---------------------------------------------------------------------------
# SHS Music (山海山) — HTML scraping  +  fallback via search
# ---------------------------------------------------------------------------
def _shsmusic_parse_items(soup, label):
    """Parse product items from a shsmusic product list page."""
    results = []
    pro_list = soup.select_one('.pro-list')
    if not pro_list:
        print(f'[山海山{label}] 找不到 .pro-list，頁面片段: {soup.get_text()[:300]!r}')
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
            src = img_el.get('data-src') or img_el.get('src') or ''
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
    return results


def _shsmusic_fallback(label):
    """Fallback: search '黑膠' on shsmusic and return top 10 results."""
    from scrapers.shanhaisan import search as shs_search
    print(f'[山海山{label}] 啟用 fallback: 搜尋「黑膠」')
    try:
        items = shs_search('黑膠')
        print(f'[山海山{label}] fallback 取得 {len(items)} 筆')
        return items[:10]
    except Exception as e:
        print(f'[山海山{label}] fallback 也失敗: {e}')
        print(traceback.format_exc())
        return []


def _shsmusic_scrape(url, label):
    results = []
    try:
        headers = {
            **HEADERS,
            'Referer': SHSMUSIC_BASE + '/',
        }
        session = _session_with_retry()
        print(f'[山海山{label}] 請求 URL: {url}')
        r = session.get(url, headers=headers, timeout=20)
        print(f'[山海山{label}] HTTP {r.status_code}, content length: {len(r.content)}, encoding: {r.encoding}')
        r.encoding = 'utf-8'

        if r.status_code != 200:
            print(f'[山海山{label}] 非 200 狀態，啟用 fallback')
            return _shsmusic_fallback(label)

        soup = BeautifulSoup(r.text, 'html.parser')
        results = _shsmusic_parse_items(soup, label)
        print(f'[山海山{label}] 解析到 {len(results)} 筆')

        if not results:
            print(f'[山海山{label}] 解析結果為空，啟用 fallback')
            return _shsmusic_fallback(label)

    except Exception as e:
        print(f'[山海山{label}] 錯誤: {e}')
        print(traceback.format_exc())
        return _shsmusic_fallback(label)

    return results


def shanhaisan_ranking():
    """山海山 — 黑膠唱片 熱門 top 10."""
    return _shsmusic_scrape(SHSMUSIC_HOT_URL, '熱門')
