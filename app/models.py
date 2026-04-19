import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

_PAYMENT_PATTERNS = [
    re.compile(r'\bI would pay\b', re.I),
    re.compile(r'\bwould pay for\b', re.I),
    re.compile(r'\bwilling to pay\b', re.I),
    re.compile(r'\bpay\s+\$\d+', re.I),
    re.compile(r"\bpay\s+\d+\s*(?:dollars?|bucks?|\/mo|\/month|\/year)\b", re.I),
    re.compile(r'\bwould pay\b', re.I),
]
_WISHLIST_PATTERNS = [
    re.compile(r'\bsomeone should build\b', re.I),
    re.compile(r'\bwish there was\b', re.I),
    re.compile(r"\bwould love (?:a|an|to have)\b", re.I),
    re.compile(r'\blooking for a tool\b', re.I),
    re.compile(r"\bneed a tool\b", re.I),
    re.compile(r"\bhasn't been built\b", re.I),
    re.compile(r"\bnobody has built\b", re.I),
]
_WHY_NOT_PATTERNS = [
    re.compile(r"\bwhy doesn't\b", re.I),
    re.compile(r"\bwhy is there no\b", re.I),
    re.compile(r"\bwhy hasn't anyone\b", re.I),
    re.compile(r"\bwhy isn't there\b", re.I),
    re.compile(r"\bwhy doesn't .+ exist\b", re.I),
]
_CURRENCY_RE = re.compile(r'\$\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?')


def has_signal(text: str) -> bool:
    return any(
        p.search(text)
        for p in _PAYMENT_PATTERNS + _WISHLIST_PATTERNS + _WHY_NOT_PATTERNS
    )


def classify_post(text: str) -> tuple[str, list[str]]:
    amounts = _CURRENCY_RE.findall(text)
    for pat in _PAYMENT_PATTERNS:
        if pat.search(text):
            return ('explicit_pay' if amounts else 'implied_pay'), amounts
    for pat in _WHY_NOT_PATTERNS:
        if pat.search(text):
            return 'why_not', amounts
    for pat in _WISHLIST_PATTERNS:
        if pat.search(text):
            return 'wishlist', amounts
    return 'wishlist', amounts


SOURCE_CHOICES = [
    ("reddit", "Reddit"),
    ("hackernews", "Hacker News"),
    ("indiehackers", "Indie Hackers"),
]
LABEL_CHOICES = [
    ("explicit_pay", "Explicit Pay"),
    ("implied_pay", "Implied Pay"),
    ("wishlist", "Wishlist"),
    ("why_not", "Why Not"),
]

_SOURCE_DISPLAY = dict(SOURCE_CHOICES)
_LABEL_DISPLAY = dict(LABEL_CHOICES)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str


class ScrapeJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(default="all")
    status: str = Field(default="pending", index=True)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = Field(default=None)
    posts_found: int = Field(default=0)
    posts_created: int = Field(default=0)
    error: str = Field(default="")
    notes: str = Field(default="")

    def is_active(self) -> bool:
        return self.status in ("pending", "running")


class IdeaPost(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    community: str = Field(default="", index=True)
    post_id: str = Field(unique=True, index=True)
    url: str
    title: str = Field(default="")
    body: str = Field(default="")
    author: str = Field(default="")
    posted_at: Optional[datetime] = Field(default=None, index=True)
    score: int = Field(default=0, index=True)
    num_comments: int = Field(default=0)
    monetary_amounts: Any = Field(default_factory=list, sa_column=Column(JSONB))
    label: str = Field(default="wishlist", index=True)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def source_display(self) -> str:
        return _SOURCE_DISPLAY.get(self.source, self.source)

    @property
    def label_display(self) -> str:
        return _LABEL_DISPLAY.get(self.label, self.label)
