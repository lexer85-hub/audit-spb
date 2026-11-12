#!/usr/bin/env python3
"""Check static release references and markup with the Python standard library."""
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, unquote
import runpy

ROOT = Path(__file__).resolve().parents[1]
build_checks = runpy.run_path(str(ROOT / 'scripts/build-pages.py'))
Page = build_checks['Page']

pages = {p.resolve(): Page(p) for p in [*ROOT.glob('*.html'), *ROOT.glob('blog/*.html')]}
errors = []
reference_count = 0
for path, page in pages.items():
    duplicates = [key for key, count in Counter(page.ids).items() if count > 1]
    if duplicates: errors.append(f'{path.name}: duplicate IDs {duplicates}')
    for reference in page.refs:
        reference_count += 1
        url = urlsplit(reference)
        if url.scheme or url.netloc: continue
        target = (path.parent / unquote(url.path)).resolve() if url.path else path
        if target.is_dir(): target /= 'index.html'
        if not target.is_file(): errors.append(f'{path.name}: missing {reference}')
        if url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
            errors.append(f'{path.name}: missing anchor {reference}')
    for img in page.images:
        if not all(key in img for key in ('alt', 'width', 'height')):
            errors.append(f'{path.name}: image lacks alt or dimensions: {img.get("src")}')
main = pages[(ROOT / 'index.html').resolve()]
assert sum(tag == 'h1' for tag, _ in main.tags) == 1, 'Exactly one h1 required'
text = (ROOT / 'index.html').read_text()
assert all(value not in text for value in ('nicepage.js', 'jquery.js', 'nicepage.css', 'fonts.googleapis.com'))
maps = [data for tag, data in main.tags if tag == 'iframe']
assert len(maps) == 1 and urlsplit(maps[0]['src']).hostname == 'yandex.ru', 'Expected a Yandex map'
assert maps[0].get('loading') == 'lazy' and maps[0].get('title'), 'Map needs lazy loading and an accessible title'
assert 'maps.google.com' not in text, 'Old Google map must be removed'
assert 'mailto:stak@audit-spb.ru' in text and 'tel:+79112158515' in text
schema = build_checks['validate_homepage'](ROOT, 'https://audit-spb.ru/', pages)
assert schema['telephone'] == '+79112158515'
for page in pages.values():
    if page.path.name != 'index.html':
        assert any(tag == 'meta' and data.get('name') == 'robots' and 'noindex' in data['content'] for tag,data in page.tags)
if errors:
    raise SystemExit('\n'.join(errors))
print(f'PASS: {len(pages)} HTML pages; {reference_count} references; anchors; image attributes; SEO metadata; JSON-LD catalog; indexability; sitemap dates; redirect noindex; no legacy dependencies.')
