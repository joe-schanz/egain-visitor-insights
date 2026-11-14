"""Step 5 — Score accounts, write rule-based dossiers, and export JSON for the web app.

Score (0–100) = Fit (0–30) + Intent (0–50) + Engagement (0–20). Every point is explainable:
the app shows the breakdown next to the score.

Inputs : data/interim/{hits_classified, sessions, contacts, ip_identity, ip_account, accounts_firmo}.parquet
Outputs: web/public/data/{accounts, visitors, contacts, overview}.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import NOISE_CATEGORIES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INTERIM, OUT = ROOT / "data" / "interim", ROOT / "web" / "public" / "data"
DATA_END = pd.Timestamp("2025-02-25 00:16:48", tz="UTC")
GAP = (pd.Timestamp("2025-02-10", tz="UTC"), pd.Timestamp("2025-02-20", tz="UTC"))

# ---------------- scoring rules ----------------
CORE_SECTORS = {"Financial Services", "Insurance", "Healthcare & Life Sciences", "Government & Public Sector",
                "Telecommunications", "Energy & Utilities", "Retail & Consumer",
                "Travel, Transport & Hospitality"}
SIZE_POINTS = {"Large enterprise (10K+)": 15, "Enterprise (1K–10K)": 12, "Mid-market (200–1K)": 6,
               "SMB (<200)": 2, "Unknown": 5}
# intent: the strongest signal in each group counts once
INTENT_POINTS = [("conversion", 20, "Viewed a conversion page (demo, contact, pricing, trial)"),
                 ("integration", 10, "Researched a platform integration"),
                 ("proof", 8, "Read customer proof or analyst reports"),
                 ("product", 6, "Explored product pages"),
                 ("industry|solutions", 6, "Read industry or solution pages"),
                 ("webinar|resource", 4, "Engaged with webinars or resources"),
                 ("education|topic_content|customer|partner", 2, "Read educational content")]

NON_TARGET = {"Education", "Other"}

COMPETITORS = re.compile(r"incontact|\bnice\b|genesys|five9|verint|zendesk|talkdesk|freshworks|kore\.ai|"
                         r"liveperson|8x8|avaya|ujet|sprinklr|servicenow|salesforce", re.I)

TALK_TRACK = {
    "Financial Services": "Regulated answers: one compliant, approved source of truth for agents, chatbots and "
                          "branches. Lower handle time and compliance risk.",
    "Insurance": "Policy and claims questions answered the same way on every channel; faster ramp for new agents.",
    "Healthcare & Life Sciences": "Accurate, approved answers for member and patient service; fewer escalations "
                                  "and repeat calls.",
    "Government & Public Sector": "Consistent public-facing answers across contact center, web and chat; absorb "
                                  "seasonal peaks with self-service.",
    "Energy & Utilities": "Outage and billing surges: guided self-service and agent answers from one knowledge base.",
    "Telecommunications": "High-volume troubleshooting: guided resolution cuts handle time and truck rolls.",
    "Retail & Consumer": "Order, returns and product questions answered instantly across chat and contact center.",
    "Travel, Transport & Hospitality": "Disruption peaks: self-service and agent guidance keep answers consistent.",
    "Technology & Software": "Complex-product support knowledge. Check first: may be a partner or competitor.",
    "Education": "Student and IT service desk knowledge. Usually a lower-priority segment for eGain.",
}


def title_from_path(path: str) -> str:
    if path in ("/", ""):
        return "Home"
    slug = [p for p in path.split("?")[0].split("/") if p][-1]
    return re.sub(r"[-_]+", " ", slug).strip().capitalize()[:80]


def join_list(xs: list[str]) -> str:
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def score_account(a: dict) -> dict:
    parts = []
    fit_sector = (15 if a["sector"] in CORE_SECTORS else 8 if a["sector"] == "Technology & Software"
                  else 0 if a["sector"] == "Education" else 4)
    parts.append({"group": "Fit", "points": fit_sector, "reason": f"Sector: {a['sector']}"})
    parts.append({"group": "Fit", "points": SIZE_POINTS[a["size_band"]], "reason": f"Size: {a['size_band']}"})
    cats = set(a["categories"])
    intent = 0
    for rx, pts, why in INTENT_POINTS:
        if any(re.fullmatch(rx, c) for c in cats):
            parts.append({"group": "Intent", "points": pts, "reason": why})
            intent += pts
    eng = []
    if a["visits"] >= 3:
        eng.append((6, f"{a['visits']} separate visits"))
    elif a["visits"] == 2:
        eng.append((3, "Came back for a second visit"))
    if a["visitors"] >= 3:
        eng.append((6, f"{a['visitors']} different people (buying group)"))
    elif a["visitors"] == 2:
        eng.append((3, "2 different people"))
    if a["unique_pages"] >= 5:
        eng.append((4, f"{a['unique_pages']} distinct pages"))
    if a["days_since_last"] <= 7:
        eng.append((4, "Active in the final week of data"))
    for p, why in eng:
        parts.append({"group": "Engagement", "points": p, "reason": why})
    fit = min(30, fit_sector + SIZE_POINTS[a["size_band"]])
    total = fit + min(50, intent) + min(20, sum(p for p, _ in eng))
    if a["flags"]:                      # competitors, job seekers, investors: not a buying signal
        total = min(total, 34)
    # Hot needs intent AND a target sector: a school district reading everything is interesting, not a top deal
    hot = total >= 60 and a["sector"] not in NON_TARGET
    return {"score": int(total), "tier": "Hot" if hot else "Warm" if total >= 35 else "Cold",
            "breakdown": parts}


def brief(a: dict) -> dict:
    """Plain-English dossier summary and talking points, generated from rules."""
    size = (f"{a['employees']:,} employees" if a["employees"] else a["size_band"].split(" (")[0].lower()
            if a["size_band"] != "Unknown" else "")
    who = ", ".join(x for x in [a["sector"] if a["sector"] != "Other" else "", size, a["hq"]] if x)
    period = (f"between {a['first_seen'][:10]} and {a['last_seen'][:10]}" if a["first_seen"][:10] != a["last_seen"][:10]
              else f"on {a['first_seen'][:10]}")
    headline = (f"{a['visitors']} {'person' if a['visitors'] == 1 else 'people'} from {a['name']}"
                f"{f' ({who})' if who else ''} made {a['visits']} visit{'s' if a['visits'] != 1 else ''} "
                f"and viewed {a['unique_pages']} page{'s' if a['unique_pages'] != 1 else ''} {period}.")
    points = []
    if a["conversion_pages"]:
        points.append(f"Hand-raiser: viewed {join_list([title_from_path(p) for p in a['conversion_pages'][:3]])}. "
                      f"Active evaluation; follow up within 24 hours.")
    if a["integrations"]:
        names = [k for k, _ in a["integrations"][:3]]
        points.append(f"Likely tech stack: researched eGain for {join_list(names)}. Lead with the native "
                      f"{names[0]} integration and ask how knowledge reaches their agents today.")
    if a["products"]:
        points.append(f"Product interest: {join_list([k for k, _ in a['products'][:3]])}.")
    if a["industries"]:
        points.append(f"Read eGain's {join_list([k for k, _ in a['industries'][:2]])} content; use the matching "
                      f"industry story.")
    if "proof" in a["categories"]:
        points.append("Read customer stories or analyst reports: validating vendors. Offer a peer reference.")
    if a["visitors"] >= 3:
        points.append(f"{a['visitors']} different people visited: a buying group may be forming. Multi-thread "
                      f"the outreach.")
    if a["contacts"]:
        points.append(f"{len(a['contacts'])} known CRM contact(s) from this account clicked a campaign email.")
    if a["sector"] in TALK_TRACK:
        points.append(f"Angle: {TALK_TRACK[a['sector']]}")
    if a["tier"] == "Hot":
        action = "Call this week: route to the owning AE with this dossier."
    elif a["tier"] == "Warm":
        action = "Add to a targeted sequence referencing the topics they read."
    else:
        action = "Monitor: nurture by marketing until intent increases."
    if a["flags"]:
        action = "Review before outreach: " + "; ".join(a["flags"]).lower() + "."
    return {"headline": headline, "talking_points": points, "next_action": action}


# ---------------- main ----------------
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hits = pd.read_parquet(INTERIM / "hits_classified.parquet")
    human = hits[hits["traffic_class"].eq("human")].copy()
    sessions = pd.read_parquet(INTERIM / "sessions.parquet")
    contacts = pd.read_parquet(INTERIM / "contacts.parquet")
    ident = pd.read_parquet(INTERIM / "ip_identity.parquet")
    ip_acct = pd.read_parquet(INTERIM / "ip_account.parquet")
    firmo = pd.read_parquet(INTERIM / "accounts_firmo.parquet").set_index("account_key")
    report = json.loads((ROOT / "data" / "processed" / "cleaning_report.json").read_text())

    human = human.merge(ip_acct, on="ip", how="left")
    human["visitor"] = human["ip"] + "|" + human["user_agent"].astype(str)
    signal = human[~human["category"].isin(NOISE_CATEGORIES)]
    sess = sessions.set_index("session_id")

    # contacts with a human click, linked to accounts via shared IPs
    real_contacts = contacts[contacts["status"].ne("scanner_only")].copy()
    ip_to_acct = dict(zip(ip_acct["ip"], ip_acct["account_key"]))
    real_contacts["account_key"] = real_contacts["human_ips"].map(
        lambda ips: next((ip_to_acct[i] for i in ips if i in ip_to_acct), ""))

    accounts = []
    for key, g in human[human["account_key"].notna()].groupby("account_key"):
        f = firmo.loc[key]
        sg = signal[signal["account_key"].eq(key)]
        if sg.empty:                                  # only careers/investor/legal pages
            noise_only = True
        else:
            noise_only = False

        def tag_counts(col):
            s = g[col].explode().dropna()
            return [[k, int(v)] for k, v in s.value_counts().items()]

        cat_counts = g["category"].value_counts()
        n = len(g)
        flags = []
        if COMPETITORS.search(f["name"]) or COMPETITORS.search(f["raw_name"]):
            flags.append("Possible competitor or partner researching eGain")
        if cat_counts.get("careers", 0) / n > 0.5:
            flags.append("Mostly careers pages: likely job seekers")
        if cat_counts.get("investor", 0) / n > 0.5:
            flags.append("Mostly investor-relations pages: likely analysts or investors")

        visits = []
        for sid, vg in g.sort_values("ts").groupby("session_id", sort=False):
            s = sess.loc[sid]
            visits.append({
                "start": s["start"].isoformat(), "duration_sec": int(s["duration_sec"]),
                "visitor": sorted(g["visitor"].unique()).index(vg["visitor"].iat[0]) + 1,
                "device": s["device"], "browser": s["browser"],
                "source": s["ref_class"], "source_host": s["ref_host"] or "",
                "campaign": s["utm_campaign"] or "",
                "pages": [{"t": t.isoformat(), "path": p, "title": title_from_path(p), "category": c}
                          for t, p, c in vg[["ts", "path", "category"]].head(40).itertuples(index=False)],
            })
        visits.sort(key=lambda v: v["start"], reverse=True)

        ips = sorted(g["ip"].unique())
        idrows = ident[ident["ip"].isin(ips)]
        a = {
            "key": key, "name": f["name"], "raw_name": f["raw_name"], "domain": f["domain"],
            "sector": f["sector"], "size_band": f["size_band"],
            "employees": int(f["employees"]) if pd.notna(f["employees"]) else None,
            "revenue": float(f["revenue"]) if pd.notna(f["revenue"]) else None,
            "revenue_currency": f["revenue_currency"], "hq": f["hq"], "hq_country": f["hq_country"],
            "description": f["description"], "wikidata_id": f["wikidata_id"],
            "wiki_industries": list(f["industries"]),
            "id_source": f["id_source"],
            "id_evidence": ("The visitor's IP network is registered to this organisation"
                            if f["id_source"] == "ip_owner" else
                            "The internet provider registered this IP block to this organisation (RDAP)"),
            "network_owner": idrows["as_name"].mode().iat[0] if len(idrows) else "",
            "countries": sorted(idrows["country"].dropna().unique().tolist()),
            "ips": len(ips), "visitors": int(g["visitor"].nunique()), "visits": int(g["session_id"].nunique()),
            "page_views": n, "unique_pages": int(g["path"].nunique()),
            "first_seen": g["ts"].min().isoformat(), "last_seen": g["ts"].max().isoformat(),
            "active_days": int(g["ts"].dt.date.nunique()),
            "days_since_last": int((DATA_END - g["ts"].max()).days),
            "categories": sorted(set(sg["category"])),
            "category_counts": {k: int(v) for k, v in cat_counts.items()},
            "integrations": tag_counts("tag_integration"), "products": tag_counts("tag_product"),
            "industries": tag_counts("tag_industry"),
            "conversion_pages": sorted(g.loc[g["category"].eq("conversion"), "path"].unique().tolist()),
            "top_pages": [[p, int(c)] for p, c in sg["path"].value_counts().head(10).items()],
            "sources": {k: int(v) for k, v in sess.loc[g["session_id"].unique(), "ref_class"].value_counts().items()},
            "search_terms_hint": sorted(sess.loc[g["session_id"].unique(), "ref_host"].dropna().unique().tolist())[:5],
            "contacts": real_contacts.loc[real_contacts["account_key"].eq(key), "uid"].tolist(),
            "flags": flags, "noise_only": noise_only,
            "visit_log": visits[:50],
        }
        a.update(score_account(a))
        a.update(brief(a))
        accounts.append(a)
    accounts.sort(key=lambda a: (-a["score"], -a["page_views"]))
    for i, a in enumerate(accounts, 1):
        a["rank"] = i

    # ---------------- anonymous high-intent visitors (not tied to an account) ----------------
    anon = signal[signal["account_key"].isna()].merge(
        ident[["ip", "net_type", "as_name", "country", "continent"]], on="ip", how="left")
    anon = anon[anon["net_type"].isin(["isp", "unverified", "security_proxy"])]
    vstats = (anon.groupby("ip")
              .agg(points=("intent_weight", "sum"), visits=("session_id", "nunique"), pages=("path", "nunique"),
                   first=("ts", "min"), last=("ts", "max"), net_type=("net_type", "first"),
                   network=("as_name", "first"), country=("country", "first"),
                   categories=("category", lambda s: sorted(set(s))),
                   integrations=("tag_integration", lambda s: sorted(set(x for l in s for x in l))),
                   products=("tag_product", lambda s: sorted(set(x for l in s for x in l))),
                   conversion=("category", lambda s: bool((s == "conversion").any())))
              .sort_values("points", ascending=False).head(500).reset_index())
    visitors = [{
        "ip_masked": re.sub(r"\.\d+$", ".x", r.ip) if "." in r.ip else r.ip.rsplit(":", 2)[0] + ":…",
        "points": int(r.points), "visits": int(r.visits), "pages": int(r.pages),
        "first_seen": r.first.isoformat(), "last_seen": r.last.isoformat(),
        "network_type": {"isp": "Internet provider", "unverified": "Unrecognised network",
                         "security_proxy": "Enterprise security gateway"}[r.net_type],
        "network": r.network or "", "country": r.country or "",
        "categories": r.categories, "integrations": r.integrations, "products": r.products,
        "conversion": r.conversion,
    } for r in vstats.itertuples(index=False)]

    # ---------------- contacts ----------------
    sess_pages = human.groupby("session_id")["path"].apply(list)
    out_contacts = []
    for c in real_contacts.itertuples(index=False):
        sids = sessions.loc[sessions["uid"].eq(c.uid), "session_id"].tolist()
        pages = [p for s in sids for p in sess_pages.get(s, [])]
        first_ip = c.human_ips[0] if len(c.human_ips) else ""
        idr = ident[ident["ip"].eq(first_ip)]
        out_contacts.append({
            "uid": c.uid, "status": c.status, "campaigns": list(c.campaigns), "region": c.region or "",
            "first_click": c.first_seen.isoformat(), "human_clicks": int(c.clicks_human),
            "scanner_clicks": int(c.clicks_scanner),
            "pages": [title_from_path(p) for p in dict.fromkeys(pages)][:15],
            "account_key": c.account_key,
            "network": idr["as_name"].iat[0] if len(idr) else "", "country": idr["country"].iat[0] if len(idr) else "",
        })
    out_contacts.sort(key=lambda c: (c["status"] != "engaged", -len(c["pages"])))

    # ---------------- overview ----------------
    hits["date"] = hits["ts"].dt.strftime("%Y-%m-%d")
    grp = hits["traffic_class"].map(lambda c: "human" if c == "human" else
                                    "email_scanner" if c == "email_scanner" else "bot")
    daily = hits.groupby(["date", grp]).size().unstack(fill_value=0)
    all_days = pd.date_range("2025-02-01", "2025-02-24", tz="UTC").strftime("%Y-%m-%d")
    daily = daily.reindex(all_days)
    daily_rows = [{"date": d, "in_gap": bool(np.isnan(r["human"])),
                   **{k: (None if np.isnan(r[k]) else int(r[k])) for k in daily.columns}}
                  for d, r in daily.iterrows()]

    hip = ident[ident["ip"].isin(human["ip"].unique())]
    camp = contacts.explode("campaigns").groupby(["campaigns", "status"]).size().unstack(fill_value=0)
    integ = signal.explode("tag_integration").dropna(subset=["tag_integration"])
    overview = {
        "data_window": {"start": report["date_range"][0], "end": report["date_range"][1],
                        "gap": ["2025-02-10T00:17:00Z", "2025-02-20T00:17:00Z"], "days_covered": 14},
        "funnel": [
            {"label": "Raw log hits", "value": report["raw_hits"]},
            {"label": "Human page views", "value": report["human_hits"]},
            {"label": "Human visitors (IPs)", "value": report["human_ips"]},
            {"label": "On identifiable networks", "value": int(hip["net_type"].isin(
                ["organization", "isp", "unverified", "security_proxy"]).sum())},
            {"label": "Identified organisations", "value": len(accounts)},
        ],
        "traffic_classes": report["hits_by_class"],
        "network_types": {k: int(v) for k, v in hip["net_type"].value_counts().items()},
        "daily": daily_rows,
        "categories": report["human_category_hits"],
        "referrers": report["human_ref_class"],
        "integration_interest": [[k, int(v)] for k, v in
                                 integ.groupby("tag_integration")["session_id"].nunique()
                                 .sort_values(ascending=False).items()],
        "top_pages": [[p, title_from_path(p), int(c)] for p, c in signal["path"].value_counts().head(25).items()],
        "campaigns": [{"campaign": k, **{s: int(r.get(s, 0)) for s in ["scanner_only", "clicked", "engaged"]}}
                      for k, r in camp.iterrows()],
        "contacts_by_status": report["contacts_by_status"],
        "tiers": pd.Series([a["tier"] for a in accounts]).value_counts().to_dict(),
        "sectors": pd.Series([a["sector"] for a in accounts]).value_counts().to_dict(),
        "security_gateway_visitors": int((hip["net_type"] == "security_proxy").sum()),
    }

    def dump(name, obj):
        (OUT / name).write_text(json.dumps(obj, separators=(",", ":"), default=str))
        print(f"  {name}: {(OUT / name).stat().st_size / 1024:.0f} KB")
    dump("accounts.json", accounts)
    dump("visitors.json", visitors)
    dump("contacts.json", out_contacts)
    dump("overview.json", overview)
    print("tiers:", overview["tiers"])
    for a in accounts[:15]:
        print(f"  {a['rank']:>3} {a['score']:>3} {a['tier']:<4} {a['name'][:40]:<40} {a['sector'][:22]:<22} "
              f"v{a['visits']} p{a['unique_pages']} {a['flags']}")


if __name__ == "__main__":
    main()
