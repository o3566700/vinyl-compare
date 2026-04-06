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

# Keywords that indicate a product is NOT vinyl (books, DVDs, CDs, magazines)
NON_VINYL_KEYWORDS = ['書', '雜誌', 'dvd', 'blu-ray', ' cd ', '(cd)', 'bd ', '電影', '影碟']
VINYL_KEYWORDS = ['黑膠', 'lp', 'vinyl', '唱片', '12"', '7"', '12吋', '7吋']


def extract_price(text):
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', str(text))
    return int(digits) if digits else None


def is_likely_vinyl(name):
    """Return True if the product is likely vinyl, False if clearly non-vinyl."""
    name_lower = name.lower()
    # If name contains non-vinyl keywords (and not a vinyl keyword to override), skip
    has_vinyl = any(kw in name_lower for kw in VINYL_KEYWORDS)
    has_non_vinyl = any(kw in name_lower for kw in NON_VINYL_KEYWORDS)
    if has_non_vinyl and not has_vinyl:
        return False
    return True


def fetch_itunes_cover(name):
    """Fallback: fetch album artwork from iTunes Search API."""
    try:
        # Strip vinyl-specific suffixes to improve iTunes match accuracy
        term = re.sub(r'黑膠|vinyl|唱片|\d{3}g', '', name, flags=re.IGNORECASE).strip()
        resp = requests.get(
            'https://itunes.apple.com/search',
            params={'term': term, 'media': 'music', 'entity': 'album', 'limit': 1, 'country': 'TW'},
            timeout=5,
        )
        data = resp.json()
        if data.get('results'):
            artwork = data['results'][0].get('artworkUrl100', '')
            if artwork:
                return artwork.replace('100x100bb', '300x300bb')
    except Exception:
        pass
    return ''


def search(query):
    results = []
    try:
        # Always append 黑膠 to restrict to vinyl category
        vinyl_query = f'{query} 黑膠' if '黑膠' not in query and 'vinyl' not in query.lower() else query
        params = {
            'keyword': vinyl_query,
            'page': 1,
            'pageSize': 10,
        }
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for hit in data.get('hits', {}).get('hit', [])[:10]:
            fields = hit.get('fields', {})
            name = fields.get('name', '').strip()
            if not name or not is_likely_vinyl(name):
                continue

            price = extract_price(fields.get('final_price', ''))
            link = fields.get('url', '')
            stock = fields.get('stock', '1')
            in_stock = str(stock) != '0'

            img_path = fields.get('product_photo_url', '')
            img = ''
            if img_path:
                img = img_path if img_path.startswith('http') else IMG_BASE + img_path

            if not img:
                img = fetch_itunes_cover(name)

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
