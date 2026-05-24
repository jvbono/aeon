#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const FEED_NAMES = {
  cbc_politics: "CBC Politics",
  canadaland: "Canadaland",
  globe_opinion: "Globe and Mail Opinion",
  the_tyee: "The Tyee",
  walrus_politics: "The Walrus Politics",
  ipolitics: "iPolitics",
  breach_media: "Breach Media",
  pluralistic: "Pluralistic",
  disconnect: "Disconnect",
  michael_geist: "Michael Geist",
  policy_options: "Policy Options",
  priv_canada: "Privacy Commissioner of Canada",
  the_markup: "The Markup",
  eff: "EFF",
  betakit: "BetaKit",
  citation_needed: "Citation Needed",
  jwz: "JWZ",
  schneier: "Schneier on Security",
  joan_westenberg: "Joan Westenberg",
  ed_zitron: "Ed Zitron",
  convivial: "The Convivial Society",
  contraptions: "Contraptions",
  fourzerofour: "404 Media",
  platformer: "Platformer",
  garbage_day: "Garbage Day",
  tech_policy_press: "Tech Policy Press",
  techdirt: "Techdirt",
  robin_sloan: "Robin Sloan",
  ted_gioia: "Ted Gioia",
  dada_drummer: "Dada Drummer",
  aquarium_drunkard: "Aquarium Drunkard",
  interdependence: "Interdependence",
  metalabel: "Metalabel",
  new_models: "New Models",
  kneeling_bus: "Kneeling Bus",
  real_life: "Real Life",
  nplusone: "n+1",
  unpopular_front: "Unpopular Front",
  yancey_strickler: "Yancey Strickler",
};

const NOW = new Date();
const CUTOFF = new Date(NOW.getTime() - 48 * 3600 * 1000);

function stripHtml(s) {
  if (!s) return "";
  return s
    .replace(/<!\[CDATA\[/g, "")
    .replace(/\]\]>/g, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#8217;/g, "'")
    .replace(/&#8216;/g, "'")
    .replace(/&#8220;/g, '"')
    .replace(/&#8221;/g, '"')
    .replace(/&#8211;/g, "-")
    .replace(/&#8212;/g, "—")
    .replace(/\s+/g, " ")
    .trim();
}

function parseDate(s) {
  if (!s) return null;
  s = s.trim();
  const d = new Date(s);
  if (isNaN(d.getTime())) return null;
  return d;
}

function extract(block, tag) {
  // Matches <tag ...>...</tag> non-greedy across newlines
  const re = new RegExp(`<${tag}(?:\\s+[^>]*)?>([\\s\\S]*?)</${tag}>`, "i");
  const m = block.match(re);
  return m ? m[1] : "";
}

function extractAttr(block, tag, attr) {
  const re = new RegExp(`<${tag}\\s+[^>]*?${attr}=["']([^"']+)["']`, "i");
  const m = block.match(re);
  return m ? m[1] : "";
}

function parseFeed(xml, key) {
  const items = [];
  // RSS 2.0: <item>...</item>
  const itemRe = /<item(?:\s[^>]*)?>([\s\S]*?)<\/item>/gi;
  let m;
  while ((m = itemRe.exec(xml)) !== null) {
    const block = m[1];
    const title = stripHtml(extract(block, "title"));
    let link = stripHtml(extract(block, "link"));
    if (!link) {
      link = extractAttr(block, "link", "href");
    }
    const dateStr =
      extract(block, "pubDate") ||
      extract(block, "dc:date") ||
      extract(block, "published") ||
      extract(block, "updated");
    const desc = extract(block, "description");
    const content = extract(block, "content:encoded") || extract(block, "content");
    const d = parseDate(stripHtml(dateStr));
    if (!d || d < CUTOFF) continue;
    items.push({
      title,
      link,
      date: d.toISOString(),
      summary: stripHtml(content || desc).slice(0, 700),
      feed: FEED_NAMES[key] || key,
    });
  }
  // Atom: <entry>...</entry>
  const entryRe = /<entry(?:\s[^>]*)?>([\s\S]*?)<\/entry>/gi;
  while ((m = entryRe.exec(xml)) !== null) {
    const block = m[1];
    const title = stripHtml(extract(block, "title"));
    let link = extractAttr(block, "link", "href");
    if (!link) link = stripHtml(extract(block, "link"));
    const dateStr =
      extract(block, "published") ||
      extract(block, "updated") ||
      extract(block, "pubDate");
    const summary = extract(block, "summary");
    const content = extract(block, "content");
    const d = parseDate(stripHtml(dateStr));
    if (!d || d < CUTOFF) continue;
    items.push({
      title,
      link,
      date: d.toISOString(),
      summary: stripHtml(content || summary).slice(0, 700),
      feed: FEED_NAMES[key] || key,
    });
  }
  return items;
}

const base = path.dirname(path.resolve(__filename));
const files = fs.readdirSync(base).filter((f) => f.endsWith(".xml") && f !== "test.xml");
const allItems = [];
const counts = {};
for (const f of files) {
  const key = f.replace(".xml", "");
  const xml = fs.readFileSync(path.join(base, f), "utf8");
  if (xml.length < 100) {
    counts[FEED_NAMES[key] || key] = 0;
    continue;
  }
  const items = parseFeed(xml, key);
  counts[FEED_NAMES[key] || key] = items.length;
  allItems.push(...items);
}
allItems.sort((a, b) => b.date.localeCompare(a.date));
fs.writeFileSync(
  path.join(base, "items.json"),
  JSON.stringify({ items: allItems, counts, cutoff: CUTOFF.toISOString(), now: NOW.toISOString() }, null, 2)
);
console.log(`Total items (last 48h): ${allItems.length}`);
const withItems = Object.entries(counts).filter(([, v]) => v > 0);
console.log(`Feeds with items: ${withItems.length}/${Object.keys(counts).length}`);
for (const [name, count] of withItems.sort((a, b) => b[1] - a[1])) {
  console.log(`  ${name}: ${count}`);
}
const zero = Object.entries(counts).filter(([, v]) => v === 0).map(([n]) => n);
if (zero.length) console.log(`Zero items: ${zero.join(", ")}`);
