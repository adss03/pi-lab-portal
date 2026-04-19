import datetime
import logging
import time

import requests

from app.models import classify_post

logger = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'pi-lab-portal/1.0 (personal homelab; no commercial use)'

SUBREDDITS = [
    'entrepreneur',
    'startups',
    'SaaS',
    'smallbusiness',
    'SideProject',
    'webdev',
    'business',
    'indiehackers',
]

QUERIES = [
    '"I would pay"',
    '"would pay for"',
    '"willing to pay"',
    '"someone should build"',
    '"wish there was"',
    '"looking for a tool"',
    '"why doesn\'t this exist"',
    '"need a tool that"',
]


def _search(subreddit: str, query: str) -> list:
    url = f'https://www.reddit.com/r/{subreddit}/search.json'
    resp = SESSION.get(url, params={
        'q': query,
        'sort': 'new',
        't': 'year',
        'limit': 25,
        'type': 'link',
        'restrict_sr': 1,
    }, timeout=10)
    resp.raise_for_status()
    return resp.json().get('data', {}).get('children', [])


def scrape() -> list[dict]:
    results = []
    seen: set[str] = set()

    for sub in SUBREDDITS:
        for query in QUERIES:
            try:
                children = _search(sub, query)
                for child in children:
                    post = child.get('data', {})
                    post_id = post.get('id')
                    if not post_id or post_id in seen:
                        continue
                    seen.add(post_id)
                    title = post.get('title', '')
                    body = post.get('selftext', '')
                    label, amounts = classify_post(f'{title} {body}')
                    ts = post.get('created_utc')
                    posted_at = (
                        datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
                        if ts else datetime.datetime.now(datetime.timezone.utc)
                    )
                    results.append({
                        'source': 'reddit',
                        'community': sub,
                        'post_id': f'reddit_{post_id}',
                        'url': f"https://reddit.com{post.get('permalink', '')}",
                        'title': title,
                        'body': body,
                        'author': post.get('author', ''),
                        'posted_at': posted_at,
                        'score': post.get('score', 0),
                        'num_comments': post.get('num_comments', 0),
                        'monetary_amounts': amounts,
                        'label': label,
                    })
                time.sleep(1)
            except Exception:
                logger.warning('Reddit r/%s query=%r failed', sub, query, exc_info=True)

    return results
