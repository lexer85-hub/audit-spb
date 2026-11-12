#!/usr/bin/env python3
"""Build the checked public site for a GitHub Pages URL, without editing sources."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote, unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = 'https://audit-spb.ru/'
DEFAULT_URL = 'https://lexer85-hub.github.io/audit-spb/'


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.tags, self.refs, self.ids = [], [], set()
        self.feed(path.read_text(encoding='utf-8'))

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        self.tags.append((tag, data))
        if data.get('id'):
            self.ids.add(data['id'])
        self.refs.extend(data[key] for key in ('src', 'href') if data.get(key))
        if data.get('srcset'):
            self.refs.extend(item.strip().split()[0] for item in data['srcset'].split(','))
        if tag == 'meta' and data.get('http-equiv') == 'refresh':
            self.refs.append(data['content'].split('url=', 1)[1])


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_site(directory, base_url):
    pages = {p: Page(p) for p in directory.rglob('*.html')}
    base = urlsplit(base_url)
    references = 0
    for path, page in pages.items():
        page_url = base_url + quote(path.relative_to(directory).as_posix())
        canonical = [data.get('href') for tag, data in page.tags
                     if tag == 'link' and data.get('rel') == 'canonical']
        require(canonical == [base_url], f'Incorrect canonical: {path.name}')
        for ref in page.refs:
            url = urlsplit(urljoin(page_url, ref))
            if url.scheme not in ('http', 'https') or url.netloc != base.netloc:
                continue
            require(url.scheme == base.scheme and url.path.startswith(base.path),
                    f'Reference escapes the Pages URL: {ref}')
            target = (directory / unquote(url.path[len(base.path):])).resolve()
            require(target.is_relative_to(directory), f'Unsafe reference: {ref}')
            if target.is_dir():
                target /= 'index.html'
            require(target.is_file(), f'Missing published resource: {ref}')
            if url.fragment and target in pages:
                require(unquote(url.fragment) in pages[target].ids, f'Missing anchor: {ref}')
            references += 1

    main = directory / 'index.html'
    metadata = {data['property']: data.get('content') for tag, data in pages[main].tags
                if tag == 'meta' and data.get('property')}
    require(metadata.get('og:url') == base_url, 'Incorrect og:url')
    schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>',
                                 main.read_text(encoding='utf-8'), re.S)[1])
    require(schema['url'] == base_url, 'Incorrect JSON-LD URL')
    for asset in (metadata.get('og:image', ''), schema['logo']):
        require(asset.startswith(base_url), f'Incorrect absolute asset URL: {asset}')
        target = (directory / unquote(asset[len(base_url):])).resolve()
        require(target.is_relative_to(directory) and target.is_file(),
                f'Missing absolute asset: {asset}')
    sitemap = ET.parse(directory / 'sitemap.xml')
    locations = [node.text for node in sitemap.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
    require(locations == [base_url], 'Incorrect sitemap URL')
    require(f'Sitemap: {base_url}sitemap.xml' in (directory / 'robots.txt').read_text(),
            'Incorrect robots.txt sitemap URL')
    return len(pages), references


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=DEFAULT_URL,
                        help='Public HTTPS site URL, including the repository path.')
    args = parser.parse_args()
    base_url = args.base_url.rstrip('/') + '/'
    url = urlsplit(base_url)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password
            or url.query or url.fragment or any(c.isspace() for c in base_url)
            or '..' in unquote(url.path).split('/')):
        parser.error('--base-url must be an HTTPS URL without credentials, query or fragment')

    subprocess.run([sys.executable, str(ROOT / 'scripts/package-site.py')], cwd=ROOT, check=True)
    artifacts = ROOT / 'artifacts'
    manifest = json.loads((artifacts / 'release-manifest.json').read_text(encoding='utf-8'))
    output = artifacts / 'pages'
    with tempfile.TemporaryDirectory(prefix='pages-build-', dir=artifacts) as temporary:
        staging = Path(temporary).resolve()
        for filename in manifest['files']:
            relative = PurePosixPath(filename)
            require(not relative.is_absolute() and '..' not in relative.parts,
                    f'Unsafe manifest entry: {filename}')
            source = (ROOT / relative).resolve()
            require(source.is_relative_to(ROOT) and source.is_file(), f'Missing source: {filename}')
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix in ('.html', '.xml', '.txt'):
                content = source.read_text(encoding='utf-8').replace(SOURCE_URL, base_url)
                require(base_url == SOURCE_URL or SOURCE_URL not in content,
                        f'Old domain remains in {filename}')
                target.write_text(content, encoding='utf-8')
            else:
                shutil.copy2(source, target)
        (staging / '.nojekyll').touch()
        pages, references = validate_site(staging, base_url)
        if output.exists():
            require(not output.is_symlink(), 'Refusing to replace a symlink at artifacts/pages')
            shutil.rmtree(output)
        shutil.copytree(staging, output)
    print(f'Pages build verified: {pages} HTML pages, {references} internal references; '
          f'{len(manifest["files"]) + 1} files in artifacts/pages; base URL: {base_url}')


if __name__ == '__main__':
    main()
