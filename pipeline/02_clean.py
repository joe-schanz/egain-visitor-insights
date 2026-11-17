"""Step 2 — Clean the weblog: separate real people from machines, then build visits.

Inputs : data/interim/hits.parquet                (from 01_load.py)
Outputs: data/interim/hits_classified.parquet     every hit + a traffic_class label
         data/interim/sessions.parquet            human visits (30-min inactivity rule)
         data/interim/contacts.parquet            one row per emailed contact (CRM uid)
         data/processed/cleaning_report.json      funnel numbers for the deck/README

Every hit gets exactly ONE traffic_class, assigned in priority order (first rule wins):
  asset          static file (.js/.css/.png ...)
  probe          vulnerability / open-redirect scanning (wp-admin, .php, utm_medium=//bestbuy.com ...)
  bot_declared   user agent says it's a bot (bot, crawler, python, curl, nagios ...) or an RSS feed fetch
  email_scanner  campaign-link click made by an email-security gateway or sandbox, not the recipient
  monitor        IP repeatedly polls the same 1-3 pages over many days (uptime / price watchers)
  crawler        IP behaves like a crawler (hundreds of distinct pages, or 30+ hits in one minute)
  bot_suspected  browser signature that no real person uses in 2025 (Internet Explorer <= 9)
  bot_distributed  one browser signature across 100+ IPs, 95%+ one-page direct visits (proxy bot network)
  crawler (pass 2) a visit of 4+ pages loaded a median <= 2s apart
  human          everything else
See docs/DECISIONS.md (D-005 .. D-008) for why each rule and threshold was chosen.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import INTENT_WEIGHT, categorize, tags  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

# ---- thresholds (documented in DECISIONS.md) ----
GATEWAY_MIN_UIDS = 5        # one IP clicking links addressed to >= 5 different people = security gateway
MONITOR_MAX_PATHS = 3       # polls <= 3 distinct pages ...
MONITOR_MIN_HITS = 50       # ... at least 50 times ...
MONITOR_MIN_DAYS = 5        # ... spread over >= 5 days
CRAWLER_MIN_PATHS = 200     # no human reads 200+ distinct pages of a vendor site in 2 weeks
CRAWLER_MAX_PER_MIN = 30    # 30+ requests in a single minute from one IP
SESSION_GAP = pd.Timedelta(minutes=30)  # industry-standard (GA) visit timeout
DISTRIBUTED_MIN_IPS = 100     # one browser signature spread across 100+ IPs ...
DISTRIBUTED_MIN_BOUNCE = 0.95 # ... where 95%+ of visits are 1 page with no referrer = bot network
FAST_MIN_HITS = 4             # a visit of 4+ pages ...
FAST_MAX_GAP_SEC = 2          # ... loaded a median <= 2s apart is machine pace, not reading
MAX_HUMAN_PAGES_PER_VISIT = 40  # nobody evaluating a vendor reads 40+ distinct pages in one sitting
BURST_MIN_SAME_SECOND = 3     # 3+ campaign/opt-out hits from one IP in the same second = link scanner
ENGAGED_MIN_DELAY_SEC = 5     # follow-on page must come >= 5s after the click to count as engagement

BOT_UA = re.compile(
    r"bot|crawl|spider|slurp|python|aiohttp|requests/|curl|wget|java/|go-http|okhttp|httpclient|"
    r"headless|phantom|scrapy|check_http|nagios|monitor|uptime|pingdom|statuscake|feed|rss|"
    r"facebookexternalhit|preview|scanner|zgrab|masscan|nmap|libwww|apache-httpclient|axios|node-fetch|"
    r"^mozilla/5\.0/5\.0$|^-?$|^mozilla/5\.0$",
    re.I,
)
LEGACY_IE = re.compile(r"MSIE [2-9]\.", re.I)
SCANNER_UA = re.compile(r"barracuda|sentinel|mimecast|proofpoint|safelinks|ironport|forcepoint|symantec", re.I)
PROBE_QUERY = re.compile(r"bestbuy|https?:|%2f%2e|\\x5c|aHR0c|<script|union\s+select", re.I)


# ---------- parsing helpers ----------
def parse_url(url: str) -> tuple[str, dict]:
    url = url.replace("&amp;", "&").replace("amp;", "")
    parts = urlsplit(url if url.startswith("/") else "/" + url)
    path = re.sub(r"/{2,}", "/", parts.path.lower()) or "/"
    q = {k: v[0] for k, v in parse_qs(parts.query).items()}
    return path, q


def referrer_class(ref: str) -> tuple[str, str]:
    if not ref or ref == "-":
        return "direct", ""
    host = urlsplit(ref if "://" in ref else "http://" + ref).netloc.lower().removeprefix("www.")
    if "egain" in host:
        return "internal", host
    if re.search(r"google|bing|yahoo|duckduckgo|baidu|yandex|ecosia", host):
        return "search", host
    if re.search(r"linkedin|lnkd|twitter|t\.co|facebook|youtube|reddit|x\.com", host):
        return "social", host
    if re.search(r"mail|outlook|office|proofpoint|mimecast", host):
        return "email", host
    if re.search(r"chatgpt|openai|perplexity|claude|gemini|copilot", host):
        return "ai_assistant", host
    if re.search(r"g2|capterra|gartner|trustradius|kmworld|forrester", host):
        return "review_analyst", host
    return "referral", host


def ua_fields(ua: str) -> tuple[str, str, str]:
    device = "mobile" if re.search(r"mobile|iphone|android|ipad", ua, re.I) else "desktop"
    if re.search(r"edg/", ua, re.I):
        browser = "Edge"
    elif re.search(r"chrome/", ua, re.I):
        browser = "Chrome"
    elif re.search(r"firefox/", ua, re.I):
        browser = "Firefox"
    elif re.search(r"safari/", ua, re.I):
        browser = "Safari"
    elif re.search(r"msie|trident", ua, re.I):
        browser = "Internet Explorer"
    else:
        browser = "Other"
    if re.search(r"windows", ua, re.I):
        os_ = "Windows"
    elif re.search(r"iphone|ipad|ios", ua, re.I):
        os_ = "iOS"
    elif re.search(r"mac os", ua, re.I):
        os_ = "macOS"
    elif re.search(r"android", ua, re.I):
        os_ = "Android"
    elif re.search(r"linux|x11", ua, re.I):
        os_ = "Linux"
    else:
        os_ = "Other"
    return device, browser, os_


def campaign_region(campaign: str) -> str:
    c = (campaign or "").lower()
    if "emea" in c:
        return "EMEA"
    if re.search(r"(^|_)na(_|fw|$)|nafw", c):
        return "North America"
    if "apac" in c:
        return "APAC"
    return ""


def assign_sessions(df: pd.DataFrame) -> pd.Series:
    """Group human hits into visits: same IP + same browser, no gap longer than 30 minutes."""
    h = df[df["traffic_class"].eq("human")].sort_values(["ip", "user_agent", "ts"])
    new_visit = (
        h["ip"].ne(h["ip"].shift()) | h["user_agent"].ne(h["user_agent"].shift())
        | (h["ts"] - h["ts"].shift()).gt(SESSION_GAP)
    )
    return new_visit.cumsum().reindex(df.index).astype("Int64")


# ---------- main ----------
def main() -> None:
    df = pd.read_parquet(INTERIM / "hits.parquet")
    n_raw = len(df)

    # URL -> path + campaign params (parsed once per unique URL for speed)
    uniq = pd.Series(df["url"].unique())
    parsed = uniq.map(parse_url)
    url_map = pd.DataFrame({
        "url": uniq,
        "path": parsed.map(lambda t: t[0]),
        "utm_source": parsed.map(lambda t: t[1].get("utm_source", "")),
        "utm_medium": parsed.map(lambda t: t[1].get("utm_medium", "")),
        "utm_campaign": parsed.map(lambda t: t[1].get("utm_campaign", "")),
        "uid": parsed.map(lambda t: t[1].get("uid", "").lower()),
        "query_is_probe": uniq.map(lambda u: bool(PROBE_QUERY.search(u.split("?", 1)[1])) if "?" in u else False),
    })
    url_map.loc[~url_map.uid.str.fullmatch(r"[0-9a-f-]{36}"), "uid"] = ""
    df = df.merge(url_map, on="url", how="left")

    # page meaning
    paths = pd.Series(df["path"].unique())
    cat = paths.map(categorize)
    tg = paths.map(tags)
    page_map = pd.DataFrame({
        "path": paths, "category": cat, "intent_weight": cat.map(INTENT_WEIGHT).astype(int),
        "tag_industry": tg.map(lambda t: t["industry"]),
        "tag_integration": tg.map(lambda t: t["integration"]),
        "tag_product": tg.map(lambda t: t["product"]),
    })
    df = df.merge(page_map, on="path", how="left")

    # referrer + user agent
    ref = df["referrer"].map(referrer_class)
    df["ref_class"] = ref.map(lambda t: t[0])
    df["ref_host"] = ref.map(lambda t: t[1])
    uas = pd.Series(df["user_agent"].unique())
    ua_map = pd.DataFrame({
        "user_agent": uas,
        "ua_is_bot": uas.map(lambda u: bool(BOT_UA.search(u))),
        "ua_legacy_ie": uas.map(lambda u: bool(LEGACY_IE.search(u))),
        **dict(zip(["device", "browser", "os"], zip(*uas.map(ua_fields)))),
    })
    df = df.merge(ua_map, on="user_agent", how="left")

    # ---- per-IP behavior ----
    has_uid = df["uid"] != ""
    uids_per_ip = df[has_uid].groupby("ip")["uid"].nunique()
    gateway_ips = set(uids_per_ip[uids_per_ip >= GATEWAY_MIN_UIDS].index)
    # link-detonation burst: scanners open every link in an email in the same second
    # (landing page + opt-out footer link, or the same link many times)
    u = df[has_uid | df["category"].eq("opt_out")]
    per_sec = u.groupby(["ip", u["ts"].dt.floor("s")]).size()
    burst_ips = set(per_sec[per_sec >= BURST_MIN_SAME_SECOND].index.get_level_values(0))
    gateway_ips |= burst_ips

    content = ~df["category"].isin(["asset", "probe"])
    ip_stats = df[content].groupby("ip").agg(
        hits=("path", "size"), paths=("path", "nunique"), days=("ts", lambda s: s.dt.date.nunique()))
    per_min = df.groupby(["ip", df["ts"].dt.floor("min")]).size().groupby("ip").max()
    ip_stats["peak_per_min"] = per_min
    monitor_ips = set(ip_stats.query(
        "paths <= @MONITOR_MAX_PATHS and hits >= @MONITOR_MIN_HITS and days >= @MONITOR_MIN_DAYS").index)
    crawler_ips = set(ip_stats.query(
        "paths >= @CRAWLER_MIN_PATHS or peak_per_min >= @CRAWLER_MAX_PER_MIN").index)

    # ---- assign one class per hit, first rule wins ----
    scanner_ua = df["user_agent"].str.contains(SCANNER_UA)
    conds = [
        df["category"].eq("asset"),
        df["category"].eq("probe") | df["query_is_probe"],
        has_uid & (df["ua_legacy_ie"] | df["ip"].isin(gateway_ips) | scanner_ua | df["ua_is_bot"]),
        df["ua_is_bot"] | scanner_ua | df["category"].eq("feed"),
        df["ip"].isin(monitor_ips),
        df["ip"].isin(crawler_ips),
        df["ua_legacy_ie"],
    ]
    labels = ["asset", "probe", "email_scanner", "bot_declared", "monitor", "crawler", "bot_suspected"]
    df["traffic_class"] = np.select(conds, labels, default="human")
    # a gateway IP's *non*-campaign hits are judged on their own merits (it may be a corporate NAT)

    # ---- pass 2: session-level behavior of what is still "human" ----
    df["session_id"] = assign_sessions(df)
    hum = df[df["session_id"].notna()].sort_values(["session_id", "ts"]).copy()
    hum["gap"] = hum.groupby("session_id")["ts"].diff().dt.total_seconds()
    s = hum.groupby("session_id").agg(
        ua=("user_agent", "first"), ip=("ip", "first"), hits=("path", "size"),
        pages=("path", "nunique"), ref=("ref_class", "first"), gap=("gap", "median"))
    s["bounce_direct"] = (s["pages"] == 1) & (s["ref"] == "direct")
    fp = s.groupby("ua").agg(ips=("ip", "nunique"), bd=("bounce_direct", "mean"))
    distributed_uas = set(fp[(fp["ips"] >= DISTRIBUTED_MIN_IPS) & (fp["bd"] >= DISTRIBUTED_MIN_BOUNCE)].index)
    fast_sessions = set(s[((s["hits"] >= FAST_MIN_HITS) & (s["gap"] <= FAST_MAX_GAP_SEC))
                          | (s["pages"] >= MAX_HUMAN_PAGES_PER_VISIT)].index)
    df.loc[df["session_id"].notna() & df["user_agent"].isin(distributed_uas), "traffic_class"] = "bot_distributed"
    df.loc[df["session_id"].isin(fast_sessions), "traffic_class"] = "crawler"
    df["session_id"] = assign_sessions(df)  # rebuild visits from the final human set

    hh = df[df["session_id"].notna()]
    signal = ~hh["category"].isin(["opt_out", "legal", "investor", "careers", "feed"])
    sessions = hh.groupby("session_id").agg(
        ip=("ip", "first"),
        user_agent=("user_agent", "first"),
        device=("device", "first"), browser=("browser", "first"), os=("os", "first"),
        start=("ts", "min"), end=("ts", "max"),
        hits=("path", "size"), pages=("path", "nunique"),
        entry_path=("path", "first"), ref_class=("ref_class", "first"), ref_host=("ref_host", "first"),
        utm_source=("utm_source", "max"), utm_campaign=("utm_campaign", "max"), uid=("uid", "max"),
        categories=("category", lambda s: sorted(set(s))),
        max_intent=("intent_weight", "max"),
    )
    sessions["duration_sec"] = (sessions["end"] - sessions["start"]).dt.total_seconds().astype(int)
    sessions["intent_points"] = (
        hh[signal].drop_duplicates(["session_id", "path"]).groupby("session_id")["intent_weight"].sum()
        .reindex(sessions.index).fillna(0).astype(int))
    noise_only = hh.groupby("session_id")["category"].agg(
        lambda s: set(s) <= {"opt_out", "legal", "investor", "careers", "feed"})
    sessions["noise_only"] = noise_only
    sessions = sessions.reset_index()

    # ---- contacts: one row per emailed person (CRM uid) ----
    c = df[has_uid].copy()
    c["is_human_click"] = c["traffic_class"].eq("human")
    # "engaged" = after the human click, the person went on to a real page (not the campaign
    # landing page, not opt-out/legal) at least 5 seconds later. Proves a human read and explored.
    click_time = c[c["is_human_click"]].groupby("session_id")["ts"].min()
    landing = set(c["path"])
    follow = df[df["session_id"].isin(click_time.index)
                & ~df["path"].isin(landing)
                & ~df["category"].isin(["opt_out", "legal", "feed"])]
    follow = follow[(follow["ts"] - follow["session_id"].map(click_time)).dt.total_seconds() >= ENGAGED_MIN_DELAY_SEC]
    engaged_sessions = set(follow["session_id"])
    c["engaged"] = c["session_id"].isin(engaged_sessions) & c["is_human_click"]
    contacts = c.groupby("uid").agg(
        campaigns=("utm_campaign", lambda s: sorted(set(x for x in s if x))),
        first_seen=("ts", "min"), last_seen=("ts", "max"),
        clicks_total=("ts", "size"),
        clicks_scanner=("traffic_class", lambda s: int((s == "email_scanner").sum())),
        clicks_human=("is_human_click", "sum"),
        engaged=("engaged", "any"),
        human_ips=("ip", lambda s: sorted(set(s[c.loc[s.index, "is_human_click"]]))),
        all_ips=("ip", lambda s: sorted(set(s))),
    ).reset_index()
    contacts["region"] = contacts["campaigns"].map(
        lambda cs: next((r for r in map(campaign_region, cs) if r), ""))
    contacts["status"] = np.select(
        [contacts["engaged"], contacts["clicks_human"] > 0],
        ["engaged", "clicked"], default="scanner_only")

    # ---- write outputs ----
    for col in ["tag_industry", "tag_integration", "tag_product"]:
        df[col] = df[col].map(list)
    df.to_parquet(INTERIM / "hits_classified.parquet", index=False)
    sessions.to_parquet(INTERIM / "sessions.parquet", index=False)
    contacts.to_parquet(INTERIM / "contacts.parquet", index=False)

    human = df[df["traffic_class"].eq("human")]
    report = {
        "raw_hits": n_raw,
        "raw_ips": int(df["ip"].nunique()),
        "date_range": [str(df["ts"].min()), str(df["ts"].max())],
        "hits_by_class": df["traffic_class"].value_counts().to_dict(),
        "ips_by_class": df.groupby("traffic_class")["ip"].nunique().to_dict(),
        "human_hits": int(len(human)),
        "human_ips": int(human["ip"].nunique()),
        "human_sessions": int(len(sessions)),
        "human_sessions_with_signal": int((~sessions["noise_only"]).sum()),
        "gateway_ips": len(gateway_ips), "monitor_ips": len(monitor_ips), "crawler_ips": len(crawler_ips),
        "contacts_total": int(len(contacts)),
        "contacts_by_status": contacts["status"].value_counts().to_dict(),
        "campaign_clicks_total": int(has_uid.sum()),
        "campaign_clicks_scanner": int((df["traffic_class"] == "email_scanner").sum()),
        "human_category_hits": human["category"].value_counts().to_dict(),
        "human_ref_class": human.drop_duplicates("session_id")["ref_class"].value_counts().to_dict(),
    }
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "cleaning_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
