#!/usr/bin/env python3
"""Build the checked public site for a GitHub Pages URL, without editing sources."""
import argparse
from datetime import date, datetime
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = 'https://audit-spb.ru/'
DEFAULT_URL = 'https://lexer85-hub.github.io/audit-spb/'
VERIFICATION_FILES = {
    'google55676c936f3df7f0.html': 'google-site-verification: google55676c936f3df7f0.html',
    'yandex_543f725de89851ae.html': '''<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    </head>
    <body>Verification: 543f725de89851ae</body>
</html>''',
}


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.tags, self.refs, self.ids, self.images = [], [], [], []
        self.titles, self.schemas = [], []
        self._title, self._schema = None, None
        self.feed(path.read_text(encoding='utf-8'))

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        self.tags.append((tag, data))
        if data.get('id'):
            self.ids.append(data['id'])
        self.refs.extend(data[key] for key in ('src', 'href') if data.get(key))
        if data.get('srcset'):
            self.refs.extend(item.strip().split()[0] for item in data['srcset'].split(','))
        if tag == 'meta' and data.get('http-equiv') == 'refresh':
            self.refs.append(data['content'].split('url=', 1)[1])
        if tag == 'img':
            self.images.append(data)
        if tag == 'title':
            self._title = []
        if tag == 'script' and data.get('type', '').lower() == 'application/ld+json':
            self._schema = []

    def handle_data(self, data):
        if self._title is not None:
            self._title.append(data)
        if self._schema is not None:
            self._schema.append(data)

    def handle_endtag(self, tag):
        if tag == 'title' and self._title is not None:
            self.titles.append(''.join(self._title).strip())
            self._title = None
        if tag == 'script' and self._schema is not None:
            try:
                self.schemas.append(json.loads(''.join(self._schema)))
            except json.JSONDecodeError as error:
                raise ValueError(f'{self.path.name}: invalid JSON-LD: {error}') from error
            self._schema = None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_verification_files(directory):
    # Provider-issued verification files are not content pages or redirects.
    for filename, expected in VERIFICATION_FILES.items():
        path = directory / filename
        require(path.is_file(), f'Missing ownership verification file: {filename}')
        require(path.read_text(encoding='utf-8').strip() == expected,
                f'Changed ownership verification content: {filename}')


