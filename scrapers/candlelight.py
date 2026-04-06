import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# Candlelight Records Taiwan
BASE_URL = 'https://www.candlelightrecords.com.tw'


def extract_price(text):
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', text)
    return int(digits) if digits else None


def search(query):
    results = []
    try:
        # Try common search URL patterns for Taiwan e-commerce
        search_urls = [
            f'{BASE_URL}/search?q={requests.utils.quote(query)}',
            f'{BASE_URL}/search?keyword={requests.utils.quote(query)}',
            f'{BASE_URL}/?s={requests.utils.quote(query)}&post_type=product',
        ]

        resp = None
        for url in search_urls:
            try:
                r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
                if r.status_code == 200:
                    resp = r
                    break
            except Exception:
                continue

        if not resp:
            return results

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Shopline / WooCommerce / custom selectors
        products = (
            soup.select('.product-item')
            or soup.select('.product-list .item')
            or soup.select('ul.products li.product')
            or soup.select('.goods-list .goods-item')
            or soup.select('[class*="product"]')
        )

        for product in products[:10]:
            name_el = (
                product.select_one('.product-title')
                or product.select_one('.goods-title')
                or product.select_one('h2')
                or product.select_one('h3')
                or product.select_one('[class*="title"]')
            )
            price_el = (
                product.select_one('.price')
                or product.select_one('.goods-price')
                or product.select_one('[class*="price"]')
            )
            link_el = product.select_one('a')
            img_el = product.select_one('img')

            if not name_el:
                continue

            name = name_el.get_text(strip=True)
            if not name:
                continue

            price = extract_price(price_el.get_text(strip=True)) if price_el else None
            link = link_el.get('href', '') if link_el else ''
            img = ''
            if img_el:
                img = img_el.get('data-src') or img_el.get('data-original') or img_el.get('src') or ''

            if link and not link.startswith('http'):
                link = BASE_URL + link
            if img and not img.startswith('http'):
                img = BASE_URL + img

            in_stock = 'out-of-stock' not in product.get('class', []) and \
                       not product.select('.sold-out, .out-of-stock')

            results.append({
                'name': name,
                'price': price,
                'link': link,
                'image': img,
                'in_stock': in_stock,
            })
    except Exception as e:
        print(f'[燭光唱片] 錯誤: {e}')

    return results
