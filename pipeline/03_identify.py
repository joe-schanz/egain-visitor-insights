"""Step 3 — Identify the organisation behind each IP.

Two free sources, cheapest first:
  1. IPinfo Lite database (local .mmdb, free, unlimited): who owns the IP's network (ASN) for EVERY IP.
     If the network owner is the visitor's own organisation (JPMorgan, IRS, a university ...) we are done.
  2. RDAP (the modern WHOIS, free, rate-limited): for IPs on ISP / unrecognised networks, the regional
     registry often records which *customer* an ISP assigned the block to
     (e.g. a Verizon Business block registered to "GuideStone Financial Resources").
     Results are cached on disk, and one lookup covers every IP inside the returned range.

Inputs : data/interim/hits_classified.parquet, data/reference/ipinfo_lite.mmdb
Outputs: data/interim/ip_identity.parquet, data/reference/rdap_cache.json (cache, git-ignored)

Usage  : python pipeline/03_identify.py [--rdap-budget N]   (default 3000 RDAP lookups, ~1/sec)
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import maxminddb
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from networks import PROVIDER_WORDS, classify_asn  # noqa: E402

# A registrant that owns many visitor IPs which each load a single page is renting out IPs
# (residential proxy farm), not a company browsing the site.
FARM_MIN_IPS = 5
FARM_MAX_HITS_PER_VISIT = 1.1

ROOT = Path(__file__).resolve().parents[1]
INTERIM, REF = ROOT / "data" / "interim", ROOT / "data" / "reference"
CACHE = REF / "rdap_cache.json"
RDAP_URL = "https://rdap.org/ip/{}"
UA = "visitor-insights-prototype (research)"
NOISE = {"opt_out", "legal", "investor", "careers", "feed", "asset", "probe"}


# ---------------- RDAP ----------------
def rdap_fetch(ip: str) -> dict | None:
    req = urllib.request.Request(RDAP_URL.format(ip), headers={"Accept": "application/rdap+json", "User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:            # rate limited: back off and retry
                time.sleep(15 * (attempt + 1))
                continue
            if e.code == 404:
                return {}
            return None
        except Exception:
            time.sleep(3)
    return None


def _vcard_fn(entity: dict) -> str:
    v = (entity.get("vcardArray") or [None, []])[1]
    fn = [x[3] for x in v if x and x[0] == "fn"]
    return fn[0] if fn else ""


def rdap_summary(d: dict) -> dict:
    """Keep only what we need: block range, network name, and the registrant organisation."""
    if not d:
        return {}
    registrant = ""
    for e in d.get("entities", []):
        if "registrant" in e.get("roles", []):
            registrant = _vcard_fn(e) or e.get("handle", "")
            break
    return {
        "start": d.get("startAddress", ""), "end": d.get("endAddress", ""),
        "net_name": d.get("name", ""), "registrant": registrant,
        "remarks": " ".join(" ".join(r.get("description", [])) for r in d.get("remarks", []))[:300],
    }


def assigned_customer(summary: dict, as_name: str) -> str:
    """Return the customer organisation an ISP block is assigned to, or '' if it's the ISP itself."""
    reg = (summary.get("registrant") or "").strip()
    if not reg or PROVIDER_WORDS.search(reg):
        return ""
    # registrant is just the upstream provider under another spelling
    first = re.sub(r"[^a-z]", "", as_name.lower().split(" ")[0]) if as_name else ""
    if first and first[:5] in re.sub(r"[^a-z]", "", reg.lower()):
        return ""
    # registry handles / maintainer objects ("CC04", "KabelBW-MNT", "GDC-TR-CoreIP") are not company names
    if " " not in reg and (re.search(r"[-_0-9]", reg) or reg.isupper()):
        return ""
    if re.search(r"-mnt\b|maintainer|\bnoc\b|abuse", reg, re.I):
        return ""
    return reg


RESIDENTIAL_POOL = re.compile(r"cpe|resid|dynamic|dsl|pool|broadband|mobile|cable|fttx|ftth|gprs|lte|pppoe", re.I)


def reusable(s: dict) -> bool:
    """Can this block's answer be reused for other IPs inside it without a new lookup?
    Small blocks (<= 4,096 addresses) and residential pools: yes. Large business blocks: no, because the
    ISP may have sub-assigned a smaller piece to a named customer, which only a lookup of that IP reveals."""
    try:
        size = int(ipaddress.ip_address(s["end"])) - int(ipaddress.ip_address(s["start"])) + 1
    except Exception:
        return False
    return size <= 4096 or (size <= 2 ** 24 and bool(RESIDENTIAL_POOL.search(s.get("net_name", ""))))


class RangeIndex:
    """Find whether an IP falls in a block we already looked up (one lookup covers the whole block)."""

    def __init__(self, cache: dict):
        self.ranges = []
        for s in cache.values():
            self.add(s)

    def add(self, s: dict):
        if not s or not reusable(s):
            return
        self.ranges.append((int(ipaddress.ip_address(s["start"])), int(ipaddress.ip_address(s["end"])), s))

    def find(self, ip: str):
        n = int(ipaddress.ip_address(ip))
        best = None
        for lo, hi, s in self.ranges:
            if lo <= n <= hi and (best is None or hi - lo < best[1] - best[0]):
                best = (lo, hi, s)
        return best[2] if best else None


