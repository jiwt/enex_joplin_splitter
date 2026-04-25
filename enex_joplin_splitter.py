#!/usr/bin/env python3
import argparse
import csv
import glob
import html
import mimetypes
import os
import re
import sys
from datetime import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

ELLIPSIS = '…'
MAX_TITLE_LEN = 80
UNTITLED_TITLES = {'無題のノート', 'Untitled Note'}
SAFE_FILENAME_CHARS = re.compile(r'[^A-Za-z0-9._-]+')
HTML_LIKE_TAGS = {
    'table', 'tr', 'td', 'th', 'thead', 'tbody', 'tfoot', 'colgroup', 'col',
    'div', 'span', 'font', 'style', 'blockquote', 'iframe', 'object', 'embed',
    'video', 'audio', 'source', 'picture', 'svg', 'math', 'pre', 'code', 'figure',
    'figcaption', 'details', 'summary'
}
WEB_CLIP_HINTS = {'clip', 'clipped', 'webclip', 'web clip', 'web.clip', 'article', 'page', 'url'}
BLOCK_BREAK_TAGS = {'div', 'p', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br'}
NOTE_LINK_RE = re.compile(r'<a\b[^>]*\bhref\s*=\s*(["'])evernote:[^"']*\1', re.IGNORECASE)
WEB_CLIP_BODY_PATTERNS = [
    re.compile(r'<div\b[^>]*\bstyle\s*=\s*(["'])[^"']*-evernote-webclip:true[^"']*\1', re.IGNORECASE),
    re.compile(r'<div\b[^>]*\bstyle\s*=\s*(["'])[^"']*--en-clipped-content:[^"']*\1', re.IGNORECASE),
]


def configure_stdio_utf8():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def strip_ns(tag: str) -> str:
    return tag.split('}', 1)[-1] if '}' in tag else tag


def collapse_ws(s: str) -> str:
    return re.sub(r'\s+', ' ', s or '').strip()


def truncate_title(s: str, limit: int = MAX_TITLE_LEN) -> str:
    s = collapse_ws(s)
    if not s:
        return 'Untitled'
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + ELLIPSIS


def sanitize_resource_filename(name: str, fallback_stem: str, ext_hint: str = '') -> str:
    raw = (name or '').strip().replace('\\', '_').replace('/', '_')
    raw = SAFE_FILENAME_CHARS.sub('_', raw).strip('._')
    if not raw:
        raw = fallback_stem
    stem, ext = os.path.splitext(raw)
    if not ext and ext_hint:
        ext = ext_hint
    return (stem or fallback_stem) + ext


def unique_name(name: str, used: set) -> str:
    if name not in used:
        used.add(name)
        return name
    stem, ext = os.path.splitext(name)
    n = 2
    while True:
        candidate = f'{stem}_{n}{ext}'
        if candidate not in used:
            used.add(candidate)
            return candidate
        n += 1


def get_child(elem, name):
    for child in list(elem):
        if strip_ns(child.tag) == name:
            return child
    return None


def get_children(elem, name):
    return [c for c in list(elem) if strip_ns(c.tag) == name]


def enml_first_plain_line(enml: str) -> str:
    try:
        root = ET.fromstring(f'<root>{enml}</root>')
    except ET.ParseError:
        text = re.sub(r'<br\s*/?>', '\n', enml, flags=re.I)
        text = re.sub(r'</(div|p|li|tr|h[1-6])\s*>', '\n', text, flags=re.I)
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)
        for line in text.splitlines():
            line = collapse_ws(line)
            if line:
                return truncate_title(line)
        return 'Untitled'

    chunks = []
    found = None

    def walk(node):
        nonlocal found
        if found is not None:
            return
        if node.text:
            txt = collapse_ws(html.unescape(node.text))
            if txt:
                chunks.append(txt)
        for child in list(node):
            tag = strip_ns(child.tag).lower()
            if tag != 'en-media':
                walk(child)
            if found is not None:
                return
            if child.tail:
                tail = collapse_ws(html.unescape(child.tail))
                if tail:
                    chunks.append(tail)
            if tag in BLOCK_BREAK_TAGS:
                line = collapse_ws(' '.join(chunks))
                if line:
                    found = truncate_title(line)
                    return
                chunks.clear()

    walk(root)
    if found:
        return found
    line = collapse_ws(' '.join(chunks))
    return truncate_title(line) if line else 'Untitled'


