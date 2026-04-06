import requests
import re
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    'Referer': 'https://shopee.tw/',
    'X-Requested-With': 'XMLHttpRequest',
}

SHOPEE_API = 'https://shopee.tw/api/v4'


def get_shop_id(username: str) -> int | None:
    """Fetch shopid from Shopee public API."""
    try:
        url = f'{SHOPEE_API}/shop/get_shop_detail?username={username}'
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            shop_data = data.get('data') or data.get('shop_data')
            if shop_data:
                return shop_data.get('shopid') or shop_data.get('shop_id')
    except Exception as e:
        print(f'[蝦皮] 取得 shopid 失敗 ({username}): {e}')
    return None


def search_in_shop(query: str, shopid: int, username: str):
    """Search products within a specific Shopee shop."""
    results = []
    try:
        params = {
            'by': 'relevancy',
            'keyword': query,
            'limit': 10,
            'newest': 0,
            'order': 'desc',
            'page_type': 'shop',
            'scenario': 'PAGE_OTHERS',
            'version': 2,
            'shopid': shopid,
        }
        url = f'{SHOPEE_API}/search/search_items'
        resp = requests.get(url, headers=HEADERS, params=params, timeout=12)
        if resp.status_code != 200:
            return results

        data = resp.json()
        items = data.get('items', []) or []

        for item_wrapper in items:
            item = item_wrapper.get('item_basic') or item_wrapper
            name = item.get('name', '')
            price_raw = item.get('price') or item.get('price_min', 0)
            # Shopee price is in cents (x100000)
            price = round(price_raw / 100000) if price_raw else None
            item_id = item.get('itemid') or item.get('item_id', '')
            img_hash = item.get('image', '')
            img = f'https://cf.shopee.tw/file/{img_hash}_tn' if img_hash else ''
            link = f'https://shopee.tw/{username}/{item_id}' if item_id else f'https://shopee.tw/{username}'
            stock = item.get('stock', 1)
            in_stock = stock > 0

            if name:
                results.append({
                    'name': name,
                    'price': price,
                    'link': link,
                    'image': img,
                    'in_stock': in_stock,
                })
    except Exception as e:
        print(f'[蝦皮] 搜尋錯誤 ({username}): {e}')

    return results


def search_global_filter_seller(query: str, username: str):
    """Fallback: search globally and filter by username."""
    results = []
    try:
        params = {
            'by': 'relevancy',
            'keyword': f'{query} {username}',
            'limit': 20,
            'newest': 0,
            'order': 'desc',
            'page_type': 'search',
            'scenario': 'PAGE_GLOBAL_SEARCH',
            'version': 2,
        }
        url = f'{SHOPEE_API}/search/search_items'
        resp = requests.get(url, headers=HEADERS, params=params, timeout=12)
        if resp.status_code != 200:
            return results

        data = resp.json()
        items = data.get('items', []) or []

        for item_wrapper in items:
            item = item_wrapper.get('item_basic') or item_wrapper
            shop_name = item.get('shop_name', '').lower()
            if username.lower() not in shop_name:
                continue

            name = item.get('name', '')
            price_raw = item.get('price') or item.get('price_min', 0)
            price = round(price_raw / 100000) if price_raw else None
            item_id = item.get('itemid') or item.get('item_id', '')
            shopid = item.get('shopid', '')
            img_hash = item.get('image', '')
            img = f'https://cf.shopee.tw/file/{img_hash}_tn' if img_hash else ''
            link = f'https://shopee.tw/{username}/{item_id}' if item_id else f'https://shopee.tw/{username}'
            stock = item.get('stock', 1)
            in_stock = stock > 0

            if name:
                results.append({
                    'name': name,
                    'price': price,
                    'link': link,
                    'image': img,
                    'in_stock': in_stock,
                })
    except Exception as e:
        print(f'[蝦皮全域搜尋] 錯誤 ({username}): {e}')

    return results


def search(query: str, username: str):
    """Main entry: try shop-specific search, fallback to global filter."""
    shopid = get_shop_id(username)
    if shopid:
        results = search_in_shop(query, shopid, username)
        if results:
            return results

    # Fallback
    return search_global_filter_seller(query, username)
