# Server Environment & Citation Map Skill

## Server Environment

- **Hostname**: `instance-5-36` (`172.16.5.36`)
- **User**: `root`
- **OS**: Linux (Ubuntu)
- **Python**: `/root/miniconda3/bin/python3` (3.10)
- **Node**: Available via `/usr/bin/npx`
- **Chrome**: `/usr/bin/google-chrome` (v145) — NO `$DISPLAY`, headless only
- **Chromedriver**: Not installed (proxy blocks download)
- **Playwright**: Installed (`npx playwright`) but browsers not downloaded (proxy blocks CDN)

## Proxy Configuration (REQUIRED for external network access)

```bash
export http_proxy=http://172.16.5.77:8889
export https_proxy=http://172.16.5.77:8889
```

**Important**:
- ALL external HTTP/HTTPS requests require this proxy (pip install, scholarly, geopy, etc.)
- `localhost` requests are intercepted by proxy — use `--noproxy '*'` with curl or `no_proxy=localhost` prefix
- Proxy drops large downloads (~100MB+) intermittently — Playwright browser installs and chromedriver fail
- Selenium WebDriver cannot auto-download chromedriver through this proxy

## Citation World Map

### Overview

The homepage (`index.html`) displays an interactive Citation World Map below the Visitor Map section. It shows the geographic distribution of co-authors extracted from Google Scholar.

### Architecture

```
scripts/generate_citation_data.py  →  data/citation_data.json  →  index.html (inline JS)
         (offline, ~2-5 min)              (static JSON)              (SVG coloring)
```

### Data Generation

```bash
# Set proxy
export http_proxy=http://172.16.5.77:8889
export https_proxy=http://172.16.5.77:8889

# Run generator (uses scholarly + geopy, fully headless)
python scripts/generate_citation_data.py

# Output: data/citation_data.json
# Cache: scripts/.citation_cache/ (delete to re-scrape from scratch)
```

**Dependencies**: `scholarly`, `geopy`, `pycountry`, `tqdm` (all installed via `pip install citation-map`)

### Strategy: Co-author Approach

The original CitationMap tool iterates through every citing paper (O(total_citations) requests) which takes hours for 1000+ citations. Instead, we:

1. Fetch the author profile and extract co-authors from the profile section + publication author lists
2. Look up each unique co-author on Google Scholar to get their affiliation
3. Geocode affiliations using known affiliation dictionary + Nominatim fallback
4. Aggregate by country → output JSON

This completes in ~2-5 minutes instead of hours.

### JSON Schema

```json
{
  "scholar_id": "1ckaPgwAAAAJ",
  "total_coauthors": 13,
  "total_countries": 3,
  "total_institutions": 11,
  "countries": {
    "CN": {
      "name": "China",
      "count": 9,
      "institutions": [
        {"name": "Peking University", "count": 2, "lat": 39.9869, "lng": 116.3059}
      ]
    }
  }
}
```

### Frontend Integration

- **SVG**: Reuses `assets/img/world-map.min.svg` (same as Visitor Map)
- **Country IDs**: Lowercase ISO 3166-1 alpha-2 (e.g., `id="cn"`, `id="gb"`, `id="au"`)
- **Color scale**: Warm orange tones (`#fde8d0` → `#b35a1a`), distinct from Visitor Map's blue
- **Tooltip**: Shows country name, co-author count, top 5 institutions
- **Location in index.html**: CSS (~line 537), HTML (~line 888), JS (~line 1062)

### Known Limitations

- Co-author approach shows collaboration network, not citation distribution
- Some co-authors may not have Google Scholar profiles → missed
- Geocoding relies on affiliation strings which may be ambiguous
- Google Scholar may throttle if run too frequently — use cache
- `scripts/.citation_cache/` stores pickle files to avoid re-scraping

### Changing Scholar ID

Edit `SCHOLAR_ID` in `scripts/generate_citation_data.py` (line ~44), delete cache, and re-run.
