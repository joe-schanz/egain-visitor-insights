import { useEffect, useState } from "react";

const cache = {};

/** Load a precomputed JSON file from /data once and share it across pages. */
export function useData(name) {
  const [data, setData] = useState(cache[name]?.value ?? null);
  useEffect(() => {
    if (cache[name]?.value) return;
    cache[name] ??= { promise: fetch(`/data/${name}.json`).then((r) => r.json()) };
    let live = true;
    cache[name].promise.then((v) => {
      cache[name].value = v;
      if (live) setData(v);
    });
    return () => { live = false; };
  }, [name]);
  return data;
}

export const fmt = (n) => (n == null ? "–" : Number(n).toLocaleString("en-US"));

export function fmtDate(iso, withTime = false) {
  if (!iso) return "–";
  const d = new Date(iso);
  const opts = { month: "short", day: "numeric", timeZone: "UTC" };
  if (withTime) Object.assign(opts, { hour: "2-digit", minute: "2-digit", hour12: false });
  return d.toLocaleString("en-US", opts) + (withTime ? " UTC" : "");
}

export function fmtMoney(v, cur) {
  if (v == null) return null;
  const units = [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]];
  const [div, u] = units.find(([d]) => v >= d) || [1, ""];
  return `${(v / div).toFixed(v / div >= 100 ? 0 : 1)}${u} ${cur || ""}`.trim();
}

export function fmtDuration(sec) {
  if (!sec) return "<1 min";
  if (sec < 60) return `${sec}s`;
  const m = Math.round(sec / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)}h ${m % 60}m`;
}

export const CATEGORY_LABEL = {
  conversion: "Conversion", integration: "Integration", product: "Product", proof: "Proof & analysts",
  industry: "Industry", solutions: "Solutions", webinar: "Webinars & events", resource: "Resources",
  education: "Education / blog", topic_content: "Topic content", partner: "Partners", customer: "Customers",
  company: "Company", home: "Home", news: "News", careers: "Careers", investor: "Investors",
  legal: "Legal", opt_out: "Email opt-out", feed: "Feeds", asset: "Assets", probe: "Probes",
};

export const SOURCE_LABEL = {
  direct: "Direct", search: "Search", internal: "Internal", referral: "Referral", social: "Social",
  review_analyst: "Review / analyst sites", email: "Email", ai_assistant: "AI assistant",
};

export const REPO_URL = "https://github.com/joe-schanz/egain-visitor-insights";
