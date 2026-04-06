import requests
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Origin': 'https://www.eslite.com',
    'Referer': 'https://www.eslite.com/',
}

API_URL = 'https://athena.eslite.com/api/v2/search'
IMG_BASE = 'https://www.eslite.com'


def extract_price(text):
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else None


def search(query):
    results = []
    try:
        params = {
            'keyword': query,
            'page': 1,
            'pageSize': 10,
        }
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for hit in data.get('hits', {}).get('hit', [])[:10]:
            fields = hit.get('fields', {})
            name = fields.get('name', '').strip()
            if not name:
                continue

            price = extract_price(fields.get('final_price', ''))
            link = fields.get('url', '')
            stock = fields.get('stock', '1')
            in_stock = str(stock) != '0'

            img_path = fields.get('product_photo_url', '')
            img = ''
            if img_path:
                img = img_path if img_path.startswith('http') else IMG_BASE + img_path

            results.append({
                'name': name,
                'price': price,
                'link': link,
                'image': img,
                'in_stock': in_stock,
            })

    except Exception as e:
        print(f'[誠品] 錯誤: {e}')

    return results