def validate_homepage(directory, base_url, pages):
    """Apply the same SEO checks to source files and the rewritten Pages build."""
    page = pages[directory / 'index.html']

    def meta(name, attribute='name'):
        values = [data.get('content', '').strip() for tag, data in page.tags
                  if tag == 'meta' and data.get(attribute, '').lower() == name]
        require(len(values) == 1 and values[0], f'Expected one nonempty {name} meta tag')
        return values[0]

    require(sum(tag == 'title' for tag, _ in page.tags) == len(page.titles) == 1 and page.titles[0],
            'Expected one nonempty homepage title')
    meta('description')
    canonical = [data.get('href') for tag, data in page.tags
                 if tag == 'link' and 'canonical' in data.get('rel', '').lower().split()]
    require(canonical == [base_url], 'Incorrect or duplicate homepage canonical')
    for tag, data in page.tags:
        if tag == 'meta' and data.get('name', '').lower() in ('robots', 'googlebot', 'yandex'):
            directives = set(re.split(r'[,\s]+', data.get('content', '').lower()))
            require(not directives.intersection(('noindex', 'none')), 'Homepage must remain indexable')
    require(not any(tag == 'meta' and data.get('http-equiv', '').lower() == 'refresh'
                    for tag, data in page.tags), 'Homepage must not redirect')
    require(meta('og:url', 'property') == base_url, 'Incorrect og:url')
    social_image = meta('og:image', 'property')
    require(meta('twitter:card') == 'summary_large_image', 'Incorrect Twitter card type')
    require(meta('twitter:image') == social_image, 'Social image URLs must match')
    for dimension in ('width', 'height'):
        value = meta(f'og:image:{dimension}', 'property')
        require(value.isdigit() and int(value) > 0, f'Invalid social image {dimension}')

    require(page.schemas and all(isinstance(item, dict) for item in page.schemas),
            'Expected JSON-LD objects on the homepage')
    organizations = [item for item in page.schemas if item.get('@type') == 'AccountingService']
    websites = [item for item in page.schemas if item.get('@type') == 'WebSite']
    require(len(organizations) == len(websites) == 1, 'Expected AccountingService and WebSite entities')
    organization, website = organizations[0], websites[0]
    require(page.schemas[0] is organization, 'AccountingService must remain the first JSON-LD block')
    organization_id = base_url + '#organization'
    require(organization.get('@id') == organization_id, 'Incorrect organization identifier')
    require(website.get('@id') == base_url + '#website', 'Incorrect website identifier')
    for entity in (organization, website):
        require(entity.get('url') == base_url, 'Incorrect JSON-LD URL')
        require(entity.get('name') and entity.get('alternateName'), 'Missing structured entity names')
    require(website.get('publisher', {}).get('@id') == organization_id, 'Incorrect website publisher')
    require(website.get('inLanguage') == 'ru-RU', 'Incorrect website language')
    require(organization.get('description'), 'Missing business description')
    require(organization.get('areaServed', {}).get('@type') == 'City', 'Missing service area')
    geo = organization.get('geo', {})
    require(geo.get('@type') == 'GeoCoordinates'
            and isinstance(geo.get('latitude'), (int, float)) and -90 <= geo['latitude'] <= 90
            and isinstance(geo.get('longitude'), (int, float)) and -180 <= geo['longitude'] <= 180,
            'Invalid business coordinates')
    maps = [data.get('src') for tag, data in page.tags if tag == 'iframe']
    require(organization.get('hasMap') in maps, 'Structured map must match the visible map')
    catalog = organization.get('hasOfferCatalog', {})
    offers = catalog.get('itemListElement', [])
    require(catalog.get('@type') == 'OfferCatalog' and len(offers) == 4, 'Expected four catalog offers')
    service_ids, service_urls = [], []
    for offer in offers:
        service = offer.get('itemOffered', {})
        require(offer.get('@type') == 'Offer' and service.get('@type') == 'Service', 'Invalid service offer')
        require(service.get('name') and service.get('description'), 'Missing service name or description')
        require(service.get('provider', {}).get('@id') == organization_id, 'Incorrect service provider')
        service_id = service.get('@id', '')
        require(service_id.startswith(base_url + '#') and len(service_id) > len(base_url) + 1,
                'Incorrect service identifier')
        service_ids.append(service_id)
        url = urlsplit(service.get('url', ''))
        require(url._replace(fragment='').geturl() == base_url and unquote(url.fragment) in page.ids,
                f'Service URL must point to an existing homepage section: {service.get("url")}')
        service_urls.append(url.geturl())
    require(len(set(service_ids + [organization_id, website['@id']])) == 6
            and len(set(service_urls)) == 4, 'Duplicate structured entities or catalog services')
    for asset in (social_image, organization.get('logo', '')):
        require(asset.startswith(base_url), f'Incorrect absolute asset URL: {asset}')
        target = (directory / unquote(asset[len(base_url):])).resolve()
        require(target.is_relative_to(directory) and target.is_file(), f'Missing absolute asset: {asset}')

    namespace = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap = ET.parse(directory / 'sitemap.xml')
    entries = sitemap.findall('sm:url', namespace)
    require([entry.findtext('sm:loc', namespaces=namespace) for entry in entries] == [base_url],
            'Sitemap must contain only the indexable canonical homepage')
    today = datetime.now(ZoneInfo('Europe/Moscow')).date()
    for entry in entries:
        lastmod = entry.findtext('sm:lastmod', namespaces=namespace) or ''
        require(re.fullmatch(r'\d{4}-\d{2}-\d{2}', lastmod), 'Sitemap lastmod must be an ISO date')
        require(date.fromisoformat(lastmod) <= today, 'Sitemap lastmod cannot be in the future')
    robots = RobotFileParser()
    robots.parse((directory / 'robots.txt').read_text(encoding='utf-8').splitlines())
    require(robots.site_maps() == [base_url + 'sitemap.xml'], 'Incorrect robots.txt sitemap URL')
    for crawler in ('*', 'Googlebot', 'YandexBot'):
        require(robots.can_fetch(crawler, base_url), f'Homepage blocked in robots.txt for {crawler}')
    return organization


def validate_site(directory, base_url):
    pages = {p: Page(p) for p in directory.rglob('*.html')}
    validate_verification_files(directory)
    base = urlsplit(base_url)
    references = 0
    for path, page in pages.items():
        if path.parent == directory and path.name in VERIFICATION_FILES:
            continue
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

    validate_homepage(directory, base_url, pages)
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
            if filename in VERIFICATION_FILES:
                shutil.copyfile(source, target)
            elif source.suffix in ('.html', '.xml', '.txt'):
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
