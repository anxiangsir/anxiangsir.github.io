#!/usr/bin/env python3
"""
Generate citation_data.json for the static Citation World Map.

Uses Semantic Scholar API to collect all citing authors, then geocodes their
affiliations to produce a JSON file aggregated by country.

Strategy:
  1. S2 /author/{id}/papers  -> get all papers
  2. S2 /paper/{id}/citations -> get all citing papers + author IDs (paginated)
  3. S2 /author/batch          -> batch lookup author affiliations (500/request)
  4. Geocode affiliations via KNOWN_AFFILIATIONS dict + Nominatim fallback
  5. Aggregate by country -> JSON

Rate-limiting:
  - S2 unauthenticated: ~1 req/sec (100 req/5min)
  - 1.2s delay between requests, 30s backoff on 429
  - Incremental cache: resume after any interruption

Usage:
    export http_proxy=http://172.16.5.77:8889
    export https_proxy=http://172.16.5.77:8889
    pip install requests geopy pycountry tqdm
    python scripts/generate_citation_data.py
"""

import json
import os
import pickle
import time
from collections import Counter
from pathlib import Path

import requests
from geopy.geocoders import Nominatim
from tqdm import tqdm

# === Configuration ===
S2_AUTHOR_ID = "2054941340"  # Semantic Scholar author ID for Xiang An
GS_SCHOLAR_ID = "1ckaPgwAAAAJ"  # Google Scholar ID (for JSON metadata)
S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_DELAY = 1.2  # seconds between S2 API calls
S2_BACKOFF = 30  # seconds to wait on 429
S2_BATCH_SIZE = 500  # authors per batch request (max 1000)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".citation_cache")
OUTPUT_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "citation_data.json",
)


