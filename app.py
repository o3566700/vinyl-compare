import json
import os
import re
import concurrent.futures
from flask import Flask, render_template, jsonify, request

from scrapers import shanhaisan, candlelight, eslite, shopee

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECO_FILE = os.path.join(BASE_DIR, 'data', 'recommendations.json')

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
    {
        'key': 'shopee_vinyl_voyage',
        'name': 'Vinyl_voyage（蝦皮）',
        'color': 'orange',
        'fn': lambda q: shopee.search(q, 'Vinyl_voyage'),
    },
    {
        'key': 'shopee_wshit1206',
        'name': 'wshit1206（蝦皮）',
        'color': 'violet',
        'fn': lambda q: shopee.search(q, 'wshit1206'),
    },
]


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


def load_recommendations():
    with open(RECO_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.route('/')
def index():
    recommendations = load_recommendations()
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
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
    return jsonify(load_recommendations())


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, port=port, host='0.0.0.0')
