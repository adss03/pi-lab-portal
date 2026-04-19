import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from app.models import classify_post

logger = logging.getLogger(__name__)

FIREBASE = 'https://hacker-news.firebaseio.com/v0'
SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'pi-lab-portal/1.0'

PAYMENT_PHRASES = [
    'i would pay',
    'would pay for',
    'willing to pay',
    'would pay $',
    'pay per month',
    'pay monthly',
    '/month',
    '/mo',
]
IDEA_PHRASES = [
    'someone should build',
    'wish there was',
    "why doesn't this exist",
    'looking for a tool',
    'need a product',
    'would love a tool',
]
ALL_PHRASES = PAYMENT_PHRASES + IDEA_PHRASES


def _matches(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in ALL_PHRASES)


def _fetch_item(item_id: int) -> dict | None:
    try:
        r = SESSION.get(f'{FIREBASE}/item/{item_id}.json', timeout=8)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _item_to_record(item: dict) -> dict:
    title = item.get('title') or ''
    body = item.get('text') or ''
    label, amounts = classify_post(f'{title} {body}')
    ts = item.get('time')
    posted_at = (
        datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        if ts else datetime.datetime.now(datetime.timezone.utc)
    )
    item_id = str(item['id'])
    return {
        'source': 'hackernews',
        'community': 'Hacker News',
        'post_id': f'hn_{item_id}',
        'url': f'https://news.ycombinator.com/item?id={item_id}',
        'title': title,
        'body': body,
        'author': item.get('by') or '',
        'posted_at': posted_at,
        'score': item.get('score') or 0,
        'num_comments': len(item.get('kids') or []),
        'monetary_amounts': amounts,
        'label': label,
    }


def _fetch_list(endpoint: str, limit: int = 300) -> list:
    try:
        r = SESSION.get(f'{FIREBASE}/{endpoint}.json', timeout=10)
        r.raise_for_status()
        return (r.json() or [])[:limit]
    except Exception:
        logger.warning('Failed to fetch %s', endpoint, exc_info=True)
        return []


def scrape() -> list[dict]:
    results = []
    seen: set[int] = set()

    ids = []
    for endpoint in ('askstories', 'showstories', 'newstories'):
        limit = 300 if endpoint == 'newstories' else 200
        ids.extend(_fetch_list(endpoint, limit))

    unique_ids = list(dict.fromkeys(ids))

    with ThreadPoolExecutor(max_workers=15) as pool:
        futures = {pool.submit(_fetch_item, i): i for i in unique_ids}
        for future in as_completed(futures):
            item = future.result()
            if not item or item.get('deleted') or item.get('dead'):
                continue
            item_id = item.get('id')
            if not item_id or item_id in seen:
                continue
            text = f"{item.get('title', '')} {item.get('text', '')}"
            if not _matches(text):
                continue
            seen.add(item_id)
            results.append(_item_to_record(item))

    return results
