"""Radar Kıbrıs RSS 2.0 bridge. Requires only public/authorized feeds."""
import calendar
import hashlib
import html
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import feedparser
import requests
import trafilatura
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / 'docs'
DATA = ROOT / 'data'
CONTENT_NS = 'http://purl.org/rss/1.0/modules/content/'
MEDIA_NS = 'http://search.yahoo.com/mrss/'
ET.register_namespace('content', CONTENT_NS)
ET.register_namespace('media', MEDIA_NS)
HEADERS = {'User-Agent': 'RadarKibrisRSSBridge/1.0 (editorial feed reader; contact: https://radarkibris.com)'}
MAX_ITEMS = 60
MIN_WORDS = 45


def fetch(url):
    if not url.startswith(('https://', 'http://')):
        raise ValueError('Invalid URL')
    r = requests.get(url, headers=HEADERS, timeout=(8, 20), allow_redirects=True)
    r.raise_for_status()
    if len(r.content) > 5_000_000:
        raise ValueError('Response too large')
    return r


def clean(s):
    return BeautifulSoup(s or '', 'html.parser').get_text(' ', strip=True)


def extract_image(page, entry):
    for media in entry.get('media_content', []) + entry.get('media_thumbnail', []):
        u = media.get('url', '')
        if u.startswith('https://'):
            return u
    soup = BeautifulSoup(page, 'html.parser')
    for selector, attr in [('meta[property="og:image"]', 'content'), ('meta[name="twitter:image"]', 'content')]:
        tag = soup.select_one(selector)
        if tag and tag.get(attr, '').startswith('https://'):
            return tag[attr]
    for link in entry.get('links', []):
        if link.get('type', '').startswith('image/') and link.get('href', '').startswith('https://'):
            return link['href']
    return ''


def make_item(entry, source):
    url = entry.get('link', '').strip()
    if not url.startswith(('https://', 'http://')):
        return None, 'missing_link'
    title = clean(entry.get('title', ''))
    if not title:
        return None, 'missing_title'
    summary = clean(entry.get('summary', ''))
    text = ''
    image = ''
    try:
        response = fetch(url)
        if source.get('full_text', False):
            text = trafilatura.extract(response.text, include_comments=False, include_tables=False) or ''
        image = extract_image(response.text, entry)
    except Exception as exc:
        logging.warning('Article fetch failed %s: %s', url, exc)
        image = extract_image('', entry)
    # Default public feed republishes only the source's short summary, not scraped full articles.
    body = text if source.get('full_text', False) else summary
    if source.get('full_text', False) and len(text.split()) < MIN_WORDS:
        return None, 'short_or_missing_full_text'
    if not body.strip():
        return None, 'missing_content'
    if not image:
        return None, 'missing_image'
    date = entry.get('published_parsed') or entry.get('updated_parsed')
    stamp = calendar.timegm(date) if date else int(time.time())
    guid = hashlib.sha256(url.encode()).hexdigest()
    return {'title': title, 'url': url, 'body': body, 'image': image, 'stamp': stamp, 'guid': guid}, None


def output_feed(source, items):
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    for tag, val in [('title', 'Radar Kıbrıs | ' + source['name']), ('link', 'https://radarkibris.com'),
                     ('description', 'Editör onayı için kaynak haber akışı'), ('language', 'tr'),
                     ('lastBuildDate', format_datetime(datetime.now(timezone.utc)))]:
        ET.SubElement(channel, tag).text = val
    for item in items:
        node = ET.SubElement(channel, 'item')
        for tag, val in [('title', item['title']), ('link', item['url']), ('guid', item['guid']),
                         ('description', item['body'][:450]),
                         ('pubDate', format_datetime(datetime.fromtimestamp(item['stamp'], timezone.utc)))]:
            ET.SubElement(node, tag).text = val
        # CDATA is not required: XML entities safely encode HTML markup.
        content = '<p>' + html.escape(item['body']).replace('\n', '</p><p>') + '</p>'
        ET.SubElement(node, f'{{{CONTENT_NS}}}encoded').text = content
        ET.SubElement(node, 'enclosure', {'url': item['image'], 'type': 'image/jpeg', 'length': '0'})
        ET.SubElement(node, f'{{{MEDIA_NS}}}content', {'url': item['image'], 'medium': 'image'})
    DOCS.mkdir(exist_ok=True)
    ET.ElementTree(rss).write(DOCS / (source['id'] + '.xml'), encoding='utf-8', xml_declaration=True)


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    DOCS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    sources = yaml.safe_load((ROOT / 'sources.yml').read_text(encoding='utf-8'))['sources']
    reports = {}
    for source in sources:
        if not source.get('enabled') or not source.get('feed'):
            reports[source['id']] = {'status': 'disabled_or_unconfigured'}
            continue
        path = DATA / (source['id'] + '.json')
        previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
        stored = {x['guid']: x for x in previous}
        failures = []
        try:
            response = fetch(source['feed'])
            parsed = feedparser.parse(response.content)
            if not parsed.entries:
                raise ValueError('RSS returned no entries')
            for entry in parsed.entries[:35]:
                guid = hashlib.sha256(entry.get('link', '').strip().encode()).hexdigest()
                if guid in stored:
                    continue
                item, error = make_item(entry, source)
                if item:
                    stored[item['guid']] = item
                else:
                    failures.append({'url': entry.get('link', ''), 'reason': error})
                time.sleep(0.5)
            items = sorted(stored.values(), key=lambda x: x['stamp'], reverse=True)[:MAX_ITEMS]
            path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
            output_feed(source, items)
            reports[source['id']] = {'status': 'ok', 'items': len(items), 'failed': failures[:30]}
        except Exception as exc:
            logging.exception('Source failed: %s', source['id'])
            reports[source['id']] = {'status': 'error', 'detail': str(exc)}
            if previous:
                output_feed(source, previous[:MAX_ITEMS])
    (DOCS / 'status.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    (DOCS / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Radar RSS</title><h1>Radar RSS Feeds</h1><p>See status.json for feed health.</p>', encoding='utf-8')
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
