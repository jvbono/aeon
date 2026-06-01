#!/usr/bin/env node
// Parse RSS/Atom XML files in .rss-cache/raw/ and emit recent entries as JSON.
const fs = require('fs');
const path = require('path');

const ROOT = '/home/runner/work/aeon/aeon';
const RAW = path.join(ROOT, '.rss-cache', 'raw');
const HOURS = 48;
const NOW = new Date();
const CUTOFF = new Date(NOW.getTime() - HOURS * 3600 * 1000);

// Parse feeds.yml (simple format: lines with `  - name:` and `    url:`)
const feedsYml = fs.readFileSync(path.join(ROOT, 'memory', 'feeds.yml'), 'utf8');
const feeds = [];
let curName = null;
for (const line of feedsYml.split('\n')) {
  const nameMatch = line.match(/^\s*-\s*name:\s*(.+)$/);
  const urlMatch = line.match(/^\s*url:\s*(.+)$/);
  if (nameMatch) curName = nameMatch[1].trim();
  if (urlMatch && curName) {
    feeds.push({ name: curName, url: urlMatch[1].trim() });
    curName = null;
  }
}
const nameMap = {};
for (const f of feeds) {
  const safe = f.name.replace(/[^A-Za-z0-9]/g, '_');
  nameMap[safe] = f.name;
}

function decode(s) {
  if (!s) return '';
  return s
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, n) => String.fromCharCode(parseInt(n, 16)))
    .replace(/&nbsp;/g, ' ')
    .replace(/&mdash;/g, '—')
    .replace(/&ndash;/g, '–')
    .replace(/&hellip;/g, '…')
    .replace(/&rsquo;/g, '’')
    .replace(/&lsquo;/g, '‘')
    .replace(/&rdquo;/g, '”')
    .replace(/&ldquo;/g, '“')
    .replace(/&amp;/g, '&');
}

function strip(s) {
  if (!s) return '';
  // Remove CDATA
  s = s.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1');
  // Remove tags
  s = s.replace(/<[^>]+>/g, ' ');
  s = decode(s);
  s = s.replace(/\s+/g, ' ').trim();
  return s;
}

function parseDate(s) {
  if (!s) return null;
  s = s.trim();
  const d = new Date(s);
  if (!isNaN(d.getTime())) return d;
  return null;
}

// Extract elements via regex (good enough for RSS/Atom)
function extractAll(xml, tag) {
  const re = new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)</${tag}>`, 'gi');
  const out = [];
  let m;
  while ((m = re.exec(xml)) !== null) out.push(m[1]);
  return out;
}

function extractFirst(xml, tag) {
  const re = new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)</${tag}>`, 'i');
  const m = xml.match(re);
  return m ? m[1] : '';
}

function extractAttr(xml, tag, attr, defaultRel) {
  // For atom links: <link rel="alternate" href="..."/>
  const re = new RegExp(`<${tag}([^>]*)/?>`, 'gi');
  let m;
  while ((m = re.exec(xml)) !== null) {
    const attrs = m[1];
    const relMatch = attrs.match(/rel=["']([^"']+)["']/);
    const rel = relMatch ? relMatch[1] : null;
    if (defaultRel && rel && rel !== defaultRel) continue;
    const hrefMatch = attrs.match(new RegExp(`${attr}=["']([^"']+)["']`));
    if (hrefMatch) return hrefMatch[1];
  }
  return '';
}

function parseFeed(xml) {
  const isAtom = /<feed[\s>]/i.test(xml) && !/<rss[\s>]/i.test(xml);
  const items = [];
  if (isAtom) {
    const entries = extractAll(xml, 'entry');
    for (const e of entries) {
      const title = strip(extractFirst(e, 'title'));
      const link = extractAttr(e, 'link', 'href', 'alternate') || extractAttr(e, 'link', 'href');
      const summary = extractFirst(e, 'summary');
      const content = extractFirst(e, 'content');
      const desc = strip(summary || content).slice(0, 600);
      const pub = strip(extractFirst(e, 'published') || extractFirst(e, 'updated'));
      const d = parseDate(pub);
      items.push({ title, link, desc, date: d });
    }
  } else {
    const its = extractAll(xml, 'item');
    for (const it of its) {
      const title = strip(extractFirst(it, 'title'));
      const link = strip(extractFirst(it, 'link'));
      const desc = strip(extractFirst(it, 'description') || extractFirst(it, 'content:encoded')).slice(0, 600);
      const pub = strip(extractFirst(it, 'pubDate') || extractFirst(it, 'dc:date'));
      const d = parseDate(pub);
      items.push({ title, link, desc, date: d });
    }
  }
  return items;
}

const files = fs.readdirSync(RAW).filter(f => f.endsWith('.xml'));
const results = {};
const errors = [];
let totalAll = 0, totalRecent = 0;
for (const f of files) {
  const safe = f.replace(/\.xml$/, '');
  const feedName = nameMap[safe] || safe;
  const xml = fs.readFileSync(path.join(RAW, f), 'utf8');
  if (xml.length < 200 || !(/<rss[\s>]/i.test(xml) || /<feed[\s>]/i.test(xml) || /<rdf:/i.test(xml))) {
    errors.push([feedName, 'not_a_feed_or_too_small']);
    continue;
  }
  let items;
  try {
    items = parseFeed(xml);
  } catch (e) {
    errors.push([feedName, 'parse_error: ' + e.message]);
    continue;
  }
  const recent = [];
  for (const it of items) {
    totalAll++;
    if (!it.date) continue;
    if (it.date >= CUTOFF) {
      totalRecent++;
      recent.push({
        title: it.title,
        link: it.link,
        desc: it.desc,
        date: it.date.toISOString(),
      });
    }
  }
  if (recent.length) {
    recent.sort((a, b) => (a.date < b.date ? 1 : -1));
    results[feedName] = recent;
  }
}

const out = {
  now: NOW.toISOString(),
  cutoff: CUTOFF.toISOString(),
  feed_count: files.length,
  feeds_with_recent: Object.keys(results).length,
  total_entries: totalAll,
  total_recent: totalRecent,
  errors,
  feeds: results,
};
fs.writeFileSync(path.join(ROOT, '.rss-cache', 'parsed.json'), JSON.stringify(out, null, 2));

const summary = {
  feed_count: out.feed_count,
  feeds_with_recent: out.feeds_with_recent,
  total_recent: out.total_recent,
  errors,
  feed_names_with_recent: Object.keys(results).map(n => `${n} (${results[n].length})`),
};
console.log(JSON.stringify(summary, null, 2));
