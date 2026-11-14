"""Step 4 — Firmographics: industry, size, revenue, HQ for every identified organisation.

Source: Wikidata (free, open, CC0). Matching is precision-first, because a wrong company is worse
than a blank one in front of a rep:
  1. Website match: the organisation's domain equals the official website (P856) on a Wikidata item.
  2. Name match: an item whose English label or alias is exactly the cleaned name AND that looks like an
     organisation (has an industry, headcount, website, revenue or HQ). Ties go to the best-known item
     (most Wikipedia language editions).
Everything is batched SPARQL against the Wikidata Query Service (a handful of requests in total).
Anything unmatched still gets a sector from transparent keyword rules on its name/domain.

Inputs : data/interim/ip_identity.parquet
Outputs: data/interim/accounts_firmo.parquet, data/reference/wikidata_cache.json (cache, git-ignored)
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTERIM, REF = ROOT / "data" / "interim", ROOT / "data" / "reference"
CACHE = REF / "wikidata_cache.json"
SPARQL = "https://query.wikidata.org/sparql"
UA = "visitor-insights-prototype/0.1 (research prototype)"

CURRENCY = {"Q4917": "USD", "Q4916": "EUR", "Q25224": "GBP", "Q8146": "JPY", "Q80524": "INR",
            "Q41044": "RUB", "Q172872": "TRY", "Q202040": "KRW", "Q1104069": "CAD", "Q259502": "AUD",
            "Q173117": "BRL", "Q25344": "CHF", "Q39099": "CNY", "Q131473": "SEK", "Q31015": "HKD"}

# IPinfo country code -> Wikidata country label (only where they differ from a simple lookup)
COUNTRY_NAME = {"US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia",
                "IN": "India", "RU": "Russia", "TR": "Turkey", "KR": "South Korea", "CN": "People's Republic of China",
                "HK": "Hong Kong", "DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain", "NL": "Kingdom of the Netherlands",
                "IE": "Ireland", "CZ": "Czech Republic", "GH": "Ghana", "SG": "Singapore", "PK": "Pakistan", "NR": "Nauru",
                "JP": "Japan", "BR": "Brazil", "MX": "Mexico", "CH": "Switzerland", "SE": "Sweden", "IL": "Israel",
                "ZA": "South Africa", "NZ": "New Zealand", "KZ": "Kazakhstan", "UA": "Ukraine", "CY": "Cyprus",
                "LV": "Latvia", "MY": "Malaysia", "AR": "Argentina", "BE": "Belgium", "AT": "Austria", "PL": "Poland"}

# eGain's go-to-market verticals. First match wins; checked against
# "<name> <domain> <wikidata industry> <wikidata description> <instance-of>".
SECTOR_RULES = [
    ("Financial Services", r"\bbank|bancorp|banco|banca|bankasi|credit union|\bfcu\b|financial|securities|"
                           r"investment|capital markets|payment|worldpay|stock exchange|moex|siac|brokerage|"
                           r"jpmorgan|jpmchase|chase|citibank|capital one|squarepoint|asset management|lending|fintech|early warning"),
    ("Insurance", r"insurance|assurance|insurer|blue cross|blue shield|health plan|medica\b|hartford"),
    ("Healthcare & Life Sciences", r"hospital|medical|health|clinic|pharma|biotech|biopharm|csl\b|nih\b"),
    ("Government & Public Sector", r"government|ministry|department of|state of|county|city of|city hall|"
                                   r"council|federal|revenue service|\.gov\b|gov\.|veterans|public library|"
                                   r"agency|military|police|municipal"),
    ("Education", r"universit|univerzit|knihovna|college|school|academy|institute of technology|\.edu\b|edu\.|library"),
    ("Energy & Utilities", r"energy|electric|utility|utilities|power|gas\b|propane|petrol|oil\b|water"),
    ("Telecommunications", r"telecom|telephone|communications|wireless|mobile network|internet service"),
    ("Technology & Software", r"software|technolog|systems|cisco|check point|fortinet|lg cns|computer|"
                              r"\bit services|information protection|cybersecurity|incontact|cloud"),
    ("Professional Services", r"law firm|attorney|legal services|consult|accounting|advisory"),
    ("Travel, Transport & Hospitality", r"airline|airways|hotel|resort|travel|logistics|railway|transport|"
                                       r"shipping|sonesta"),
    ("Retail & Consumer", r"retail|store|consumer|food|restaurant|apparel|grocery|feed service|wine|spirits|distributing"),
    ("Manufacturing & Industrial", r"manufactur|industrial|engineering|construction|motors|automotive|"
                                   r"chemical|steel|alberici|tenaquip|packaging|tooling|cartridge"),
    ("Media & Entertainment", r"media|pictures|entertainment|broadcast|publishing|game"),
    ("Nonprofit & Religious", r"church|baptist|society|foundation|nonprofit|charity|genealogical"),
]
_SECTOR_RX = [(s, re.compile(p, re.I)) for s, p in SECTOR_RULES]

LEGAL_SUFFIX = re.compile(
    r"[,.]?\s*\b(inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|plc|ag|gmbh|sa|s\.a|"
    r"a\.s|as|pjsc|jsc|nv|bv|b\.v|n\.a|national association|sdn bhd|srl|s\.r\.l|oy|ab|pty|llp|lp)\b\.?",
    re.I)


def clean_name(name: str) -> str:
    n = re.sub(r"-\d{6,}$", "", name or "").strip()          # registry suffixes like "-090205144208"
    prev = None
    while prev != n:
        prev, n = n, LEGAL_SUFFIX.sub("", n).strip(" ,.&")
    if n.isupper() and len(n) > 4:
        n = n.title()
    return re.sub(r"\s+", " ", n)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", clean_name(s).lower().replace("&", "and"))


def http_json(url: str, params: dict | None = None, post: bool = False) -> dict:
    data = None
    if params and post:
        data = urllib.parse.urlencode(params).encode()
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:
            time.sleep(5 * (attempt + 1))
    return {}


# ---------------- SPARQL helpers ----------------
def sparql(q: str) -> list[dict]:
    res = http_json(SPARQL, {"query": q, "format": "json"}, post=True)
    time.sleep(1)
    return [{k: v["value"] for k, v in b.items()} for b in res.get("results", {}).get("bindings", [])]


def qid(uri: str) -> str:
    return uri.rsplit("/", 1)[1]


def lit(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"@en'


ORG_FILTER = "FILTER EXISTS { ?item wdt:P452|wdt:P1128|wdt:P856|wdt:P2139|wdt:P159 ?_x }"


def match_by_website(domains: list[str]) -> dict[str, str]:
    """domain -> QID via the official-website property (P856)."""
    out: dict[str, str] = {}
    for i in range(0, len(domains), 40):
        chunk = domains[i:i + 40]
        vals = " ".join(f"<{p}://{w}{d}{s}>" for d in chunk for p in ("http", "https")
                        for w in ("", "www.") for s in ("", "/"))
        rows = sparql(f"SELECT ?item ?site ?links WHERE {{ VALUES ?site {{ {vals} }} ?item wdt:P856 ?site ; "
                      f"wikibase:sitelinks ?links . }}")
        best: dict[str, tuple] = {}
        for r in rows:
            host = re.sub(r"^https?://(www\.)?|/$", "", r["site"]).lower()
            if host not in best or int(r["links"]) > best[host][0]:
                best[host] = (int(r["links"]), qid(r["item"]))
        out.update({h: v[1] for h, v in best.items()})
        print(f"  website match {i + len(chunk)}/{len(domains)}", flush=True)
    return out


def match_by_label(names: list[str]) -> dict[str, str]:
    """cleaned name -> QID via exact English label/alias, organisation-like items only."""
    out: dict[str, str] = {}
    for i in range(0, len(names), 30):
        chunk = names[i:i + 30]
        vals = " ".join(lit(n) for n in chunk)
        rows = sparql(f"SELECT ?item ?lbl ?links WHERE {{ VALUES ?lbl {{ {vals} }} "
                      f"{{ ?item rdfs:label ?lbl }} UNION {{ ?item skos:altLabel ?lbl }} "
                      f"{ORG_FILTER} ?item wikibase:sitelinks ?links . }}")
        best: dict[str, tuple] = {}
        for r in rows:
            if r["lbl"] not in best or int(r["links"]) > best[r["lbl"]][0]:
                best[r["lbl"]] = (int(r["links"]), qid(r["item"]))
        out.update({k: v[1] for k, v in best.items()})
        print(f"  name match {i + len(chunk)}/{len(names)}", flush=True)
    return out


def details(qids: list[str]) -> dict[str, dict]:
    """Label, description, industries, HQ, country, instance-of, latest headcount and revenue."""
    out: dict[str, dict] = {q: {"industries": [], "inst": []} for q in qids}
    for i in range(0, len(qids), 50):
        vals = " ".join(f"wd:{q}" for q in qids[i:i + 50])
        for r in sparql(f"""SELECT ?item ?label ?desc
              (GROUP_CONCAT(DISTINCT ?indL; separator="|") AS ?ind)
              (GROUP_CONCAT(DISTINCT ?instL; separator="|") AS ?inst)
              (SAMPLE(?hqL) AS ?hq) (SAMPLE(?ctL) AS ?ct) WHERE {{
              VALUES ?item {{ {vals} }}
              OPTIONAL {{ ?item rdfs:label ?label FILTER(lang(?label)="en") }}
              OPTIONAL {{ ?item schema:description ?desc FILTER(lang(?desc)="en") }}
              OPTIONAL {{ ?item wdt:P452 ?i . ?i rdfs:label ?indL FILTER(lang(?indL)="en") }}
              OPTIONAL {{ ?item wdt:P31 ?t . ?t rdfs:label ?instL FILTER(lang(?instL)="en") }}
              OPTIONAL {{ ?item wdt:P159 ?h . ?h rdfs:label ?hqL FILTER(lang(?hqL)="en") }}
              OPTIONAL {{ ?item wdt:P17 ?c . ?c rdfs:label ?ctL FILTER(lang(?ctL)="en") }}
            }} GROUP BY ?item ?label ?desc"""):
            d = out[qid(r["item"])]
            d.update(label=r.get("label", ""), desc=r.get("desc", ""), hq=r.get("hq", ""), country=r.get("ct", ""),
                     industries=[x for x in r.get("ind", "").split("|") if x][:3],
                     inst=[x for x in r.get("inst", "").split("|") if x][:3])
        # quantities: keep the most recent statement (by 'point in time'), preferring preferred rank
        for prop, key in (("P1128", "employees"), ("P2139", "revenue")):
            for r in sparql(f"""SELECT ?item ?amt ?unit ?t ?rank WHERE {{
                  VALUES ?item {{ {vals} }} ?item p:{prop} ?st . ?st psv:{prop} ?v ; wikibase:rank ?rank .
                  ?v wikibase:quantityAmount ?amt . OPTIONAL {{ ?v wikibase:quantityUnit ?unit }}
                  OPTIONAL {{ ?st pq:P585 ?t }} }}"""):
                d = out[qid(r["item"])]
                rank = (r["rank"].endswith("PreferredRank"), r.get("t", ""))
                if key not in d or rank > d[key][0]:
                    d[key] = (rank, float(r["amt"]), qid(r.get("unit", "/Q199")))
    return out


# ---------------- main ----------------
def main() -> None:
    ident = pd.read_parquet(INTERIM / "ip_identity.parquet")
    org = ident[ident["net_type"].eq("organization") & ident["company_name"].ne("")].copy()
    org["company_domain"] = org["company_domain"].fillna("").str.lower()
    org["account_key"] = org["company_domain"].where(org["company_domain"].ne(""), org["company_name"].map(norm))
    accts = (org.groupby("account_key")
             .agg(raw_name=("company_name", "first"), domain=("company_domain", "first"),
                  id_source=("id_source", "first"), ip_country=("country_code", lambda s: s.mode().iat[0]))
             .reset_index())
    accts["clean"] = accts["raw_name"].map(clean_name)

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    cache.setdefault("site", {}); cache.setdefault("label", {}); cache.setdefault("details", {})

    todo = [d for d in accts["domain"].unique() if d and d not in cache["site"]]
    if todo:
        found = match_by_website(todo)
        cache["site"].update({d: found.get(d, "") for d in todo})
        CACHE.write_text(json.dumps(cache))
    accts["qid"] = accts["domain"].map(lambda d: cache["site"].get(d, "") if d else "")
    accts["match"] = accts["qid"].ne("").map({True: "website", False: "none"})

    names = [n for n in accts.loc[accts["qid"].eq(""), "clean"].unique() if n not in cache["label"]]
    if names:
        found = match_by_label(names)
        cache["label"].update({n: found.get(n, "") for n in names})
        CACHE.write_text(json.dumps(cache))
    by_name = accts["qid"].eq("") & accts["clean"].map(lambda n: bool(cache["label"].get(n)))
    accts.loc[by_name, "qid"] = accts.loc[by_name, "clean"].map(cache["label"])
    accts.loc[by_name, "match"] = "name"

    need = [q for q in accts["qid"].unique() if q and q not in cache["details"]]
    if need:
        cache["details"].update(details(need))
        CACHE.write_text(json.dumps(cache))

    # a name-only match must agree on country (CSL Limited in Hong Kong is not the Chinese Super League),
    # unless Wikidata describes the organisation as multinational
    def country_ok(a) -> bool:
        d = cache["details"].get(a.qid, {})
        c = COUNTRY_NAME.get(a.ip_country, a.ip_country)
        return (not d.get("country") or d["country"] == c or "multinational" in d.get("desc", "").lower())
    bad = accts["match"].eq("name") & ~accts.apply(country_ok, axis=1)
    if bad.any():
        print("  rejected name matches (country mismatch):", ", ".join(accts.loc[bad, "raw_name"]))
    accts.loc[bad, ["qid", "match"]] = ["", "none"]

    rows = []
    for a in accts.itertuples(index=False):
        d = cache["details"].get(a.qid, {}) if a.qid else {}
        emp, rev = d.get("employees"), d.get("revenue")
        employees = int(emp[1]) if emp else None
        name = d.get("label") or a.clean
        blob = " ".join([a.raw_name, name, a.domain, *d.get("industries", []), d.get("desc", ""), *d.get("inst", [])])
        rows.append({
            "account_key": a.account_key, "name": name, "raw_name": a.raw_name, "domain": a.domain,
            "id_source": a.id_source, "wikidata_id": a.qid, "wikidata_match": a.match,
            "description": d.get("desc", ""), "industries": d.get("industries", []),
            "sector": next((s for s, rx in _SECTOR_RX if rx.search(blob)), "Other"),
            "employees": employees,
            "revenue": rev[1] if rev else None,
            "revenue_currency": CURRENCY.get(rev[2], "") if rev else "",
            "hq": d.get("hq", ""), "hq_country": d.get("country", ""), "ip_country": a.ip_country,
            "size_band": ("Large enterprise (10K+)" if employees and employees >= 10000 else
                          "Enterprise (1K–10K)" if employees and employees >= 1000 else
                          "Mid-market (200–1K)" if employees and employees >= 200 else
                          "SMB (<200)" if employees else "Unknown"),
        })
    out = pd.DataFrame(rows)
    out.to_parquet(INTERIM / "accounts_firmo.parquet", index=False)
    org[["ip", "account_key"]].to_parquet(INTERIM / "ip_account.parquet", index=False)

    print(f"{len(out)} accounts | wikidata match: {out['wikidata_match'].value_counts().to_dict()}")
    print("sector:\n", out["sector"].value_counts().to_string())
    print("size:\n", out["size_band"].value_counts().to_string())


if __name__ == "__main__":
    main()
