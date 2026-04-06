import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

BASE_URL = 'https://www.shanhaisan.com'


def extract_price(text):
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', text)
    return int(digits) if digits else None


def search(query):
    results = []
    try:
        url = f'{BASE_URL}/?s={requests.utils.quote(query)}&post_type=product'
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # WooCommerce standard product selectors
        products = soup.select('ul.products li.product, .woocommerce-loop-product__link')
        if not products:
            products = soup.select('.product-item, .product_item, article.product')

        for product in products[:10]:
            name_el = (
                product.select_one('.woocommerce-loop-product__title')
                or product.select_one('h2.woocommerce-loop-product__title')
                or product.select_one('h3')
                or product.select_one('h2')
            )
            # Price: may show sale/regular
            price_el = product.select_one('ins .woocommerce-Price-amount') or \
                       product.select_one('.woocommerce-Price-amount')
            link_el = product.select_one('a.woocommerce-loop-product__link') or product.select_one('a')
            img_el = product.select_one('img')

            if not name_el:
                continue

            name = name_el.get_text(strip=True)
            price = extract_price(price_el.get_text(strip=True)) if price_el else None
            link = link_el.get('href', '') if link_el else ''
            img = ''
            if img_el:
                img = img_el.get('data-src') or img_el.get('src') or ''

            out_of_stock_el = product.select_one('.out-of-stock, .stock.out-of-stock')
            in_stock = out_of_stock_el is None

            results.append({
                'name': name,
                'price': price,
                'link': link if link.startswith('http') else BASE_URL + link,
                'image': img,
                'in_stock': in_stock,
            })
    except Exception as e:
        print(f'[山海山] 錯誤: {e}')

    return results