def load_cache(name: str):
    path = os.path.join(CACHE_DIR, f"{name}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None


def save_cache(name: str, data):
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{name}.pkl")
    with open(path, "wb") as f:
        pickle.dump(data, f)


def s2_get(url, params=None, timeout=30):
    """GET request to S2 API with rate-limit handling."""
    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                wait = S2_BACKOFF * (attempt + 1)
                print(f"    [429] Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429:
                time.sleep(S2_BACKOFF * (attempt + 1))
                continue
            raise
        except Exception as e:
            print(f"    [ERR] {type(e).__name__}: {e}")
            time.sleep(5)
    return None


def s2_post(url, json_body, params=None, timeout=60):
    """POST request to S2 API with rate-limit handling."""
    for attempt in range(5):
        try:
            resp = requests.post(url, json=json_body, params=params, timeout=timeout)
            if resp.status_code == 429:
                wait = S2_BACKOFF * (attempt + 1)
                print(f"    [429] Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError:
            if resp.status_code == 429:
                time.sleep(S2_BACKOFF * (attempt + 1))
                continue
            raise
        except Exception as e:
            print(f"    [ERR] {type(e).__name__}: {e}")
            time.sleep(5)
    return None


# ─── Step 1: Get all papers ───────────────────────────────────────────

def step1_get_papers() -> list:
    """Fetch all papers for the author from Semantic Scholar."""
    cached = load_cache("s2_papers")
    if cached:
        print(f"  Loaded {len(cached)} cached papers")
        return cached

    print(f"[1/4] Fetching papers for S2 author {S2_AUTHOR_ID} ...")
    data = s2_get(f"{S2_API_BASE}/author/{S2_AUTHOR_ID}", params={
        "fields": "name,paperCount,citationCount,hIndex"
    })
    if data:
        print(f"  Name: {data.get('name')}")
        print(f"  Papers: {data.get('paperCount')}, Citations: {data.get('citationCount')}")

    time.sleep(S2_DELAY)

    papers = []
    offset = 0
    while True:
        resp = s2_get(f"{S2_API_BASE}/author/{S2_AUTHOR_ID}/papers", params={
            "fields": "paperId,title,citationCount",
            "limit": 1000,
            "offset": offset,
        })
        if not resp or not resp.get("data"):
            break
        papers.extend(resp["data"])
        if resp.get("next") is None:
            break
        offset = resp["next"]
        time.sleep(S2_DELAY)

    papers.sort(key=lambda p: p.get("citationCount", 0), reverse=True)
    total_cites = sum(p.get("citationCount", 0) for p in papers)
    print(f"  Found {len(papers)} papers, {total_cites} total citations")

    save_cache("s2_papers", papers)
    return papers


# ─── Step 2: Collect all citing author IDs ────────────────────────────

def step2_collect_citing_authors(papers: list) -> set:
    """For each paper, paginate through all citations to collect author IDs."""
    progress = load_cache("s2_citing_progress") or {
        "completed_papers": set(),
        "author_ids": set(),
    }
    completed = progress["completed_papers"]
    all_author_ids = progress["author_ids"]

    remaining = [p for p in papers if p["paperId"] not in completed and p.get("citationCount", 0) > 0]

    if not remaining:
        print(f"  All papers already processed. {len(all_author_ids)} unique citing author IDs.")
        return all_author_ids

    print(f"\n[2/4] Collecting citing author IDs ({len(remaining)} papers remaining) ...")

    for i, paper in enumerate(remaining):
        pid = paper["paperId"]
        title = paper["title"][:55]
        nc = paper.get("citationCount", 0)
        paper_aids = set()
        offset = 0

        while True:
            time.sleep(S2_DELAY)
            resp = s2_get(f"{S2_API_BASE}/paper/{pid}/citations", params={
                "fields": "authors",
                "limit": 1000,
                "offset": offset,
            })
            if not resp or not resp.get("data"):
                break

            for item in resp["data"]:
                for author in item.get("citingPaper", {}).get("authors", []):
                    aid = author.get("authorId")
                    if aid:
                        paper_aids.add(aid)

            if resp.get("next") is None:
                break
            offset = resp["next"]

        all_author_ids.update(paper_aids)
        completed.add(pid)
        save_cache("s2_citing_progress", progress)
        print(f"  [{i+1}/{len(remaining)}] {title} ({nc} cites) "
              f"-> {len(paper_aids)} IDs (total: {len(all_author_ids)})")

    print(f"\n  Total unique citing author IDs: {len(all_author_ids)}")
    return all_author_ids


# ─── Step 3: Batch lookup affiliations ────────────────────────────────

def step3_lookup_affiliations(author_ids: set) -> list:
    """Batch lookup author affiliations via S2 /author/batch API."""
    cached_lookups = load_cache("s2_affiliations") or {}
    ids_list = list(author_ids)
    remaining = [aid for aid in ids_list if aid not in cached_lookups]

    if not remaining:
        print(f"  All {len(author_ids)} authors already looked up.")
    else:
        print(f"\n[3/4] Batch-looking up {len(remaining)} authors "
              f"({len(cached_lookups)} cached) ...")

        for batch_start in range(0, len(remaining), S2_BATCH_SIZE):
            batch = remaining[batch_start:batch_start + S2_BATCH_SIZE]
            batch_num = batch_start // S2_BATCH_SIZE + 1
            total_batches = (len(remaining) + S2_BATCH_SIZE - 1) // S2_BATCH_SIZE

            time.sleep(S2_DELAY)
            result = s2_post(
                f"{S2_API_BASE}/author/batch",
                json_body={"ids": batch},
                params={"fields": "name,affiliations"},
            )

            if result:
                has_aff = 0
                for author_data in result:
                    if author_data and author_data.get("authorId"):
                        aid = author_data["authorId"]
                        affs = author_data.get("affiliations", [])
                        cached_lookups[aid] = {
                            "name": author_data.get("name", ""),
                            "affiliations": affs,
                        }
                        if affs:
                            has_aff += 1
                    elif author_data is None:
                        # Author not found
                        pass

                save_cache("s2_affiliations", cached_lookups)
                print(f"  Batch {batch_num}/{total_batches}: "
                      f"{len(batch)} authors, {has_aff} with affiliations")

    # Build results list
    results = []
    for aid in author_ids:
        info = cached_lookups.get(aid)
        if not info:
            continue
        affs = info.get("affiliations", [])
        if affs:
            # Use first affiliation as primary
            results.append({
                "author_id": aid,
                "author_name": info["name"],
                "affiliation": affs[0],  # primary affiliation
            })

    total_with = len(results)
    print(f"\n  {total_with}/{len(author_ids)} authors have affiliations "
          f"({100*total_with/max(len(author_ids),1):.1f}%)")
    return results


# ─── Step 4: Geocode + Aggregate ──────────────────────────────────────

AFFILIATION_PREFIXES = [
    "professor at ", "associate professor at ", "assistant professor at ",
    "postdoc at ", "postdoctoral researcher at ", "phd student at ",
    "research scientist at ", "researcher at ", "engineer at ",
    "senior researcher at ", "lecturer at ", "reader at ",
    "professor, ", "associate professor, ", "assistant professor, ",
    "ph.d. student at ", "ph.d. candidate at ", "graduate student at ",
    "department of ", "school of ", "faculty of ", "lab of ",
]

KNOWN_AFFILIATIONS = {
    # --- United States ---
    "google": ("United States", "US", 37.4220, -122.0841),
    "meta": ("United States", "US", 37.4851, -122.1483),
    "facebook": ("United States", "US", 37.4851, -122.1483),
    "microsoft": ("United States", "US", 47.6457, -122.1318),
    "amazon": ("United States", "US", 47.6228, -122.3372),
    "apple": ("United States", "US", 37.3349, -122.0090),
    "nvidia": ("United States", "US", 37.3709, -122.0386),
    "intel": ("United States", "US", 37.3875, -121.9636),
    "ibm": ("United States", "US", 41.1072, -73.7209),
    "adobe": ("United States", "US", 37.3310, -121.8922),
    "openai": ("United States", "US", 37.7749, -122.4194),
    "deepmind": ("United States", "US", 37.4220, -122.0841),
    "salesforce": ("United States", "US", 37.7749, -122.4194),
    "qualcomm": ("United States", "US", 32.8998, -117.1971),
    "mit": ("United States", "US", 42.3601, -71.0942),
    "massachusetts institute": ("United States", "US", 42.3601, -71.0942),
    "stanford": ("United States", "US", 37.4275, -122.1697),
    "cmu": ("United States", "US", 40.4433, -79.9436),
    "carnegie mellon": ("United States", "US", 40.4433, -79.9436),
    "berkeley": ("United States", "US", 37.8719, -122.2585),
    "harvard": ("United States", "US", 42.3770, -71.1167),
    "yale": ("United States", "US", 41.3163, -72.9223),
    "princeton": ("United States", "US", 40.3431, -74.6551),
    "columbia university": ("United States", "US", 40.8075, -73.9626),
    "georgia tech": ("United States", "US", 33.7756, -84.3963),
    "georgia institute": ("United States", "US", 33.7756, -84.3963),
    "university of michigan": ("United States", "US", 42.2780, -83.7382),
    "michigan state": ("United States", "US", 42.7010, -84.4822),
    "university of maryland": ("United States", "US", 38.9869, -76.9426),
    "johns hopkins": ("United States", "US", 39.3299, -76.6205),
    "university of illinois": ("United States", "US", 40.1020, -88.2272),
    "uiuc": ("United States", "US", 40.1020, -88.2272),
    "cornell": ("United States", "US", 42.4534, -76.4735),
    "ucla": ("United States", "US", 34.0689, -118.4452),
    "uc san diego": ("United States", "US", 32.8801, -117.2340),
    "ucsd": ("United States", "US", 32.8801, -117.2340),
    "uc davis": ("United States", "US", 38.5382, -121.7617),
    "uc santa barbara": ("United States", "US", 34.4140, -119.8489),
    "university of washington": ("United States", "US", 47.6553, -122.3035),
    "nyu": ("United States", "US", 40.7295, -73.9965),
    "new york university": ("United States", "US", 40.7295, -73.9965),
    "upenn": ("United States", "US", 39.9522, -75.1932),
    "university of pennsylvania": ("United States", "US", 39.9522, -75.1932),
    "duke": ("United States", "US", 36.0014, -78.9382),
    "purdue": ("United States", "US", 40.4237, -86.9212),
    "university of texas": ("United States", "US", 30.2849, -97.7341),
    "ut austin": ("United States", "US", 30.2849, -97.7341),
    "university of wisconsin": ("United States", "US", 43.0766, -89.4125),
    "university of chicago": ("United States", "US", 41.7886, -87.5987),
    "arizona state": ("United States", "US", 33.4242, -111.9281),
    "university of florida": ("United States", "US", 29.6436, -82.3549),
    "virginia tech": ("United States", "US", 37.2296, -80.4139),
    "rice university": ("United States", "US", 29.7174, -95.4018),
    "university of rochester": ("United States", "US", 43.1289, -77.6292),
    "northeastern university": ("United States", "US", 42.3398, -71.0892),
    "university of southern california": ("United States", "US", 34.0224, -118.2851),
    "usc": ("United States", "US", 34.0224, -118.2851),
    "stony brook": ("United States", "US", 40.9126, -73.1234),
    "rutgers": ("United States", "US", 40.5008, -74.4474),
    "ohio state": ("United States", "US", 40.0066, -83.0305),
    "penn state": ("United States", "US", 40.7982, -77.8599),
    # --- United Kingdom ---
    "oxford": ("United Kingdom", "GB", 51.7520, -1.2577),
    "cambridge": ("United Kingdom", "GB", 52.2043, 0.1149),
    "imperial college": ("United Kingdom", "GB", 51.4988, -0.1749),
    "ucl": ("United Kingdom", "GB", 51.5246, -0.1340),
    "university college london": ("United Kingdom", "GB", 51.5246, -0.1340),
    "edinburgh": ("United Kingdom", "GB", 55.9445, -3.1892),
    "university of manchester": ("United Kingdom", "GB", 53.4668, -2.2339),
    "university of bristol": ("United Kingdom", "GB", 51.4584, -2.6030),
    "university of surrey": ("United Kingdom", "GB", 51.2430, -0.5880),
    "university of nottingham": ("United Kingdom", "GB", 52.9388, -1.1966),
    "queen mary": ("United Kingdom", "GB", 51.5242, -0.0399),
    # --- Switzerland ---
    "eth zurich": ("Switzerland", "CH", 47.3763, 8.5480),
    "epfl": ("Switzerland", "CH", 46.5191, 6.5668),
    # --- China ---
    "tsinghua": ("China", "CN", 39.9998, 116.3266),
    "peking university": ("China", "CN", 39.9869, 116.3059),
    "beida": ("China", "CN", 39.9869, 116.3059),
    "zhejiang university": ("China", "CN", 30.2636, 120.1217),
    "fudan": ("China", "CN", 31.2984, 121.5018),
    "sjtu": ("China", "CN", 31.0285, 121.4325),
    "shanghai jiao tong": ("China", "CN", 31.0285, 121.4325),
    "nanjing university": ("China", "CN", 32.0588, 118.7965),
    "ustc": ("China", "CN", 31.8226, 117.2794),
    "university of science and technology of china": ("China", "CN", 31.8226, 117.2794),
    "chinese academy": ("China", "CN", 39.9775, 116.3267),
    "institute of automation": ("China", "CN", 39.9775, 116.3267),
    "institute of computing": ("China", "CN", 39.9775, 116.3267),
    "wuhan university": ("China", "CN", 30.5378, 114.3591),
    "beihang": ("China", "CN", 39.9823, 116.3475),
    "harbin institute": ("China", "CN", 45.7506, 126.6528),
    "southeast university": ("China", "CN", 32.0584, 118.7965),
    "sun yat-sen": ("China", "CN", 23.0955, 113.3606),
    "xiamen university": ("China", "CN", 24.4380, 118.1002),
    "huazhong": ("China", "CN", 30.5130, 114.4130),
    "beijing university of posts": ("China", "CN", 39.9629, 116.3544),
    "bupt": ("China", "CN", 39.9629, 116.3544),
    "dalian university": ("China", "CN", 38.8760, 121.5264),
    "tianjin university": ("China", "CN", 39.1088, 117.1665),
    "renmin university": ("China", "CN", 39.9696, 116.3132),
    "shandong university": ("China", "CN", 36.6700, 116.9847),
    "northwestern polytechnical": ("China", "CN", 34.2467, 108.9167),
    "south china university": ("China", "CN", 23.1560, 113.2870),
    "baidu": ("China", "CN", 40.0565, 116.3076),
    "tencent": ("China", "CN", 22.5431, 114.0579),
    "alibaba": ("China", "CN", 30.2741, 120.1551),
    "bytedance": ("China", "CN", 39.9837, 116.3076),
    "huawei": ("China", "CN", 22.6508, 114.0596),
    "sensetime": ("China", "CN", 31.2304, 121.4737),
    "megvii": ("China", "CN", 39.9837, 116.3076),
    "deepglint": ("China", "CN", 39.9837, 116.3076),
    "insightface": ("China", "CN", 39.9042, 116.4074),
    "jd.com": ("China", "CN", 39.9042, 116.4074),
    "didi": ("China", "CN", 39.9042, 116.4074),
    "xiaomi": ("China", "CN", 39.9042, 116.4074),
    "xidian": ("China", "CN", 34.1294, 108.8383),
    "cuhk": ("China", "CN", 22.4196, 114.2068),
    "chinese university of hong kong": ("China", "CN", 22.4196, 114.2068),
    "hku": ("China", "CN", 22.2830, 114.1370),
    "university of hong kong": ("China", "CN", 22.2830, 114.1370),
    "city university of hong kong": ("China", "CN", 22.3372, 114.1735),
    "hong kong polytechnic": ("China", "CN", 22.3036, 114.1795),
    # --- Singapore ---
    "nus": ("Singapore", "SG", 1.2966, 103.7764),
    "national university of singapore": ("Singapore", "SG", 1.2966, 103.7764),
    "ntu singapore": ("Singapore", "SG", 1.3483, 103.6831),
    "nanyang technological": ("Singapore", "SG", 1.3483, 103.6831),
    # --- South Korea ---
    "kaist": ("South Korea", "KR", 36.3721, 127.3604),
    "seoul national": ("South Korea", "KR", 37.4602, 126.9520),
    "yonsei": ("South Korea", "KR", 37.5665, 126.9381),
    "korea university": ("South Korea", "KR", 37.5894, 127.0323),
    "postech": ("South Korea", "KR", 36.0104, 129.3221),
    "sungkyunkwan": ("South Korea", "KR", 37.2940, 126.9754),
    "samsung": ("South Korea", "KR", 37.4563, 127.0426),
    # --- Japan ---
    "university of tokyo": ("Japan", "JP", 35.7126, 139.7620),
    "kyoto university": ("Japan", "JP", 35.0269, 135.7811),
    "osaka university": ("Japan", "JP", 34.8215, 135.5231),
    "riken": ("Japan", "JP", 35.7680, 139.6078),
    # --- Germany ---
    "max planck": ("Germany", "DE", 48.2578, 11.6706),
    "rwth aachen": ("Germany", "DE", 50.7808, 6.0787),
    "tu munich": ("Germany", "DE", 48.1497, 11.5679),
    "technical university of munich": ("Germany", "DE", 48.1497, 11.5679),
    "university of bonn": ("Germany", "DE", 50.7274, 7.0869),
    "heidelberg": ("Germany", "DE", 49.3988, 8.6724),
    "university of freiburg": ("Germany", "DE", 47.9941, 7.8461),
    # --- France ---
    "inria": ("France", "FR", 48.8419, 2.3519),
    "sorbonne": ("France", "FR", 48.8462, 2.3464),
    "ecole polytechnique": ("France", "FR", 48.7147, 2.2118),
    "université paris": ("France", "FR", 48.8462, 2.3464),
    # --- Israel ---
    "technion": ("Israel", "IL", 32.7770, 35.0238),
    "tel aviv": ("Israel", "IL", 32.1133, 34.8044),
    "weizmann": ("Israel", "IL", 31.9064, 34.8100),
    "hebrew university": ("Israel", "IL", 31.7944, 35.2449),
    # --- Canada ---
    "university of toronto": ("Canada", "CA", 43.6629, -79.3957),
    "university of waterloo": ("Canada", "CA", 43.4723, -80.5449),
    "mcgill": ("Canada", "CA", 45.5048, -73.5772),
    "university of british columbia": ("Canada", "CA", 49.2606, -123.2460),
    "university of alberta": ("Canada", "CA", 53.5232, -113.5263),
    "university of montreal": ("Canada", "CA", 45.5038, -73.6147),
    "mila": ("Canada", "CA", 45.5306, -73.6138),
    # --- Australia ---
    "university of sydney": ("Australia", "AU", -33.8889, 151.1894),
    "monash": ("Australia", "AU", -37.7840, 144.9587),
    "anu": ("Australia", "AU", -35.2777, 149.1185),
    "university of melbourne": ("Australia", "AU", -37.7983, 144.9610),
    "university of queensland": ("Australia", "AU", -27.4975, 153.0137),
    "university of adelaide": ("Australia", "AU", -34.9213, 138.6005),
    # --- India ---
    "iit": ("India", "IN", 19.1334, 72.9133),
    "iiit": ("India", "IN", 17.4455, 78.3489),
    "iisc": ("India", "IN", 13.0219, 77.5671),
    "indian institute": ("India", "IN", 19.1334, 72.9133),
    # --- Netherlands ---
    "university of amsterdam": ("Netherlands", "NL", 52.3559, 4.9554),
    "tu delft": ("Netherlands", "NL", 52.0021, 4.3736),
    # --- Sweden ---
    "kth": ("Sweden", "SE", 59.3500, 18.0700),
    # --- Finland ---
    "aalto": ("Finland", "FI", 60.1841, 24.8301),
    # --- Italy ---
    "sapienza": ("Italy", "IT", 41.9016, 12.5132),
    "politecnico di milano": ("Italy", "IT", 45.4787, 9.2278),
    "university of trento": ("Italy", "IT", 46.0643, 11.1207),
    # --- Spain ---
    "universitat de barcelona": ("Spain", "ES", 41.3861, 2.1650),
    "universidad": ("Spain", "ES", 40.4168, -3.7038),
    # --- Brazil ---
    "university of são paulo": ("Brazil", "BR", -23.5505, -46.6333),
    "universidade": ("Brazil", "BR", -23.5505, -46.6333),
    # --- UAE ---
    "mbzuai": ("United Arab Emirates", "AE", 24.4367, 54.6150),
    "khalifa university": ("United Arab Emirates", "AE", 24.4539, 54.3773),
    # --- Saudi Arabia ---
    "kaust": ("Saudi Arabia", "SA", 22.3095, 39.1028),
    "king abdullah": ("Saudi Arabia", "SA", 22.3095, 39.1028),
    # --- Russia ---
    "skoltech": ("Russia", "RU", 55.6981, 37.3596),
    # --- Poland ---
    "university of warsaw": ("Poland", "PL", 52.2297, 21.0122),
    # --- Luxembourg ---
    "university of luxembourg": ("Luxembourg", "LU", 49.5041, 6.0210),
    # --- Austria ---
    "tu wien": ("Austria", "AT", 48.1990, 16.3698),
    "vienna": ("Austria", "AT", 48.2082, 16.3738),
}


def clean_affiliation(raw: str) -> str:
    cleaned = raw.strip()
    lower = cleaned.lower()
    for prefix in AFFILIATION_PREFIXES:
        if lower.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    return cleaned.strip()


def _is_known(affiliation: str) -> bool:
    lower = affiliation.lower()
    return any(key in lower for key in KNOWN_AFFILIATIONS)


def _geocode_one(affiliation: str, geolocator):
    lower = affiliation.lower()
    for key, val in KNOWN_AFFILIATIONS.items():
        if key in lower:
            return val
    try:
        loc = geolocator.geocode(affiliation, language="en", addressdetails=True)
        if loc:
            addr = loc.raw.get("address", {})
            return (addr.get("country", "Unknown"),
                    addr.get("country_code", "XX").upper(),
                    loc.latitude, loc.longitude)
    except Exception:
        pass
    parts = [p.strip() for p in affiliation.split(",")]
    if len(parts) > 1:
        try:
            loc = geolocator.geocode(parts[-1], language="en", addressdetails=True)
            if loc:
                addr = loc.raw.get("address", {})
                return (addr.get("country", "Unknown"),
                        addr.get("country_code", "XX").upper(),
                        loc.latitude, loc.longitude)
        except Exception:
            pass
    return None


def step4_geocode_and_aggregate(authors: list, json_path: str):
    """Geocode affiliations and aggregate by country into JSON."""
    print(f"\n[4/4] Geocoding {len(authors)} affiliations ...")
    geolocator = Nominatim(user_agent="citation_map_gen_s2_v1", timeout=10)
    geo_cache = {}

    countries = {}
    institution_set = set()
    iso_map = _build_iso_map()
    geocoded_count = 0

    for entry in tqdm(authors, desc="Geocoding"):
        aff = clean_affiliation(entry["affiliation"])
        if not aff:
            continue

        if aff not in geo_cache:
            geo_cache[aff] = _geocode_one(aff, geolocator)
            if not _is_known(aff):
                time.sleep(1.1)  # Nominatim rate limit

        geo = geo_cache[aff]
        if not geo:
            continue

        geocoded_count += 1
        country_name, code, lat, lng = geo

        if code == "XX" and country_name.lower() in iso_map:
            code = iso_map[country_name.lower()]

        if code not in countries:
            countries[code] = {"name": country_name, "count": 0, "institutions": {}}
        c = countries[code]
        c["count"] += 1
        if aff not in c["institutions"]:
            c["institutions"][aff] = {"count": 0, "lat": lat, "lng": lng}
        c["institutions"][aff]["count"] += 1
        institution_set.add(aff)

    # Build output
    result = {}
    for code, cdata in countries.items():
        insts = sorted(
            [{"name": n, "count": d["count"],
              "lat": round(d["lat"], 4), "lng": round(d["lng"], 4)}
             for n, d in cdata["institutions"].items()],
            key=lambda x: x["count"], reverse=True
        )
        result[code] = {"name": cdata["name"], "count": cdata["count"],
                        "institutions": insts}

    total = sum(c["count"] for c in result.values())
    output = {
        "scholar_id": GS_SCHOLAR_ID,
        "s2_author_id": S2_AUTHOR_ID,
        "total_citations": total,
        "total_countries": len(result),
        "total_institutions": len(institution_set),
        "countries": result,
    }

    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  Geocoded: {geocoded_count}/{len(authors)}")
    print(f"  JSON: {json_path}")
    print(f"    {total} citing authors from {len(result)} countries, "
          f"{len(institution_set)} institutions")

    # Print country summary
    sorted_countries = sorted(result.items(), key=lambda x: x[1]["count"], reverse=True)
    print(f"\n  Top countries:")
    for code, cdata in sorted_countries[:15]:
        print(f"    {code} {cdata['name']:30s} {cdata['count']:4d} authors")


def _build_iso_map():
    try:
        import pycountry
        m = {}
        for c in pycountry.countries:
            m[c.name.lower()] = c.alpha_2
            if hasattr(c, "common_name"):
                m[c.common_name.lower()] = c.alpha_2
            if hasattr(c, "official_name"):
                m[c.official_name.lower()] = c.alpha_2
        m.update({"usa": "US", "uk": "GB", "south korea": "KR",
                  "russia": "RU", "iran": "IR", "taiwan": "TW",
                  "hong kong": "HK", "macau": "MO"})
        return m
    except ImportError:
        return {"united states": "US", "china": "CN", "japan": "JP",
                "germany": "DE", "france": "FR", "united kingdom": "GB"}


def main():
    print("=" * 60)
    print("  Citation Map — Semantic Scholar Scraper v1")
    print("  (S2 API: citations + batch author lookup)")
    print("=" * 60)
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

    papers = step1_get_papers()
    author_ids = step2_collect_citing_authors(papers)
    authors = step3_lookup_affiliations(author_ids)
    step4_geocode_and_aggregate(authors, OUTPUT_JSON)

    print("\n" + "=" * 60)
    print("  Done! Push data/citation_data.json to deploy.")
    print(f"  Cache: {CACHE_DIR} (delete to re-scrape)")
    print("=" * 60)


if __name__ == "__main__":
    main()
