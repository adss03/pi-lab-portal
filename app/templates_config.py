import re
from html import escape

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

templates = Jinja2Templates(directory="app/templates")


def _linebreaks(value: str) -> Markup:
    escaped = escape(str(value))
    normalized = re.sub(r'\r\n|\r', '\n', escaped)
    paragraphs = re.split(r'\n{2,}', normalized)
    parts = []
    for para in paragraphs:
        para = para.strip()
        if para:
            parts.append('<p>' + para.replace('\n', '<br>\n') + '</p>')
    return Markup('\n'.join(parts))


def _pluralize(count: int, suffix: str = "s") -> str:
    return suffix if count != 1 else ""


templates.env.filters["linebreaks"] = _linebreaks
templates.env.filters["pluralize"] = _pluralize