def retitle_if_needed(note_elem):
    title_elem = get_child(note_elem, 'title')
    current = (title_elem.text or '').strip() if title_elem is not None and title_elem.text else ''
    if current in UNTITLED_TITLES:
        content_elem = get_child(note_elem, 'content')
        enml = content_elem.text or '' if content_elem is not None else ''
        new_title = enml_first_plain_line(enml)
        if title_elem is None:
            title_elem = ET.Element('title')
            note_elem.insert(0, title_elem)
        title_elem.text = new_title
        return True, current, new_title
    return False, current, current


def normalize_resources(note_elem):
    changed = False
    used = set()
    renamed = []
    for i, res in enumerate(get_children(note_elem, 'resource'), start=1):
        mime_elem = get_child(res, 'mime')
        mime_type = (mime_elem.text or '').strip() if mime_elem is not None and mime_elem.text else ''
        ext = mimetypes.guess_extension(mime_type or '') or ''
        attrs = get_child(res, 'resource-attributes')
        file_name_elem = get_child(attrs, 'file-name') if attrs is not None else None
        current_name = (file_name_elem.text or '').strip() if file_name_elem is not None and file_name_elem.text else ''
        safe = sanitize_resource_filename(current_name, f'resource_{i}', ext)
        safe = unique_name(safe, used)
        if file_name_elem is None:
            if attrs is None:
                attrs = ET.Element('resource-attributes')
                res.append(attrs)
            file_name_elem = ET.Element('file-name')
            attrs.append(file_name_elem)
        if file_name_elem.text != safe:
            renamed.append((current_name, safe))
            file_name_elem.text = safe
            changed = True
    return changed, renamed


def is_web_clip_or_html_heavy(note_elem):
    content = get_child(note_elem, 'content')
    enml = (content.text or '') if content is not None else ''
    lowered = enml.lower()

    attrs = get_child(note_elem, 'note-attributes')
    source_url = collapse_ws(getattr(get_child(attrs, 'source-url'), 'text', '') if attrs is not None else '')
    source = collapse_ws(getattr(get_child(attrs, 'source'), 'text', '') if attrs is not None else '')
    if source_url:
        return True, 'source-url'
    if source and any(k in source.lower() for k in WEB_CLIP_HINTS):
        return True, f'source={source}'

    tag_names = [m.group(1).lower() for m in re.finditer(r'<\s*([a-zA-Z0-9:-]+)\b', lowered)]
    html_like_count = sum(1 for t in tag_names if t in HTML_LIKE_TAGS)
    style_attrs = len(re.findall(r'\sstyle\s*=\s*"[^"]*"', lowered)) + len(re.findall(r"\sstyle\s*=\s*'[^']*'", lowered))
    class_attrs = len(re.findall(r'\sclass\s*=\s*"[^"]*"', lowered)) + len(re.findall(r"\sclass\s*=\s*'[^']*'", lowered))
    span_font_count = sum(1 for t in tag_names if t in {'span', 'font'})
    table_count = sum(1 for t in tag_names if t in {'table', 'tr', 'td', 'th'})
    media_count = sum(1 for t in tag_names if t in {'iframe', 'object', 'embed', 'video', 'audio', 'source'})

    score = 0
    reasons = []
    if html_like_count >= 3:
        score += 2
        reasons.append(f'html_tags={html_like_count}')
    if style_attrs >= 3:
        score += 2
        reasons.append(f'style_attrs={style_attrs}')
    if class_attrs >= 3:
        score += 1
        reasons.append(f'class_attrs={class_attrs}')
    if span_font_count >= 8:
        score += 2
        reasons.append(f'span_font={span_font_count}')
    if table_count >= 4:
        score += 2
        reasons.append(f'table_tags={table_count}')
    if media_count >= 1:
        score += 3
        reasons.append(f'media_tags={media_count}')

    if score >= 3:
        return True, ';'.join(reasons) or f'html_score={score}'
    return False, 'markdown-friendly'