# ---------------- main ----------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rdap-budget", type=int, default=3000)
    args = ap.parse_args()

    hits = pd.read_parquet(INTERIM / "hits_classified.parquet",
                           columns=["ip", "traffic_class", "category", "intent_weight", "session_id"])

    # 1) IPinfo Lite for every IP
    db = maxminddb.open_database(str(REF / "ipinfo_lite.mmdb"))
    ips = pd.Series(hits["ip"].unique())
    rec = ips.map(lambda i: db.get(i) or {})
    ident = pd.DataFrame({
        "ip": ips,
        "asn": rec.map(lambda d: d.get("asn", "")),
        "as_name": rec.map(lambda d: d.get("as_name", "")),
        "as_domain": rec.map(lambda d: d.get("as_domain", "")),
        "country_code": rec.map(lambda d: d.get("country_code", "")),
        "country": rec.map(lambda d: d.get("country", "")),
        "continent": rec.map(lambda d: d.get("continent", "")),
    })
    asn_type = {a: classify_asn(n, d) for a, n, d in
                ident.drop_duplicates("asn")[["asn", "as_name", "as_domain"]].itertuples(index=False)}
    ident["net_type"] = ident["asn"].map(asn_type)
    ident["company_name"] = ""
    ident["company_domain"] = ""
    ident["id_source"] = ""
    org = ident["net_type"].eq("organization")
    ident.loc[org, "company_name"] = ident.loc[org, "as_name"]
    ident.loc[org, "company_domain"] = ident.loc[org, "as_domain"]
    ident.loc[org, "id_source"] = "ip_owner"

    # 2) RDAP for human visitors on ISP / unrecognised networks, highest-intent first
    human = hits[hits["traffic_class"].eq("human") & ~hits["category"].isin(NOISE)]
    intent = human.groupby("ip")["intent_weight"].sum()
    cand = ident[ident["ip"].isin(intent.index) & ident["net_type"].isin(["isp", "unverified"])].copy()
    cand["intent"] = cand["ip"].map(intent)
    cand = cand.sort_values("intent", ascending=False)

    cache: dict = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    idx = RangeIndex(cache)
    fetched = reused = 0
    t0 = time.time()
    for ip in cand["ip"]:
        if ip in cache:
            continue
        hit = idx.find(ip)
        if hit is not None:
            cache[ip] = hit
            reused += 1
            continue
        if fetched >= args.rdap_budget:
            continue
        d = rdap_fetch(ip)
        fetched += 1
        if d is None:
            continue
        s = rdap_summary(d)
        cache[ip] = s
        idx.add(s)
        time.sleep(1.0)
        if fetched % 100 == 0:
            CACHE.write_text(json.dumps(cache))
            print(f"  rdap {fetched} fetched, {reused} covered by known blocks, {time.time()-t0:.0f}s", flush=True)
    CACHE.write_text(json.dumps(cache))

    # apply RDAP results
    as_name = dict(zip(ident["ip"], ident["as_name"]))
    for ip, s in cache.items():
        if not s or ip not in as_name:
            continue
        m = ident["ip"].eq(ip)
        blob = f"{s.get('net_name','')} {s.get('registrant','')}"
        if re.search(r"\begain\b|^EGAIN", blob, re.I):
            ident.loc[m, ["net_type", "company_name", "id_source"]] = ["egain", "eGain (internal)", "rdap"]
            continue
        cust = assigned_customer(s, as_name[ip])
        if not cust:
            continue
        # the registrant may itself be a hosting / proxy / ISP / security company
        rtype = classify_asn(cust, "")
        if rtype in ("hosting", "isp", "security_proxy"):
            ident.loc[m, ["net_type", "id_source"]] = [rtype, "rdap"]
            continue
        ident.loc[m, ["net_type", "company_name", "id_source"]] = ["organization", cust, "rdap"]

    # behavioural check: proxy farms registered under an innocuous company name
    hv = (human.groupby("ip").agg(hits=("session_id", "size"), visits=("session_id", "nunique")))
    named = ident[ident["id_source"].eq("rdap") & ident["company_name"].ne("")].join(hv, on="ip")
    per = named.groupby("company_name").agg(ips=("ip", "size"), hits=("hits", "sum"), visits=("visits", "sum"))
    farms = per[(per["ips"] >= FARM_MIN_IPS) & (per["hits"] / per["visits"] <= FARM_MAX_HITS_PER_VISIT)].index
    if len(farms):
        print("proxy farms (behavioural):", ", ".join(farms))
        f = ident["company_name"].isin(farms) & ident["id_source"].eq("rdap")
        ident.loc[f, ["net_type", "company_name"]] = ["hosting", ""]

    ident.to_parquet(INTERIM / "ip_identity.parquet", index=False)
    h = ident[ident["ip"].isin(intent.index)]
    print("\nhuman IPs by network type:\n", h["net_type"].value_counts().to_string())
    print("identified by:\n", h[h["company_name"].ne("")]["id_source"].value_counts().to_string())
    print(f"RDAP: {fetched} fetched this run, {reused} covered by known blocks, cache {len(cache)}")


if __name__ == "__main__":
    main()
