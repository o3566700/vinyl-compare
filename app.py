import os
import time
import re
import concurrent.futures
from flask import Flask, render_template, jsonify, request

from scrapers import shanhaisan, candlelight, eslite
from scrapers.covers import get_cover

app = Flask(__name__)

SOURCES = [
    {
        'key': 'shanhaisan',
        'name': '山海山唱片行',
        'color': 'amber',
        'fn': shanhaisan.search,
    },
    {
        'key': 'candlelight',
        'name': '燭光唱片',
        'color': 'red',
        'fn': candlelight.search,
    },
    {
        'key': 'eslite',
        'name': '誠品線上',
        'color': 'emerald',
        'fn': eslite.search,
    },
]

# In-memory cache for live recommendations (1-hour TTL)
_reco_cache = {'data': None, 'ts': 0}
_RECO_TTL = 3600


def _enrich_cover(item):
    """If an item lacks a cover image, fetch one from iTunes."""
    if not item.get('image'):
        item['image'] = get_cover(item.get('name', ''))
    return item


def _fetch_live_recommendations():
    now = time.time()
    if _reco_cache['data'] and now - _reco_cache['ts'] < _RECO_TTL:
        return _reco_cache['data']

    def _shanhaisan():
        items = shanhaisan.get_home_items(limit=12)
        return [_enrich_cover(i) for i in items]

    def _candlelight():
        items = candlelight.get_home_items(limit=12)
        return [_enrich_cover(i) for i in items]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f_shs = ex.submit(_shanhaisan)
        f_cdl = ex.submit(_candlelight)
        shs_items = f_shs.result(timeout=20) if not f_shs.exception() else []
        cdl_items = f_cdl.result(timeout=20) if not f_cdl.exception() else []

    data = {
        'shanhaisan': shs_items,
        'candlelight': cdl_items,
    }
    _reco_cache['data'] = data
    _reco_cache['ts'] = now
    return data


def filter_relevant_items(items, query):
    """Keep only items whose name contains at least one word from the search query."""
    if not items or not query:
        return items
    # Split on whitespace; keep words of 2+ chars
    words = [w.lower() for w in re.split(r'\s+', query.strip()) if len(w) >= 2]
    if not words:
        return items
    filtered = []
    for item in items:
        name_lower = (item.get('name') or '').lower()
        if any(word in name_lower for word in words):
            filtered.append(item)
    return filtered


@app.route('/')
def index():
    recommendations = _fetch_live_recommendations()
    return render_template('index.html', recommendations=recommendations)


@app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': '請輸入搜尋關鍵字'}), 400

    results = {}

    def run_scraper(source):
        try:
            items = source['fn'](query)
            # Fill missing cover images
            for item in items:
                if not item.get('image'):
                    item['image'] = get_cover(query)
            return source['key'], {
                'name': source['name'],
                'color': source['color'],
                'items': items,
                'error': None,
            }
        except Exception as e:
            return source['key'], {
                'name': source['name'],
                'color': source['color'],
                'items': [],
                'error': str(e),
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SOURCES)) as executor:
        futures = {executor.submit(run_scraper, s): s for s in SOURCES}
        for future in concurrent.futures.as_completed(futures):
            key, data = future.result()
            results[key] = data

    # Filter results by relevance: item name must contain at least one query word
    for key in results:
        results[key]['items'] = filter_relevant_items(results[key]['items'], query)

    # Find global minimum price across all results
    all_prices = [
        item['price']
        for src in results.values()
        for item in src['items']
        if item.get('price') and item.get('in_stock')
    ]
    min_price = min(all_prices) if all_prices else None

    return jsonify({
        'query': query,
        'results': results,
        'min_price': min_price,
        'source_order': [s['key'] for s in SOURCES],
    })


@app.route('/api/recommendations')
def api_recommendations():
    return jsonify(_fetch_live_recommendations())


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, port=port, host='0.0.0.0')