def write_note(note_elem, fh):
    fh.write(ET.tostring(note_elem, encoding='unicode'))
    fh.write('\n')


def expand_inputs(patterns, recursive=False):
    seen = set()
    results = []
    for pattern in patterns:
        expanded = os.path.expanduser(pattern)
        matches = glob.glob(expanded, recursive=recursive)
        if not matches and Path(expanded).is_file():
            matches = [expanded]
        for p in matches:
            path = Path(p)
            if path.is_file() and path.suffix.lower() == '.enex':
                key = str(path.resolve()) if path.exists() else str(path)
                if key not in seen:
                    seen.add(key)
                    results.append(path)
    return sorted(results)


def process_file_streaming(input_path: Path, output_dir: Path, csv_writer=None):
    base = input_path.stem
    md_path = output_dir / f'{base}_md.enex'
    html_path = output_dir / f'{base}_html.enex'

    summary = {
        'input_file': str(input_path),
        'md_output': str(md_path),
        'html_output': str(html_path),
        'retitled': 0,
        'md_notes': 0,
        'html_notes': 0,
        'resource_filenames_fixed': 0,
        'total_notes': 0,
    }

    with md_path.open('w', encoding='utf-8', newline='\n') as md_fh, html_path.open('w', encoding='utf-8', newline='\n') as html_fh:
        md_fh.write('<?xml version="1.0" encoding="utf-8"?>\n')
        html_fh.write('<?xml version="1.0" encoding="utf-8"?>\n')

        context = ET.iterparse(str(input_path), events=('start', 'end'))
        _, root = next(context)
        export_open_written = False
        stack = [root]
        note_index = 0

        for event, elem in context:
            if event == 'start':
                stack.append(elem)
                continue

            if elem is root:
                continue

            tag = strip_ns(elem.tag)

            if not export_open_written and tag == 'note':
                attrs = ' '.join(f'{k}="{html.escape(v, quote=True)}"' for k, v in root.attrib.items())
                open_tag = f'<{strip_ns(root.tag)}' + (f' {attrs}' if attrs else '') + '>'
                md_fh.write(open_tag + '\n')
                html_fh.write(open_tag + '\n')
                export_open_written = True

            if tag == 'note':
                note_index += 1
                title_elem = get_child(elem, 'title')
                original_title = (title_elem.text or '').strip() if title_elem is not None and title_elem.text else ''
                was_retitled, _, final_title = retitle_if_needed(elem)
                if was_retitled:
                    summary['retitled'] += 1

                resources_changed, renamed_resources = normalize_resources(elem)
                if resources_changed:
                    summary['resource_filenames_fixed'] += 1

                content_elem = get_child(elem, 'content')
                enml = content_elem.text or '' if content_elem is not None else ''
                enml_lower = enml.lower()
                has_encrypted = '<en-crypt ' in enml_lower
                has_note_link = bool(NOTE_LINK_RE.search(enml))

                is_html, reason = is_web_clip_or_html_heavy(elem)
                bucket = 'html' if is_html else 'md'
                if is_html:
                    write_note(elem, html_fh)
                    summary['html_notes'] += 1
                else:
                    write_note(elem, md_fh)
                    summary['md_notes'] += 1
                summary['total_notes'] += 1

                if csv_writer is not None:
                    csv_writer.writerow([
                        str(input_path),
                        note_index,
                        original_title,
                        final_title,
                        'yes' if was_retitled else 'no',
                        'yes' if has_encrypted else 'no',
                        'yes' if has_note_link else 'no',
                        bucket,
                        reason,
                        'yes' if resources_changed else 'no',
                        len(renamed_resources),
                    ])

                elem.clear()
                if len(stack) >= 2:
                    stack[-2].remove(elem)

            stack.pop()

        if not export_open_written:
            attrs = ' '.join(f'{k}="{html.escape(v, quote=True)}"' for k, v in root.attrib.items())
            open_tag = f'<{strip_ns(root.tag)}' + (f' {attrs}' if attrs else '') + '>'
            md_fh.write(open_tag + '\n')
            html_fh.write(open_tag + '\n')

        md_fh.write(f'</{strip_ns(root.tag)}>\n')
        html_fh.write(f'</{strip_ns(root.tag)}>\n')

    return summary


