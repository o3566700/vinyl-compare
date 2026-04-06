"""Album cover lookup via iTunes Search API (free, no auth needed)."""
import requests

_ITUNES_URL = 'https://itunes.apple.com/search'
_HEADERS = {'User-Agent': 'VinylCompare/1.0'}
_CACHE = {}


def get_cover(query: str, size: int = 600) -> str:
    """Return an album artwork URL for the given query, or empty string."""
    key = query.lower().strip()
    if key in _CACHE:
        return _CACHE[key]

    url = ''
    try:
        params = {
            'term': query,
            'media': 'music',
            'entity': 'album',
            'limit': 1,
        }
        resp = requests.get(_ITUNES_URL, params=params, headers=_HEADERS, timeout=8)
        if resp.status_code == 200:
            results = resp.json().get('results', [])
            if results:
                artwork = results[0].get('artworkUrl100', '')
                if artwork:
                    url = artwork.replace('100x100bb', f'{size}x{size}bb')
    except Exception as e:
        print(f'[iTunes封面] 錯誤: {e}')

    _CACHE[key] = url
    return url
