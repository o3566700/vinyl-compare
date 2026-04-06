import requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9',
    'Referer': 'https://www.eslite.com/rank/music-vinyl',
}

# Vinyl LP category ID in eslite's taxonomy
VINYL_LP_CATEGORY_ID = 15442

BESTSELLERS_URL = 'https://athena.eslite.com/api/v1/best_sellers/online/week'
SEARCH_URL = 'https://athena.eslite.com/api/v2/search'


def _fetch_price(eslite_sn):
    """Fetch current price by searching with eslite_sn."""
    try:
        r = requests.get(
            SEARCH_URL,
            params={'keyword': eslite_sn, 'size': 1, 'page': 1},
            headers=HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        hit_list = r.json().get('hits', {}).get('hit', [])
        if hit_list:
            fields = hit_list[0]['fields']
            price_str = fields.get('final_price', '')
            return int(price_str) if price_str.isdigit() else None
    except Exception:
        pass
    return None


def fetch_hot_ranking(limit=10):
    """
    Fetch the weekly hot-selling vinyl LP ranking from eslite.

    Returns a list of dicts:
      {rank, name, author, price, url, image, in_stock}
    """
    r = requests.get(
        BESTSELLERS_URL,
        params={'l1': VINYL_LP_CATEGORY_ID, 'page': 1, 'per_page': limit},
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    products = r.json().get('products', [])

    results = []
    for i, p in enumerate(products[:limit], 1):
        product_id = p.get('id', '')
        eslite_sn = p.get('eslite_sn', '')
        price = _fetch_price(eslite_sn) if eslite_sn else None
        img = p.get('product_photo_url', '')

        results.append({
            'rank': i,
            'name': p.get('name', ''),
            'author': p.get('author', ''),
            'price': price,
            'url': f'https://www.eslite.com/product/{product_id}' if product_id else '',
            'image': img,
            'in_stock': int(p.get('stock', 0)) > 0,
        })

    return results
