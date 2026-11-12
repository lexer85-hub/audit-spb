#!/usr/bin/env python3
"""Build a static deployment ZIP, excluding backups, reports and unused legacy assets."""
from pathlib import Path
from urllib.parse import urlsplit, unquote
import json
import re
import runpy
import zipfile

ROOT = Path(__file__).resolve().parents[1]
checks = runpy.run_path(str(ROOT / 'scripts/check-site.py'))
files = {Path('index.css'), Path('site.js'), Path('robots.txt'), Path('sitemap.xml')}
for path, page in checks['pages'].items():
    files.add(path.relative_to(ROOT))
    for ref in page.refs:
        url = urlsplit(ref)
        if url.scheme or url.netloc or not url.path: continue
        target = (path.parent / unquote(url.path)).resolve()
        if target.is_dir(): target /= 'index.html'
        files.add(target.relative_to(ROOT))
main = (ROOT / 'index.html').read_text()
schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', main, re.S)[1])
files.add(Path(urlsplit(schema['logo']).path.lstrip('/')))
for tag, data in checks['main'].tags:
    if tag == 'meta' and data.get('property') == 'og:image':
        files.add(Path(urlsplit(data['content']).path.lstrip('/')))
archive = ROOT / 'artifacts/stak-optimized-2026-11-12.zip'
archive.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for path in sorted(files): z.write(ROOT / path, str(path))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any(name.startswith(('artifacts/', 'scripts/')) for name in z.namelist())
manifest = {'archive': archive.name, 'file_count': len(files), 'zip_bytes': archive.stat().st_size, 'uncompressed_bytes': sum((ROOT / p).stat().st_size for p in files), 'files': [str(p) for p in sorted(files)]}
(ROOT / 'artifacts/release-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
print(f'Release: {archive.name}; {len(files)} files; {archive.stat().st_size:,} bytes; ZIP verified.')
