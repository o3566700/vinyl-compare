import os
import json
import time
import re
import traceback
import concurrent.futures
from flask import Flask, render_template, jsonify, request

from scrapers import shanhaisan, candlelight, eslite
from scrapers.covers import get_cover
from scrapers import eslite_ranking as eslite_rank
from scrapers import ranking as extra_rank

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
    """Keep items whose name contains at least one CJK character or word from the query."""
    if not items or not query:
        return items
    q = query.strip().lower()
    if not q:
        return items

    # CJK characters (any single Chinese/Japanese/Korean character in the query)
    cjk_chars = [c for c in q if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff']
    # ASCII words of 2+ chars
    ascii_words = [w for w in re.split(r'[\s\W]+', q) if len(w) >= 2 and w.isascii()]

    if not cjk_chars and not ascii_words:
        return items

    filtered = []
    for item in items:
        name = (item.get('name') or '').lower()
        # Match if any CJK char appears in name, OR any ascii word appears in name
        if (cjk_chars and any(c in name for c in cjk_chars)) or \
           (ascii_words and any(w in name for w in ascii_words)):
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


@app.route('/api/eslite-ranking')
def api_eslite_ranking():
    try:
        items = eslite_rank.fetch_hot_ranking(limit=10)
        return jsonify({'items': items, 'error': None})
    except Exception as e:
        return jsonify({'items': [], 'error': str(e)})


# ---------------------------------------------------------------------------
# Additional ranking endpoints (燭光 / 山海山) — 1-hour in-memory cache
# with JSON fallback when live scraping fails or returns empty
# ---------------------------------------------------------------------------
_extra_cache: dict = {}
_EXTRA_TTL = 3600
_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def _load_fallback(filename):
    """Load cached JSON data from the data/ directory."""
    path = os.path.join(_DATA_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _get_extra(key, fn, label='', fallback_file=None):
    now = time.time()
    if key in _extra_cache:
        data, ts = _extra_cache[key]
        if now - ts < _EXTRA_TTL:
            return data
    try:
        data = fn()
    except Exception as e:
        print(f'[_get_extra:{label}] 未捕捉例外: {e}')
        print(traceback.format_exc())
        data = []
    if not data and fallback_file:
        data = _load_fallback(fallback_file)
    _extra_cache[key] = (data, now)
    return data


@app.route('/api/candlelight-new-ranking')
def api_candlelight_new_ranking():
    data = _get_extra('candlelight_new', extra_rank.candlelight_new_ranking, '燭光全新', 'candlelight_new.json')
    return jsonify(data)


@app.route('/api/candlelight-used-ranking')
def api_candlelight_used_ranking():
    data = _get_extra('candlelight_used', extra_rank.candlelight_used_ranking, '燭光二手', 'candlelight_used.json')
    return jsonify(data)


@app.route('/api/candlelight-ep-ranking')
def api_candlelight_ep_ranking():
    data = _get_extra('candlelight_ep', extra_rank.candlelight_ep_ranking, '燭光EP', 'candlelight_ep.json')
    return jsonify(data)


@app.route('/api/shanhaisan-ranking')
def api_shanhaisan_ranking():
    print('[api/shanhaisan-ranking] 開始請求')
    try:
        data = _get_extra('shanhaisan', extra_rank.shanhaisan_ranking, '山海山熱門', 'shanhaisan_hot.json')
        print(f'[api/shanhaisan-ranking] 回傳 {len(data)} 筆')
        return jsonify(data)
    except Exception as e:
        print(f'[api/shanhaisan-ranking] 例外: {e}')
        print(traceback.format_exc())
        return jsonify([])


@app.route('/api/shanhaisan-new')
def api_shanhaisan_new():
    print('[api/shanhaisan-new] 開始請求')
    try:
        data = _get_extra('shanhaisan_new', extra_rank.shanhaisan_new_arrivals, '山海山最新', 'shanhaisan_new.json')
        print(f'[api/shanhaisan-new] 回傳 {len(data)} 筆')
        return jsonify(data)
    except Exception as e:
        print(f'[api/shanhaisan-new] 例外: {e}')
        print(traceback.format_exc())
        return jsonify([])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, port=port, host='0.0.0.0')
