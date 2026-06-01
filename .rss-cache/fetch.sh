#!/usr/bin/env bash
# Parallel-fetch all feeds with timeouts
set -u
mkdir -p /home/runner/work/aeon/aeon/.rss-cache/raw
cd /home/runner/work/aeon/aeon/.rss-cache/raw

fetch_one() {
  local name="$1"
  local url="$2"
  local safe=$(echo "$name" | tr -c 'A-Za-z0-9' '_' )
  curl -sL --max-time 20 -A "Mozilla/5.0 (compatible; Aeon-RSS/1.0)" "$url" -o "${safe}.xml" 2>/dev/null
  echo "$safe|$name|$url|$(wc -c < "${safe}.xml" 2>/dev/null || echo 0)"
}

export -f fetch_one

# Build feed list (name|url)
python3 -c "
import yaml
with open('/home/runner/work/aeon/aeon/memory/feeds.yml') as f:
    d = yaml.safe_load(f)
for feed in d['feeds']:
    print(f\"{feed['name']}|{feed['url']}\")
" > /tmp/feedlist.txt

# Parallel fetch (8 at a time)
cat /tmp/feedlist.txt | while IFS='|' read -r name url; do
  fetch_one "$name" "$url" &
  # Limit concurrent jobs
  while [ "$(jobs -r | wc -l)" -ge 8 ]; do sleep 0.2; done
done
wait
echo "DONE"