def make_default_csv_name(output_dir: Path) -> Path:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return output_dir / f'enex_split_log_{ts}.csv'


def main():
    configure_stdio_utf8()

    p = argparse.ArgumentParser(
        description='Stream-process huge Evernote ENEX files, split into Markdown-friendly / HTML-heavy ENEX, and output CSV log.'
    )
    p.add_argument('inputs', nargs='+', help='Input .enex files or wildcard patterns, e.g. export/*.enex **/*.enex')
    p.add_argument('-o', '--output-dir', default='.', help='Output directory')
    p.add_argument('--recursive', action='store_true', help='Enable recursive wildcard expansion for patterns like **/*.enex')
    p.add_argument('--csv-log', default=None, help='CSV log file path (default: output_dir/enex_split_log_YYYYmmdd_HHMMSS.csv)')
    args = p.parse_args()

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files = expand_inputs(args.inputs, recursive=args.recursive)
    if not input_files:
        raise SystemExit('No .enex files matched the given input patterns.')

    csv_path = Path(args.csv_log).expanduser() if args.csv_log else make_default_csv_name(output_dir)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    totals = {
        'files': 0,
        'notes': 0,
        'retitled': 0,
        'md_notes': 0,
        'html_notes': 0,
        'resource_filenames_fixed': 0,
    }

    with csv_path.open('w', newline='', encoding='utf-8-sig') as csv_fh:
        writer = csv.writer(csv_fh)
        writer.writerow([
            'input_file',
            'note_index',
            'original_title',
            'final_title',
            'retitled',
            'has_encrypted',
            'has_note_link',
            'bucket',
            'classification_reason',
            'resource_filenames_fixed',
            'resource_rename_count',
        ])

        for input_path in input_files:
            summary = process_file_streaming(input_path, output_dir, csv_writer=writer)
            totals['files'] += 1
            totals['notes'] += summary['total_notes']
            totals['retitled'] += summary['retitled']
            totals['md_notes'] += summary['md_notes']
            totals['html_notes'] += summary['html_notes']
            totals['resource_filenames_fixed'] += summary['resource_filenames_fixed']
            print(f"Processed: {input_path}")
            print(f"  Markdown ENEX: {summary['md_output']}")
            print(f"  HTML ENEX: {summary['html_output']}")
            print(f"  Notes: {summary['total_notes']} / Retitled: {summary['retitled']} / MD: {summary['md_notes']} / HTML: {summary['html_notes']}")

    print('---')
    print(f"Matched files: {totals['files']}")
    print(f"Total notes: {totals['notes']}")
    print(f"Retitled notes: {totals['retitled']}")
    print(f"Markdown notes: {totals['md_notes']}")
    print(f"HTML notes: {totals['html_notes']}")
    print(f"Resource filename fixes: {totals['resource_filenames_fixed']}")
    print(f"CSV log: {csv_path}")


if __name__ == '__main__':
    main()
