#!/usr/bin/env python3
"""
Generate citation_data.json for the static Citation World Map.

Hybrid strategy: S2 for paper/citation discovery, OpenAlex for author affiliations.

Pipeline:
  1. S2 /author/{id}/papers          -> get all papers with citation counts
  2. OpenAlex /works?search={title}   -> map S2 papers to OpenAlex work IDs
  3. OpenAlex /works?filter=cites:{id}-> get all citing works with author+institution
  4. Deduplicate authors, geocode institutions -> aggregate by country -> JSON

Why hybrid:
  - S2 has accurate citation counts and paper discovery
  - OpenAlex has ~80% author-institution coverage (vs S2's ~3%)
  - Both are free, no auth required, generous rate limits

Rate-limiting:
  - S2: ~1 req/sec (unauthenticated)
  - OpenAlex: ~10 req/sec (polite pool with email)
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
OA_API_BASE = "https://api.openalex.org"
OA_EMAIL = "anxiangsir@gmail.com"  # For OpenAlex polite pool (10 req/s)

S2_DELAY = 1.2  # seconds between S2 API calls
S2_BACKOFF = 30  # seconds to wait on S2 429
OA_DELAY = 0.15  # seconds between OpenAlex calls (polite pool)
OA_PER_PAGE = 200  # max items per OpenAlex page

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
        except requests.exceptions.HTTPError:
            if resp.status_code == 429:
                time.sleep(S2_BACKOFF * (attempt + 1))
                continue
            raise
        except Exception as e:
            print(f"    [ERR] {type(e).__name__}: {e}")
            time.sleep(5)
    return None


def oa_get(url, params=None, timeout=30):
    """GET request to OpenAlex API with retry handling."""
    if params is None:
        params = {}
    params["mailto"] = OA_EMAIL  # Polite pool

    for attempt in range(5):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"    [OA 429] Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError:
            if resp.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            print(f"    [OA {resp.status_code}] {resp.text[:200]}")
            return None
        except Exception as e:
            print(f"    [OA ERR] {type(e).__name__}: {e}")
            time.sleep(3 * (attempt + 1))
    return None


# ─── Step 1: Get all papers from S2 ─────────────────────────────────

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


# ─── Step 2: Map S2 papers to OpenAlex work IDs ─────────────────────

def step2_map_to_openalex(papers: list) -> list:
    """Map S2 papers to OpenAlex work IDs by title search."""
    cached = load_cache("oa_paper_map")
    if cached and len(cached) >= len([p for p in papers if p.get("citationCount", 0) > 0]):
        print(f"  Loaded {len(cached)} cached OA mappings")
        return cached

    print(f"\n[2/4] Mapping papers to OpenAlex ...")
    mappings = cached or []
    mapped_titles = {m["title"] for m in mappings}

    for i, p in enumerate(papers):
        title = p["title"]
        s2_cites = p.get("citationCount", 0)
        if s2_cites == 0 or title in mapped_titles:
            continue

        time.sleep(OA_DELAY)
        resp = oa_get(f"{OA_API_BASE}/works", params={
            "search": title,
            "per_page": 1,
            "select": "id,title,cited_by_count",
        })

        if resp and resp.get("results"):
            w = resp["results"][0]
            oa_title = w.get("title", "")
            oa_id = w["id"].replace("https://openalex.org/", "")
            oa_cites = w.get("cited_by_count", 0)

            # Validate: OA citation count should be in a reasonable range
            # If OA has 10x more cites than S2, it's likely a wrong match
            if oa_cites > s2_cites * 10 and s2_cites > 0:
                print(f"  [SKIP] S2:{s2_cites:4d} OA:{oa_cites:4d} (likely wrong match) | {title[:55]}")
                print(f"         OA title: {oa_title[:70]}")
            else:
                mappings.append({
                    "title": title,
                    "s2_paper_id": p["paperId"],
                    "s2_cites": s2_cites,
                    "oa_id": oa_id,
                    "oa_cites": oa_cites,
                })
                print(f"  [{len(mappings)}] S2:{s2_cites:4d} OA:{oa_cites:4d} | {title[:65]}")
        else:
            print(f"  [MISS] S2:{s2_cites:4d} | {title[:65]}")

        save_cache("oa_paper_map", mappings)

    print(f"\n  Mapped {len(mappings)} papers to OpenAlex")
    total_oa_cites = sum(m["oa_cites"] for m in mappings)
    print(f"  Total OpenAlex citations: {total_oa_cites}")
    return mappings


# ─── Step 3: Collect citing authors + institutions from OpenAlex ─────

def step3_collect_citing_authors(mappings: list) -> list:
    """
    For each paper, paginate through OpenAlex citing works to collect
    all authors with their institutions. Deduplicate by (author_name, institution).
    """
    progress = load_cache("oa_citing_progress") or {
        "completed_papers": set(),
        "authors": {},  # key: (name_lower, institution_lower) -> {name, institution, country_code, country_name}
    }
    completed = progress["completed_papers"]
    all_authors = progress["authors"]

    remaining = [m for m in mappings if m["oa_id"] not in completed and m["oa_cites"] > 0]

    if not remaining:
        print(f"  All papers processed. {len(all_authors)} unique author-institution pairs.")
        return list(all_authors.values())

    print(f"\n[3/4] Collecting citing authors from OpenAlex ({len(remaining)} papers remaining) ...")

    for i, m in enumerate(remaining):
        oa_id = m["oa_id"]
        title = m["title"][:55]
        oa_cites = m["oa_cites"]
        paper_count = 0
        paper_authors = 0
        cursor = "*"

        while cursor:
            time.sleep(OA_DELAY)
            resp = oa_get(f"{OA_API_BASE}/works", params={
                "filter": f"cites:{oa_id}",
                "per_page": OA_PER_PAGE,
                "select": "authorships",
                "cursor": cursor,
            })

            if not resp:
                break

            for work in resp.get("results", []):
                paper_count += 1
                for authorship in work.get("authorships", []):
                    author = authorship.get("author", {})
                    author_name = author.get("display_name", "").strip()
                    if not author_name:
                        continue

                    # Get institution info
                    institutions = authorship.get("institutions", [])
                    if institutions:
                        inst = institutions[0]  # Primary institution
                        if inst is None:
                            inst_name = ""
                            country_code = ""
                        else:
                            inst_name = (inst.get("display_name") or "").strip()
                            country_code = (inst.get("country_code") or "")
                        # OpenAlex has ROR-linked country codes (ISO 3166-1 alpha-2)
                    else:
                        inst_name = ""
                        country_code = ""

                    # Also grab raw_affiliation_strings as fallback
                    raw_aff = authorship.get("raw_affiliation_strings", [])
                    raw_aff_str = raw_aff[0] if raw_aff else ""

                    if not inst_name and not raw_aff_str:
                        continue  # No affiliation at all, skip

                    key = (author_name.lower(), (inst_name or raw_aff_str).lower())
                    if key not in all_authors:
                        all_authors[key] = {
                            "author_name": author_name,
                            "institution": inst_name,
                            "country_code": country_code,
                            "raw_affiliation": raw_aff_str,
                        }
                        paper_authors += 1

            cursor = resp.get("meta", {}).get("next_cursor")

        completed.add(oa_id)
        save_cache("oa_citing_progress", progress)
        print(f"  [{i+1}/{len(remaining)}] {title} ({oa_cites} cites, "
              f"{paper_count} works) -> +{paper_authors} new (total: {len(all_authors)})")

    print(f"\n  Total unique author-institution pairs: {len(all_authors)}")

    # Count coverage
    with_country = sum(1 for a in all_authors.values() if a.get("country_code"))
    with_inst = sum(1 for a in all_authors.values() if a.get("institution"))
    print(f"  With OA country code: {with_country} ({100*with_country/max(len(all_authors),1):.1f}%)")
    print(f"  With institution name: {with_inst} ({100*with_inst/max(len(all_authors),1):.1f}%)")

    return list(all_authors.values())


# ─── Step 3b: S2 citations → OpenAlex affiliation lookup ──────────

def step3b_s2_citations_to_openalex(papers: list, existing_authors: list) -> list:
    """
    Use S2's citation API to discover ALL citing papers (not just those in OA's index).
    Then look up each citing paper on OpenAlex by DOI/title to get author affiliations.
    Merges with existing authors from step3 (deduplicates by author+institution).
    """
    progress = load_cache("s2_citing_oa_progress") or {
        "completed_papers": set(),
        "authors": {},
    }
    completed = progress["completed_papers"]
    all_authors = progress["authors"]

    # Seed with existing authors from step3 (for dedup)
    if not all_authors:
        for a in existing_authors:
            key = (a["author_name"].lower(), (a["institution"] or a.get("raw_affiliation", "")).lower())
            if key not in all_authors:
                all_authors[key] = a
        progress["authors"] = all_authors
        save_cache("s2_citing_oa_progress", progress)
        print(f"  Seeded {len(all_authors)} authors from step3")

    # Filter papers with citations that still need processing
    papers_with_cites = [p for p in papers if p.get("citationCount", 0) > 0]
    remaining = [p for p in papers_with_cites if p["paperId"] not in completed]

    if not remaining:
        print(f"  All papers processed via S2→OA. {len(all_authors)} unique author-institution pairs.")
        return list(all_authors.values())

    print(f"\n[3b/4] S2 citations → OpenAlex affiliations ({len(remaining)} papers remaining) ...")

    for pi, paper in enumerate(remaining):
        paper_id = paper["paperId"]
        title = paper["title"][:55]
        s2_cites = paper.get("citationCount", 0)
        new_authors = 0
        citing_papers_found = 0
        oa_lookups = 0

        # Paginate through S2 citations for this paper
        offset = 0
        while True:
            time.sleep(S2_DELAY)
            resp = s2_get(f"{S2_API_BASE}/paper/{paper_id}/citations", params={
                "fields": "paperId,externalIds,title",
                "limit": 1000,
                "offset": offset,
            })

            if not resp or not resp.get("data"):
                break

            batch = resp["data"]
            citing_papers_found += len(batch)

            # Collect DOIs and titles from citing papers
            to_lookup = []
            for item in batch:
                citing = item.get("citingPaper", {})
                if not citing:
                    continue
                ext_ids = citing.get("externalIds", {}) or {}
                doi = ext_ids.get("DOI")
                cp_title = citing.get("title", "")
                cp_id = citing.get("paperId", "")
                to_lookup.append({"doi": doi, "title": cp_title, "s2_id": cp_id})

            # Batch-lookup on OpenAlex: prefer DOI, fallback to title search
            # OpenAlex supports batch DOI filter: works?filter=doi:d1|d2|d3
            doi_batch = [item["doi"] for item in to_lookup if item["doi"]]

            # Process DOIs in chunks of 50 (OA filter limit)
            chunk_size = 50
            oa_results = {}  # doi -> work data

            for ci in range(0, len(doi_batch), chunk_size):
                chunk = doi_batch[ci:ci + chunk_size]
                doi_filter = "|".join(chunk)
                time.sleep(OA_DELAY)
                oa_lookups += 1
                resp_oa = oa_get(f"{OA_API_BASE}/works", params={
                    "filter": f"doi:{doi_filter}",
                    "per_page": 200,
                    "select": "doi,authorships",
                })
                if resp_oa:
                    for work in resp_oa.get("results", []):
                        work_doi = (work.get("doi") or "").replace("https://doi.org/", "").lower()
                        oa_results[work_doi] = work

            # Process OA results to extract authors
            for item in to_lookup:
                doi = item["doi"]
                work = None
                if doi:
                    work = oa_results.get(doi.lower())

                if not work:
                    # Try title search for papers without DOI or not found by DOI
                    cp_title = item["title"]
                    if cp_title and len(cp_title) > 10:
                        time.sleep(OA_DELAY)
                        oa_lookups += 1
                        title_resp = oa_get(f"{OA_API_BASE}/works", params={
                            "search": cp_title,
                            "per_page": 1,
                            "select": "title,authorships",
                        })
                        if title_resp and title_resp.get("results"):
                            candidate = title_resp["results"][0]
                            # Verify title similarity (avoid wrong matches)
                            cand_title = (candidate.get("title") or "").lower()
                            if cp_title.lower()[:30] in cand_title or cand_title[:30] in cp_title.lower():
                                work = candidate

                if not work:
                    continue

                for authorship in work.get("authorships", []):
                    author = authorship.get("author", {})
                    author_name = (author.get("display_name") or "").strip()
                    if not author_name:
                        continue

                    institutions = authorship.get("institutions", [])
                    if institutions:
                        inst = institutions[0]
                        if inst is None:
                            inst_name = ""
                            country_code = ""
                        else:
                            inst_name = (inst.get("display_name") or "").strip()
                            country_code = (inst.get("country_code") or "")
                    else:
                        inst_name = ""
                        country_code = ""

                    raw_aff = authorship.get("raw_affiliation_strings", [])
                    raw_aff_str = raw_aff[0] if raw_aff else ""

                    if not inst_name and not raw_aff_str:
                        continue

                    key = (author_name.lower(), (inst_name or raw_aff_str).lower())
                    if key not in all_authors:
                        all_authors[key] = {
                            "author_name": author_name,
                            "institution": inst_name,
                            "country_code": country_code,
                            "raw_affiliation": raw_aff_str,
                        }
                        new_authors += 1

            if resp.get("next") is None:
                break
            offset = resp["next"]

        completed.add(paper_id)
        save_cache("s2_citing_oa_progress", progress)
        print(f"  [{pi+1}/{len(remaining)}] {title} (S2:{s2_cites}, found:{citing_papers_found}, "
              f"OA lookups:{oa_lookups}) -> +{new_authors} new (total: {len(all_authors)})")

    print(f"\n  Total unique author-institution pairs: {len(all_authors)}")
    with_country = sum(1 for a in all_authors.values() if a.get("country_code"))
    with_inst = sum(1 for a in all_authors.values() if a.get("institution"))
    print(f"  With OA country code: {with_country} ({100*with_country/max(len(all_authors),1):.1f}%)")
    print(f"  With institution name: {with_inst} ({100*with_inst/max(len(all_authors),1):.1f}%)")

    return list(all_authors.values())

# ─── Step 4: Geocode + Aggregate ──────────────────────────────────────

# Prefix patterns to strip from affiliation strings
AFFILIATION_PREFIXES = [
    "professor at ", "associate professor at ", "assistant professor at ",
    "postdoc at ", "postdoctoral researcher at ", "phd student at ",
    "research scientist at ", "researcher at ", "engineer at ",
    "senior researcher at ", "lecturer at ", "reader at ",
    "professor, ", "associate professor, ", "assistant professor, ",
    "ph.d. student at ", "ph.d. candidate at ", "graduate student at ",
    "department of ", "school of ", "faculty of ", "lab of ",
]

# Known institution -> (country_name, country_code, lat, lng)
# Used as fallback when OpenAlex doesn't provide country_code
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
    "fraunhofer": ("Germany", "DE", 48.7433, 9.1013),
    "technical university of darmstadt": ("Germany", "DE", 49.8728, 8.6512),
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
    # --- Turkey ---
    "bogazici": ("Turkey", "TR", 41.0826, 29.0508),
    "bilkent": ("Turkey", "TR", 39.8679, 32.7491),
    # --- Czech Republic ---
    "czech technical": ("Czech Republic", "CZ", 50.1037, 14.3916),
    # --- Additional Chinese institutions (commonly mislocated) ---
    "jinan university": ("China", "CN", 23.1291, 113.3472),  # Guangzhou
    "chengdu university": ("China", "CN", 30.5728, 104.0668),
    "beijing academy of artificial intelligence": ("China", "CN", 39.9775, 116.3267),
    "beijing jiaotong": ("China", "CN", 39.9563, 116.3388),
    "sichuan university": ("China", "CN", 30.6320, 104.0828),
    "nanjing normal": ("China", "CN", 32.1019, 118.9143),
    "changchun university": ("China", "CN", 43.8879, 125.3245),
    "beijing normal": ("China", "CN", 39.9592, 116.3283),
    "peng cheng laboratory": ("China", "CN", 22.5431, 114.0579),  # Shenzhen
    "southwest jiaotong": ("China", "CN", 30.6993, 103.9867),
    "chongqing university of technology": ("China", "CN", 29.5630, 106.5516),
    "yibin university": ("China", "CN", 28.7523, 104.6306),
    "jiangnan university": ("China", "CN", 31.5098, 120.2940),  # Wuxi
    "zhejiang lab": ("China", "CN", 30.2741, 120.1551),  # Hangzhou
    "south china robotics": ("China", "CN", 23.1291, 113.3472),  # Guangzhou
    "center for excellence in brain science": ("China", "CN", 31.2304, 121.4737),  # Shanghai CAS
    "national yang ming chiao tung": ("Taiwan", "TW", 24.7867, 120.9963),  # Hsinchu
    "ministry of public security": ("China", "CN", 39.9042, 116.4074),  # Beijing
    "fujitsu": ("Japan", "JP", 35.6581, 139.7414),
    "netease": ("China", "CN", 30.2741, 120.1551),  # Hangzhou
    "national engineering research center for information technology in agriculture": ("China", "CN", 39.9629, 116.2846),  # Beijing
    "deepcam": ("China", "CN", 22.5431, 114.0579),  # Shenzhen
    "intellifusion": ("China", "CN", 22.5431, 114.0579),  # Shenzhen
    "china pacific insurance": ("China", "CN", 31.2304, 121.4737),  # Shanghai
    "southwest university of science and technology": ("China", "CN", 31.5388, 104.6838),  # Mianyang
    "iie, cas": ("China", "CN", 39.9775, 116.3267),  # Beijing, Institute of Info Engineering
    "cair, hkisi": ("China", "CN", 22.3372, 114.1735),  # HK
    "hkisi, cas": ("China", "CN", 22.3372, 114.1735),  # HK
    "shenzhen academy of robotics": ("China", "CN", 22.5431, 114.0579),
    "academy of military medical": ("China", "CN", 39.9042, 116.4074),  # Beijing
    "taiyuan university": ("China", "CN", 37.8706, 112.5489),
    "yancheng institute of technology": ("China", "CN", 33.3476, 120.1619),
    "china university of petroleum": ("China", "CN", 36.7614, 117.0255),  # Qingdao/Dongying
    "yunnan vocational": ("China", "CN", 25.0389, 102.7183),  # Kunming
    "jiangxi normal": ("China", "CN", 28.6765, 115.8922),  # Nanchang
    "changzhou institute of technology": ("China", "CN", 31.8106, 119.9736),
    "nanjing tech university": ("China", "CN", 32.0169, 118.7857),
    "hubei university of economics": ("China", "CN", 30.5928, 114.3055),  # Wuhan
    "liaoning shihua": ("China", "CN", 41.8044, 123.4107),  # Fushun
    "gansu research institute": ("China", "CN", 36.0611, 103.8343),  # Lanzhou
    "shandong provincial key lab": ("China", "CN", 36.6700, 116.9847),  # Jinan
    "west china medical center": ("China", "CN", 30.6320, 104.0828),  # Chengdu/Sichuan
    "jilin province science": ("China", "CN", 43.8879, 125.3245),  # Changchun
    "lingnan university": ("China", "CN", 22.3372, 114.1735),  # HK
    "macau polytechnic": ("China", "CN", 22.1987, 113.5439),  # Macau
    "shanghai research center for wireless": ("China", "CN", 31.2304, 121.4737),
    "hongzhiwei": ("China", "CN", 31.2304, 121.4737),  # Shanghai
    "wanfang data": ("China", "CN", 39.9042, 116.4074),  # Beijing
    "unigroup guoxin": ("China", "CN", 39.9042, 116.4074),  # Beijing
    "jovision": ("China", "CN", 22.5431, 114.0579),  # Shenzhen
    "qiyuan lab": ("China", "CN", 39.9042, 116.4074),  # Beijing
    "unisound": ("China", "CN", 39.9042, 116.4074),  # Beijing
    "tiktok": ("China", "CN", 31.2304, 121.4737),  # Shanghai
    "momenta": ("China", "CN", 31.3005, 120.5853),  # Suzhou
    "farsee2": ("China", "CN", 30.5378, 114.3591),  # Wuhan
    "lens, inc": ("United States", "US", 37.7749, -122.4194),  # SF
    "institute of engineering": ("China", "CN", 39.9775, 116.3267),  # CAS Beijing default
    "university of alicante": ("Spain", "ES", 38.3853, -0.5131),
    "university of augsburg": ("Germany", "DE", 48.3305, 10.8958),
    "max planck institute for intelligent systems": ("Germany", "DE", 48.7433, 9.1013),  # Stuttgart
    "jeonbuk national": ("South Korea", "KR", 35.8468, 127.1294),  # Jeonju
    "vignan": ("India", "IN", 16.2333, 80.6500),  # Guntur
    "artificial intelligence in medicine": ("Canada", "CA", 43.6532, -79.3832),  # Toronto default
    "amity university": ("India", "IN", 28.5440, 77.3333),  # Noida
    "tomorrows children": ("United States", "US", 40.9176, -74.1719),  # NJ
}

# Major city coordinates for city extraction from affiliation strings
# e.g. 'XForwardAI, Beijing, China' -> extract 'Beijing' -> lookup here
CITY_COORDINATES = {
    # China
    "beijing": ("China", "CN", 39.9042, 116.4074),
    "shanghai": ("China", "CN", 31.2304, 121.4737),
    "shenzhen": ("China", "CN", 22.5431, 114.0579),
    "guangzhou": ("China", "CN", 23.1291, 113.3472),
    "hangzhou": ("China", "CN", 30.2741, 120.1551),
    "chengdu": ("China", "CN", 30.5728, 104.0668),
    "wuhan": ("China", "CN", 30.5378, 114.3591),
    "nanjing": ("China", "CN", 32.0603, 118.7969),
    "xi'an": ("China", "CN", 34.2649, 108.9403),
    "xian": ("China", "CN", 34.2649, 108.9403),
    "changsha": ("China", "CN", 28.2282, 112.9388),
    "harbin": ("China", "CN", 45.7506, 126.6528),
    "dalian": ("China", "CN", 38.8760, 121.5264),
    "tianjin": ("China", "CN", 30.9756, 117.8242),
    "suzhou": ("China", "CN", 31.3005, 120.5853),
    "hefei": ("China", "CN", 31.8206, 117.2272),
    "xiamen": ("China", "CN", 24.4798, 118.0894),
    "jinan": ("China", "CN", 36.6512, 116.9972),
    "zhengzhou": ("China", "CN", 34.7466, 113.6254),
    "kunming": ("China", "CN", 25.0389, 102.7183),
    "fuzhou": ("China", "CN", 26.0745, 119.2965),
    "changchun": ("China", "CN", 43.8879, 125.3245),
    "qingdao": ("China", "CN", 36.0671, 120.3826),
    "chongqing": ("China", "CN", 29.5630, 106.5516),
    "hong kong": ("China", "CN", 22.3193, 114.1694),
    "macau": ("China", "CN", 22.1987, 113.5439),
    "macao": ("China", "CN", 22.1987, 113.5439),
    # Japan
    "tokyo": ("Japan", "JP", 35.6762, 139.6503),
    "osaka": ("Japan", "JP", 34.6937, 135.5023),
    "kyoto": ("Japan", "JP", 35.0116, 135.7681),
    # South Korea
    "seoul": ("South Korea", "KR", 37.5665, 126.9780),
    "busan": ("South Korea", "KR", 35.1796, 129.0756),
    "daejeon": ("South Korea", "KR", 36.3504, 127.3845),
    "jeonju": ("South Korea", "KR", 35.8468, 127.1294),
    # India
    "mumbai": ("India", "IN", 19.0760, 72.8777),
    "bangalore": ("India", "IN", 12.9716, 77.5946),
    "bengaluru": ("India", "IN", 12.9716, 77.5946),
    "hyderabad": ("India", "IN", 17.3850, 78.4867),
    "new delhi": ("India", "IN", 28.6139, 77.2090),
    "delhi": ("India", "IN", 28.6139, 77.2090),
    "chennai": ("India", "IN", 13.0827, 80.2707),
    "kolkata": ("India", "IN", 22.5726, 88.3639),
    "pune": ("India", "IN", 18.5204, 73.8567),
    # US
    "san francisco": ("United States", "US", 37.7749, -122.4194),
    "new york": ("United States", "US", 40.7128, -74.0060),
    "los angeles": ("United States", "US", 34.0522, -118.2437),
    "seattle": ("United States", "US", 47.6062, -122.3321),
    "boston": ("United States", "US", 42.3601, -71.0589),
    "pittsburgh": ("United States", "US", 40.4406, -79.9959),
    # UK
    "london": ("United Kingdom", "GB", 51.5074, -0.1278),
    # Germany
    "berlin": ("Germany", "DE", 52.5200, 13.4050),
    "munich": ("Germany", "DE", 48.1351, 11.5820),
    "stuttgart": ("Germany", "DE", 48.7758, 9.1829),
    # France
    "paris": ("France", "FR", 48.8566, 2.3522),
    # Singapore
    "singapore": ("Singapore", "SG", 1.3521, 103.8198),
    # Australia
    "sydney": ("Australia", "AU", -33.8688, 151.2093),
    "melbourne": ("Australia", "AU", -37.8136, 144.9631),
    # Canada
    "toronto": ("Canada", "CA", 43.6532, -79.3832),
    "montreal": ("Canada", "CA", 45.5017, -73.5673),
    "vancouver": ("Canada", "CA", 49.2827, -123.1207),
    # Russia
    "moscow": ("Russia", "RU", 55.7558, 37.6173),
    # Other
    "zurich": ("Switzerland", "CH", 47.3769, 8.5417),
    "amsterdam": ("Netherlands", "NL", 52.3676, 4.9041),
    "stockholm": ("Sweden", "SE", 59.3293, 18.0686),
    "tel aviv": ("Israel", "IL", 32.0853, 34.7818),
}

# Country bounding boxes (lat_min, lat_max, lng_min, lng_max) for validation
# If a geocoded point falls outside the country bbox, it's likely wrong
COUNTRY_BOUNDS = {
    "CN": (17.0, 54.0, 73.0, 136.0),
    "US": (24.0, 72.0, -180.0, -65.0),
    "GB": (49.0, 61.0, -9.0, 2.0),
    "DE": (47.0, 55.5, 5.5, 15.5),
    "FR": (41.0, 51.5, -5.5, 10.0),
    "JP": (24.0, 46.0, 122.0, 154.0),
    "KR": (33.0, 39.0, 124.0, 132.0),
    "IN": (6.0, 36.0, 68.0, 98.0),
    "AU": (-44.0, -10.0, 112.0, 155.0),
    "CA": (41.0, 84.0, -141.0, -52.0),
    "BR": (-34.0, 6.0, -74.0, -34.0),
    "RU": (41.0, 82.0, 19.0, 180.0),
    "IT": (36.0, 47.5, 6.5, 19.0),
    "ES": (27.0, 44.0, -19.0, 5.0),
    "TW": (21.5, 25.5, 119.0, 122.5),
    "SG": (1.1, 1.5, 103.5, 104.1),
}

# Country centroids (lat, lng) for ISO 3166-1 alpha-2 codes.
# Used to skip Nominatim for entries that already have an OpenAlex country_code.
COUNTRY_CENTROIDS = {
    "AD": (42.5063, 1.5218), "AE": (23.4241, 53.8478), "AF": (33.9391, 67.7100),
    "AG": (17.0608, -61.7964), "AL": (41.1533, 20.1683), "AM": (40.0691, 43.9493),
    "AO": (-11.2027, 17.8739), "AR": (-38.4161, -63.6167), "AT": (47.5162, 14.5501),
    "AU": (-25.2744, 133.7751), "AZ": (40.1431, 47.5769), "BA": (43.9159, 17.6791),
    "BB": (13.1939, -59.5432), "BD": (23.685, 90.3563), "BE": (50.5039, 4.4699),
    "BF": (12.2383, -1.5616), "BG": (42.7339, 25.4858), "BH": (26.0667, 50.5577),
    "BI": (-3.3731, 29.9189), "BJ": (9.3077, 2.3158), "BN": (4.5353, 114.7277),
    "BO": (-16.2902, -63.5887), "BR": (-14.235, -51.9253), "BS": (25.0343, -77.3963),
    "BT": (27.5142, 90.4336), "BW": (-22.3285, 24.6849), "BY": (53.7098, 27.9534),
    "BZ": (17.1899, -88.4976), "CA": (56.1304, -106.3468), "CD": (-4.0383, 21.7587),
    "CF": (6.6111, 20.9394), "CG": (-0.228, 15.8277), "CH": (46.8182, 8.2275),
    "CI": (7.54, -5.5471), "CL": (-35.6751, -71.543), "CM": (7.3697, 12.3547),
    "CN": (35.8617, 104.1954), "CO": (4.5709, -74.2973), "CR": (9.7489, -83.7534),
    "CU": (21.5218, -77.7812), "CV": (16.5388, -23.0418), "CY": (35.1264, 33.4299),
    "CZ": (49.8175, 15.473), "DE": (51.1657, 10.4515), "DJ": (11.8251, 42.5903),
    "DK": (56.2639, 9.5018), "DM": (15.415, -61.371), "DO": (18.7357, -70.1627),
    "DZ": (28.0339, 1.6596), "EC": (-1.8312, -78.1834), "EE": (58.5953, 25.0136),
    "EG": (26.8206, 30.8025), "ER": (15.1794, 39.7823), "ES": (40.4637, -3.7492),
    "ET": (9.145, 40.4897), "FI": (61.9241, 25.7482), "FJ": (-17.7134, 178.065),
    "FR": (46.2276, 2.2137), "GA": (-0.8037, 11.6094), "GB": (55.3781, -3.436),
    "GD": (12.1165, -61.679), "GE": (42.3154, 43.3569), "GH": (7.9465, -1.0232),
    "GM": (13.4432, -15.3101), "GN": (9.9456, -9.6966), "GQ": (1.6508, 10.2679),
    "GR": (39.0742, 21.8243), "GT": (15.7835, -90.2308), "GW": (11.8037, -15.1804),
    "GY": (4.8604, -58.9302), "HK": (22.3193, 114.1694), "HN": (15.2, -86.2419),
    "HR": (45.1, 15.2), "HT": (18.9712, -72.2852), "HU": (47.1625, 19.5033),
    "ID": (-0.7893, 113.9213), "IE": (53.1424, -7.6921), "IL": (31.0461, 34.8516),
    "IN": (20.5937, 78.9629), "IQ": (33.2232, 43.6793), "IR": (32.4279, 53.688),
    "IS": (64.9631, -19.0208), "IT": (41.8719, 12.5674), "JM": (18.1096, -77.2975),
    "JO": (30.5852, 36.2384), "JP": (36.2048, 138.2529), "KE": (-0.0236, 37.9062),
    "KG": (41.2044, 74.7661), "KH": (12.5657, 104.991), "KI": (-3.3704, -168.734),
    "KM": (-11.875, 43.8722), "KN": (17.3578, -62.783), "KP": (40.3399, 127.5101),
    "KR": (35.9078, 127.7669), "KW": (29.3117, 47.4818), "KZ": (48.0196, 66.9237),
    "LA": (19.8563, 102.4955), "LB": (33.8547, 35.8623), "LC": (13.9094, -60.9789),
    "LI": (47.166, 9.5554), "LK": (7.8731, 80.7718), "LR": (6.4281, -9.4295),
    "LS": (-29.61, 28.2336), "LT": (55.1694, 23.8813), "LU": (49.8153, 6.1296),
    "LV": (56.8796, 24.6032), "LY": (26.3351, 17.2283), "MA": (31.7917, -7.0926),
    "MC": (43.7384, 7.4246), "MD": (47.4116, 28.3699), "ME": (42.7087, 19.3744),
    "MG": (-18.7669, 46.8691), "MK": (41.5124, 20.9631), "ML": (17.5707, -3.9962),
    "MM": (21.9162, 95.956), "MN": (46.8625, 103.8467), "MO": (22.1987, 113.5439),
    "MR": (21.0079, -10.9408), "MT": (35.9375, 14.3754), "MU": (-20.3484, 57.5522),
    "MV": (3.2028, 73.2207), "MW": (-13.2543, 34.3015), "MX": (23.6345, -102.5528),
    "MY": (4.2105, 101.9758), "MZ": (-18.6657, 35.5296), "NA": (-22.9576, 18.4904),
    "NE": (17.6078, 8.0817), "NG": (9.082, 8.6753), "NI": (12.8654, -85.2072),
    "NL": (52.1326, 5.2913), "NO": (60.472, 8.4689), "NP": (28.3949, 84.124),
    "NR": (-0.5228, 166.9315), "NZ": (-40.9006, 174.886), "OM": (21.4735, 55.9754),
    "PA": (8.538, -80.7821), "PE": (-9.19, -75.0152), "PG": (-6.315, 143.9555),
    "PH": (12.8797, 121.774), "PK": (30.3753, 69.3451), "PL": (51.9194, 19.1451),
    "PR": (18.2208, -66.5901), "PS": (31.9522, 35.2332), "PT": (39.3999, -8.2245),
    "PY": (-23.4425, -58.4438), "QA": (25.3548, 51.1839), "RO": (45.9432, 24.9668),
    "RS": (44.0165, 21.0059), "RU": (61.524, 105.3188), "RW": (-1.9403, 29.8739),
    "SA": (23.8859, 45.0792), "SB": (-9.6457, 160.1562), "SC": (-4.6796, 55.492),
    "SD": (12.8628, 30.2176), "SE": (60.1282, 18.6435), "SG": (1.3521, 103.8198),
    "SI": (46.1512, 14.9955), "SK": (48.669, 19.699), "SL": (8.4606, -11.7799),
    "SM": (43.9424, 12.4578), "SN": (14.4974, -14.4524), "SO": (5.1521, 46.1996),
    "SR": (3.9193, -56.0278), "SS": (6.877, 31.307), "ST": (0.1864, 6.6131),
    "SV": (13.7942, -88.8965), "SY": (34.8021, 38.9968), "SZ": (-26.5225, 31.4659),
    "TD": (15.4542, 18.7322), "TG": (8.6195, 1.2080), "TH": (15.87, 100.9925),
    "TJ": (38.861, 71.2761), "TL": (-8.8742, 125.7275), "TM": (38.9697, 59.5563),
    "TN": (33.8869, 9.5375), "TO": (-21.179, -175.1982), "TR": (38.9637, 35.2433),
    "TT": (10.6918, -61.2225), "TV": (-7.1095, 177.6493), "TW": (23.6978, 120.9605),
    "TZ": (-6.369, 34.8888), "UA": (48.3794, 31.1656), "UG": (1.3733, 32.2903),
    "US": (37.0902, -95.7129), "UY": (-32.5228, -55.7658), "UZ": (41.3775, 64.5853),
    "VA": (41.9029, 12.4534), "VC": (12.9843, -61.2872), "VE": (6.4238, -66.5897),
    "VN": (14.0583, 108.2772), "VU": (-15.3767, 166.9592), "WS": (-13.759, -172.1046),
    "XK": (42.6026, 20.903), "YE": (15.5527, 48.5164), "ZA": (-30.5595, 22.9375),
    "ZM": (-13.1339, 28.6387), "ZW": (-19.0154, 29.1549),
}


def clean_affiliation(raw: str) -> str:
    cleaned = raw.strip()
    lower = cleaned.lower()
    for prefix in AFFILIATION_PREFIXES:
        if lower.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    return cleaned.strip()


def _geocode_one(institution: str, country_code: str, raw_aff: str, geolocator):
    """
    Geocode an institution to CITY-LEVEL coordinates. Priority:
    1. KNOWN_AFFILIATIONS dict lookup (hand-curated city-level coords)
    2. City name extraction from affiliation string (e.g. 'XForwardAI, Beijing, China')
    3. Nominatim geocoding with country-bounds validation
    4. Country centroid as last resort
    """
    iso_map = _get_iso_map()

    # Strategy 1: KNOWN_AFFILIATIONS for well-known institutions
    for text in [institution, raw_aff]:
        if not text:
            continue
        lower = text.lower()
        # Sort keys by length descending so longer (more specific) keys match first
        for key in sorted(KNOWN_AFFILIATIONS.keys(), key=len, reverse=True):
            if key in lower:
                return KNOWN_AFFILIATIONS[key]

    # Strategy 2: City extraction from comma-separated affiliation strings
    # e.g. 'XForwardAI, Beijing, China' -> extract 'Beijing' -> CITY_COORDINATES
    for text in [raw_aff, institution]:
        if not text:
            continue
        parts = [p.strip().lower() for p in text.split(',')]
        for part in parts:
            if part in CITY_COORDINATES:
                return CITY_COORDINATES[part]
            # Also try without common suffixes
            for suffix in [' china', ' japan', ' korea', ' india']:
                cleaned_part = part.replace(suffix, '').strip()
                if cleaned_part in CITY_COORDINATES:
                    return CITY_COORDINATES[cleaned_part]

    # Strategy 3: Nominatim geocoding (city-level) with bounds validation
    country_name = ""
    if country_code and len(country_code) == 2:
        country_name = _country_name(country_code) or country_code

    def _in_bounds(lat, lng, cc):
        """Check if coordinates fall within the expected country bounding box."""
        if cc not in COUNTRY_BOUNDS:
            return True  # No bounds to check, assume ok
        lat_min, lat_max, lng_min, lng_max = COUNTRY_BOUNDS[cc]
        return lat_min <= lat <= lat_max and lng_min <= lng <= lng_max

    for text in [institution, raw_aff]:
        if not text or len(text) < 3:
            continue
        query = text
        if country_name and country_name.lower() not in text.lower():
            query = f"{text}, {country_name}"
        try:
            time.sleep(1.1)  # Nominatim rate limit
            loc = geolocator.geocode(query, language='en', addressdetails=True)
            if loc:
                addr = loc.raw.get('address', {})
                cc = addr.get('country_code', 'XX').upper()
                cn = addr.get('country', country_name or 'Unknown')
                if country_code and len(country_code) == 2:
                    cc = country_code
                    cn = country_name or cn
                # Validate: coordinates should be in the right country
                if _in_bounds(loc.latitude, loc.longitude, cc):
                    return (cn, cc, loc.latitude, loc.longitude)
                # If out of bounds, skip this result (bad geocode)
        except Exception:
            pass
        # Try comma-separated parts (city, country patterns)
        parts = [p.strip() for p in text.split(',')]
        if len(parts) > 1:
            # Try second-to-last part (often city name)
            for part_idx in [-2, -1]:
                if abs(part_idx) > len(parts):
                    continue
                try:
                    time.sleep(1.1)
                    loc = geolocator.geocode(parts[part_idx], language='en', addressdetails=True)
                    if loc:
                        addr = loc.raw.get('address', {})
                        cc = country_code if (country_code and len(country_code) == 2) else addr.get('country_code', 'XX').upper()
                        cn = country_name if country_name else addr.get('country', 'Unknown')
                        if _in_bounds(loc.latitude, loc.longitude, cc):
                            return (cn, cc, loc.latitude, loc.longitude)
                except Exception:
                    pass

    # Strategy 4: Country centroid as last resort
    if country_code and len(country_code) == 2:
        if not country_name:
            country_name = _country_name(country_code) or country_code
        if country_code in COUNTRY_CENTROIDS:
            lat, lng = COUNTRY_CENTROIDS[country_code]
            return (country_name, country_code, lat, lng)
        return (country_name, country_code, 0.0, 0.0)

    return None


_iso_map_cache = None

def _get_iso_map():
    global _iso_map_cache
    if _iso_map_cache is None:
        _iso_map_cache = _build_iso_map()
    return _iso_map_cache


_country_name_cache = {}

def _country_name(code: str) -> str:
    if code in _country_name_cache:
        return _country_name_cache[code]
    try:
        import pycountry
        c = pycountry.countries.get(alpha_2=code)
        if c:
            name = getattr(c, "common_name", c.name)
            _country_name_cache[code] = name
            return name
    except Exception:
        pass
    _country_name_cache[code] = code
    return code


def step4_geocode_and_aggregate(authors: list, json_path: str):
    """Geocode affiliations and aggregate by country + build city-level markers for JSON."""
    print(f"\n[4/4] Geocoding {len(authors)} author-institution pairs ...")
    geolocator = Nominatim(user_agent="citation_map_gen_oa_v2", timeout=10)
    geo_cache = load_cache("oa_geocode_cache") or {}
    save_interval = 50

    countries = {}
    institution_set = set()
    geocoded_count = 0

    for idx, entry in enumerate(tqdm(authors, desc="Geocoding")):
        institution = entry.get("institution", "")
        country_code = entry.get("country_code", "")
        raw_aff = entry.get("raw_affiliation", "")
        aff_display = institution or clean_affiliation(raw_aff)

        if not aff_display:
            continue

        cache_key = f"{aff_display}|{country_code}"
        if cache_key not in geo_cache:
            geo_cache[cache_key] = _geocode_one(institution, country_code, raw_aff, geolocator)

            if (idx + 1) % save_interval == 0:
                save_cache("oa_geocode_cache", geo_cache)

        geo = geo_cache[cache_key]
        if not geo:
            continue

        geocoded_count += 1
        country_name, code, lat, lng = geo

        if code == "XX":
            iso_map = _get_iso_map()
            if country_name.lower() in iso_map:
                code = iso_map[country_name.lower()]

        if code not in countries:
            countries[code] = {"name": country_name, "count": 0, "institutions": {}}
        c = countries[code]
        c["count"] += 1
        if aff_display not in c["institutions"]:
            c["institutions"][aff_display] = {"count": 0, "lat": lat, "lng": lng}
        c["institutions"][aff_display]["count"] += 1
        institution_set.add(aff_display)

    # Save final geocode cache
    save_cache("oa_geocode_cache", geo_cache)

    # Build country-level output
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

    # Build flat markers array for city-level bubble map
    # Group by (lat, lng) rounded to 2 decimals to cluster nearby institutions
    from collections import defaultdict
    coord_groups = defaultdict(lambda: {"count": 0, "institutions": [], "country": "", "cc": ""})
    for code, cdata in countries.items():
        for inst_name, inst_data in cdata["institutions"].items():
            lat_r = round(inst_data["lat"], 2)
            lng_r = round(inst_data["lng"], 2)
            key = (lat_r, lng_r)
            g = coord_groups[key]
            g["count"] += inst_data["count"]
            g["institutions"].append({"name": inst_name, "count": inst_data["count"]})
            if not g["country"]:
                g["country"] = cdata["name"]
                g["cc"] = code

    markers = []
    for (lat, lng), g in coord_groups.items():
        top_insts = sorted(g["institutions"], key=lambda x: x["count"], reverse=True)[:5]
        markers.append({
            "lat": lat, "lng": lng,
            "count": g["count"],
            "country": g["country"],
            "cc": g["cc"],
            "institutions": top_insts,
        })
    markers.sort(key=lambda x: x["count"], reverse=True)

    total = sum(c["count"] for c in result.values())
    output = {
        "scholar_id": GS_SCHOLAR_ID,
        "s2_author_id": S2_AUTHOR_ID,
        "total_citations": total,
        "total_countries": len(result),
        "total_institutions": len(institution_set),
        "countries": result,
        "markers": markers,
    }

    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  Geocoded: {geocoded_count}/{len(authors)}")
    print(f"  JSON: {json_path}")
    print(f"    {total} citing authors from {len(result)} countries, "
          f"{len(institution_set)} institutions, {len(markers)} city markers")

    # Print country summary
    sorted_countries = sorted(result.items(), key=lambda x: x[1]["count"], reverse=True)
    print(f"\n  Top countries:")
    for code, cdata in sorted_countries[:20]:
        print(f"    {code} {cdata['name']:30s} {cdata['count']:4d} authors")

    # Print top markers
    print(f"\n  Top city markers:")
    for m in markers[:15]:
        inst_str = ', '.join(i['name'][:30] for i in m['institutions'][:2])
        print(f"    ({m['lat']:7.2f}, {m['lng']:8.2f}) {m['count']:4d} authors  [{m['country']}] {inst_str}")

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
    import sys
    step4_only = "--step4-only" in sys.argv

    print("=" * 60)
    print("  Citation Map — S2 + OpenAlex Hybrid Scraper v2")
    print("  (S2: paper discovery | OpenAlex: author affiliations)")
    if step4_only:
        print("  MODE: Step 4 only (re-geocode from cached authors)")
    print("=" * 60)
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

    if step4_only:
        # Load cached authors from step3b progress
        progress = load_cache("s2_citing_oa_progress")
        if progress and progress.get("authors"):
            authors = list(progress["authors"].values())
            print(f"  Loaded {len(authors)} cached authors from step3b")
        else:
            # Fallback to step3 only
            progress3 = load_cache("oa_citing_progress")
            if isinstance(progress3, dict):
                authors = list(progress3.values())
            elif isinstance(progress3, list):
                authors = progress3
            else:
                print("  ERROR: No cached author data found. Run full pipeline first.")
                return
            print(f"  Loaded {len(authors)} cached authors from step3")
    else:
        papers = step1_get_papers()
        mappings = step2_map_to_openalex(papers)
        authors = step3_collect_citing_authors(mappings)
        # Step 3b: Use S2 citation graph to find papers OA missed
        authors = step3b_s2_citations_to_openalex(papers, authors)

    step4_geocode_and_aggregate(authors, OUTPUT_JSON)

    print("\n" + "=" * 60)
    print("  Done! Push data/citation_data.json to deploy.")
    print(f"  Cache: {CACHE_DIR} (delete to re-scrape)")
    print("=" * 60)


if __name__ == "__main__":
    main()
