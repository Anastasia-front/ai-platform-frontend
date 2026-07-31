import html
import re
from datetime import date, datetime
from datetime import timezone as dt_timezone

from django import template
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def human_datetime(value):
    if not value:
        return ''

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    else:
        value = str(value).strip()
        parsed = parse_datetime(value)
        if parsed is None:
            parsed_date = parse_date(value)
            if parsed_date is None:
                return value
            parsed = datetime.combine(parsed_date, datetime.min.time())

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    parsed = parsed.astimezone(dt_timezone.utc)

    # Timestamps are stored/served in UTC. Render a <time> element carrying
    # the ISO instant so local_time.js can reformat it to the browser's own
    # timezone client-side -- the browser is the only thing that reliably
    # knows the viewer's real timezone. The inline text is a UTC fallback
    # for no-JS contexts.
    return mark_safe(
        '<time datetime="{iso}" data-local-datetime>{fallback}</time>'.format(
            iso=parsed.isoformat(),
            fallback=parsed.strftime('%d/%m/%Y - %H:%M'),
        )
    )


@register.filter
def truncate_chars(value, max_length):
    if not value:
        return ''

    value = str(value)
    try:
        max_length = int(max_length)
    except (TypeError, ValueError):
        return value

    if max_length <= 3 or len(value) <= max_length:
        return value

    return f'{value[:max_length - 3]}...'


@register.filter
def render_markdown(value):
    if not value:
        return ''

    escaped = html.escape(str(value))
    lines = escaped.splitlines()
    blocks = []
    list_items = []
    in_code_block = False
    code_lines = []
    index = 0

    def flush_list():
        if list_items:
            blocks.append('<ul>' + ''.join(f'<li>{_inline(item)}</li>' for item in list_items) + '</ul>')
            list_items.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith('```'):
            if in_code_block:
                blocks.append('<pre><code>' + '\n'.join(code_lines) + '</code></pre>')
                code_lines = []
                in_code_block = False
            else:
                flush_list()
                in_code_block = True
            index += 1
            continue

        if in_code_block:
            code_lines.append(line)
            index += 1
            continue

        if not stripped:
            flush_list()
            index += 1
            continue

        heading = _atx_heading(stripped)
        if heading:
            flush_list()
            level, text = heading
            blocks.append(f'<h{level}>{_inline(text)}</h{level}>')
            index += 1
            continue

        setext = _setext_heading(lines, index)
        if setext:
            flush_list()
            level, text, next_index = setext
            blocks.append(f'<h{level}>{_inline(text)}</h{level}>')
            index = next_index
            continue

        if _is_horizontal_rule(stripped):
            flush_list()
            blocks.append('<hr>')
            index += 1
            continue

        list_match = re.match(r'^[-*]\s+(.+)$', stripped)
        numbered_match = re.match(r'^\d+\.\s+(.+)$', stripped)

        if list_match:
            list_items.append(list_match.group(1))
        elif numbered_match:
            list_items.append(numbered_match.group(1))
        else:
            flush_list()
            blocks.append(f'<p>{_inline(stripped)}</p>')

        index += 1

    if in_code_block:
        blocks.append('<pre><code>' + '\n'.join(code_lines) + '</code></pre>')

    flush_list()
    return mark_safe(''.join(blocks))


def _atx_heading(text):
    match = re.match(r'^(#{1,6})\s+(.+?)\s*#*$', text)
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def _setext_heading(lines, index):
    text = lines[index].strip()
    underline_index = index + 1

    if underline_index < len(lines) and not lines[underline_index].strip():
        underline_index += 1

    if underline_index >= len(lines):
        return None

    underline = lines[underline_index].strip()
    if re.fullmatch(r'=+', underline):
        return 1, text, underline_index + 1
    if re.fullmatch(r'-+', underline):
        return 2, text, underline_index + 1

    return None


def _is_horizontal_rule(text):
    return bool(re.fullmatch(r'([-*_])\s*(\1\s*){2,}', text))


def _inline(text):
    code_segments = []

    def stash_code(match):
        code_segments.append(f'<code>{match.group(1)}</code>')
        return f'@@CODE{len(code_segments) - 1}@@'

    text = re.sub(r'`([^`]+)`', stash_code, text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__([^_]+)__', r'<u>\1</u>', text)
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    text = re.sub(r'(?<!\w)_([^_\n]+)_(?!\w)', r'<em>\1</em>', text)

    for index, segment in enumerate(code_segments):
        text = text.replace(f'@@CODE{index}@@', segment)

    return text
