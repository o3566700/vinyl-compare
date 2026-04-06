import requests
from bs4 import BeautifulSoup
import re
import json

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://www.eslite.com/',
}

BASE_URL = 'https://www.eslite.com'


def extract_price(text):
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', text)
    return int(digits) if digits else None


def search(query):
    results = []
    try:
        # eslite search page - vinyl/黑膠 specific
        vinyl_query = f'{query} 黑膠' if '黑膠' not in query and 'vinyl' not in query.lower() else query
        url = f'{BASE_URL}/search?keyword={requests.utils.quote(vinyl_query)}'

        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Try to find JSON-LD structured data first
        json_ld_tags = soup.select('script[type="application/ld+json"]')
        for tag in json_ld_tags:
            try:
                data = json.loads(tag.string)
                if isinstance(data, dict) and data.get('@type') == 'ItemList':
                    for item in data.get('itemListElement', [])[:10]:
                        product = item.get('item', {})
                        name = product.get('name', '')
                        link = product.get('url', '')
                        img = product.get('image', '')
                        offer = product.get('offers', {})
                        price = None
                        if offer:
                            price_str = str(offer.get('price', ''))
                            price = extract_price(price_str)
                        in_stock = offer.get('availability', '').endswith('InStock') if offer else True

                        if name:
                            results.append({
                                'name': name,
                                'price': price,
                                'link': link,
                                'image': img if isinstance(img, str) else (img[0] if img else ''),
                                'in_stock': in_stock,
                            })
                    if results:
                        return results
            except Exception:
                continue

        # Fallback: HTML scraping
        product_cards = (
            soup.select('.product-card')
            or soup.select('.search-result-item')
            or soup.select('[class*="ProductCard"]')
            or soup.select('[class*="product-item"]')
            or soup.select('li[class*="item"]')
        )

        for card in product_cards[:10]:
            name_el = (
                card.select_one('[class*="name"]')
                or card.select_one('[class*="title"]')
                or card.select_one('h2')
                or card.select_one('h3')
            )
            price_el = (
                card.select_one('[class*="price"]')
                or card.select_one('[class*="Price"]')
            )
            link_el = card.select_one('a')
            img_el = card.select_one('img')

            if not name_el:
                continue

            name = name_el.get_text(strip=True)
            if not name:
                continue

            price = extract_price(price_el.get_text(strip=True)) if price_el else None
            link = link_el.get('href', '') if link_el else ''
            img = ''
            if img_el:
                img = img_el.get('data-src') or img_el.get('src') or ''

            if link and not link.startswith('http'):
                link = BASE_URL + link
            if img and not img.startswith('http'):
                img = BASE_URL + img

            results.append({
                'name': name,
                'price': price,
                'link': link,
                'image': img,
                'in_stock': True,
            })

    except Exception as e:
        print(f'[誠品] 錯誤: {e}')

    return results
