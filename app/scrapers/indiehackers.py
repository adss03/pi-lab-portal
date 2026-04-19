import datetime
import logging
import re

import requests
from bs4 import BeautifulSoup

from app.models import classify_post

logger = logging.getLogger(__name__)

BASE_URL = 'https://www.indiehackers.com'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 pi-lab-portal/1.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

QUERIES = [
    'I would pay',
    'would pay for',
    'someone should build',
    'wish there was',
    'willing to pay',
]


def scrape() -> list[dict]:
    results = []
    seen: set[str] = set()

    for query in QUERIES:
        try:
            resp = requests.get(
                f'{BASE_URL}/search',
                params={'q': query, 'type': 'post'},
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')

            for item in soup.select('a[href^="/post/"], a[href*="/posts/"]')[:20]:
                href = item.get('href', '')
                if not href:
                    continue
                url = f'{BASE_URL}{href}' if href.startswith('/') else href
                post_id = f'ih_{re.sub(r"[^a-z0-9]", "_", href.lower())[:100]}'
                if post_id in seen:
                    continue
                seen.add(post_id)

                title = item.get_text(strip=True)
                parent = item.find_parent(['li', 'article', 'div'])
                body = ''
                if parent:
                    excerpt = parent.find('p')
                    if excerpt:
                        body = excerpt.get_text(strip=True)

                label, amounts = classify_post(f'{title} {body}')
                results.append({
                    'source': 'indiehackers',
                    'community': 'Indie Hackers',
                    'post_id': post_id,
                    'url': url,
                    'title': title,
                    'body': body,
                    'author': '',
                    'posted_at': datetime.datetime.now(datetime.timezone.utc),
                    'score': 0,
                    'num_comments': 0,
                    'monetary_amounts': amounts,
                    'label': label,
                })
        except Exception:
            logger.warning('Indie Hackers search query=%r failed', query, exc_info=True)

    return results
