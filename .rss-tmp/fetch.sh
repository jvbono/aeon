#!/bin/bash
set +e
cd "$(dirname "$0")"
while IFS='|' read -r name url; do
  ( curl -sL --max-time 15 -A "Mozilla/5.0 (Aeon RSS Digest)" "$url" -o "${name}.xml" 2>/dev/null ) &
done < feeds.txt
wait
ls -la *.xml | wc -l
