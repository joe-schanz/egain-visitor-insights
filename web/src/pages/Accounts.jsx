import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { fmt, fmtDate, useData } from "../data.js";
import { Card, Kpi, ScoreBar, SortTh, TierPill, sortRows } from "../components.jsx";

const uniq = (xs) => [...new Set(xs.filter(Boolean))].sort();

export default function Accounts() {
  const accounts = useData("accounts");
  const overview = useData("overview");
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [sort, setSort] = useState({ key: "score", dir: "desc" });

  const f = {
    q: params.get("q") || "", tier: params.get("tier") || "All", sector: params.get("sector") || "",
    size: params.get("size") || "", country: params.get("country") || "", interest: params.get("interest") || "",
    hideFlagged: params.get("flagged") !== "show",
  };
  const set = (k, v) => {
    const p = new URLSearchParams(params);
    if (v === "" || v === "All" || v == null) p.delete(k); else p.set(k, v);
    setParams(p, { replace: true });
  };

  const opts = useMemo(() => {
    if (!accounts) return null;
    return {
      sectors: uniq(accounts.map((a) => a.sector)),
      sizes: ["Large enterprise (10K+)", "Enterprise (1K–10K)", "Mid-market (200–1K)", "SMB (<200)", "Unknown"],
      countries: uniq(accounts.flatMap((a) => a.countries)),
      interests: uniq(accounts.flatMap((a) => [...a.integrations, ...a.products].map(([k]) => k))),
    };
  }, [accounts]);

  const rows = useMemo(() => {
    if (!accounts) return [];
    const q = f.q.trim().toLowerCase();
    const out = accounts.filter((a) => {
      if (f.tier !== "All" && a.tier !== f.tier) return false;
      if (f.sector && a.sector !== f.sector) return false;
      if (f.size && a.size_band !== f.size) return false;
      if (f.country && !a.countries.includes(f.country)) return false;
      if (f.interest && ![...a.integrations, ...a.products].some(([k]) => k === f.interest)) return false;
      if (f.hideFlagged && a.flags.length) return false;
      if (q) {
        const hay = [a.name, a.raw_name, a.domain, a.sector, a.hq, ...a.countries,
          ...a.integrations.map((x) => x[0]), ...a.products.map((x) => x[0]), ...a.industries.map((x) => x[0]),
          ...a.top_pages.map((x) => x[0])].join(" ").toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    return sortRows(out, sort);
  }, [accounts, params, sort]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!accounts || !overview) return <div className="loading">Loading accounts…</div>;
  const engaged = overview.contacts_by_status.engaged;
  const hot = accounts.filter((a) => a.tier === "Hot").length;
  const warm = accounts.filter((a) => a.tier === "Warm").length;
  const anyFilter = [...params.keys()].length > 0;
  const callList = accounts.filter((a) => a.tier === "Hot" && !a.flags.length);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Accounts researching eGain</h1>
          <p>
            Organisations identified from eGain.com visits, scored on fit, intent and engagement. Click any account for
            its dossier: what they read, likely tech stack, and talking points.
          </p>
        </div>
      </div>

      <section className="callweek" aria-labelledby="callweek-title">
        <div className="callweek-head">
          <h2 id="callweek-title">Call this week</h2>
          <span className="small muted">{callList.length} hot accounts, highest score first. Each card opens the full dossier.</span>
        </div>
        <div className="callweek-grid">
          {callList.map((a) => (
            <Link key={a.key} className="callcard" to={`/account/${encodeURIComponent(a.key)}`}>
              <div className="callcard-top">
                <span className="callcard-name">{a.name}</span>
                <span className="callcard-score tnum" title={`Score ${a.score} / 100`}>{a.score}</span>
              </div>
              <div className="small muted">{a.sector}</div>
              <div className="callcard-why">{a.next_why}</div>
              <div className="small faint">
                {a.visitors} {a.visitors === 1 ? "person" : "people"} · {a.visits} visit{a.visits !== 1 ? "s" : ""} · last seen {fmtDate(a.last_seen)}
              </div>
            </Link>
          ))}
        </div>
      </section>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <Kpi label="Identified accounts" value={fmt(accounts.length)} note="from 30,083 human visitor IPs" />
        <Kpi label="Hot accounts" value={hot} note="score ≥ 60 in a target sector" />
        <Kpi label="Warm accounts" value={warm} note="score 35–59" />
        <Kpi label="Engaged email contacts" value={engaged} note="of 45,736 that 'clicked'" />
      </div>

      <Card>
        <div className="filters">
          <input className="search" placeholder="Search company, domain, integration, page…" value={f.q}
                 onChange={(e) => set("q", e.target.value)} aria-label="Search accounts" />
          <div className="seg" role="group" aria-label="Tier">
            {["All", "Hot", "Warm", "Cold"].map((t) => (
              <button key={t} className={f.tier === t ? "on" : ""} onClick={() => set("tier", t)}>{t}</button>
            ))}
          </div>
          <select value={f.sector} onChange={(e) => set("sector", e.target.value)} aria-label="Sector">
            <option value="">All sectors</option>
            {opts.sectors.map((s) => <option key={s}>{s}</option>)}
          </select>
          <select value={f.size} onChange={(e) => set("size", e.target.value)} aria-label="Company size">
            <option value="">All sizes</option>
            {opts.sizes.map((s) => <option key={s}>{s}</option>)}
          </select>
          <select value={f.country} onChange={(e) => set("country", e.target.value)} aria-label="Visitor country">
            <option value="">All countries</option>
            {opts.countries.map((s) => <option key={s}>{s}</option>)}
          </select>
          <select value={f.interest} onChange={(e) => set("interest", e.target.value)} aria-label="Interest">
            <option value="">Any interest</option>
            {opts.interests.map((s) => <option key={s}>{s}</option>)}
          </select>
          <label className="check">
            <input type="checkbox" checked={!f.hideFlagged} onChange={(e) => set("flagged", e.target.checked ? "show" : "")} />
            Show flagged
          </label>
        </div>
        <div className="small muted" style={{ marginBottom: 10 }}>
          {rows.length} of {accounts.length} accounts
          {anyFilter && <> · <button className="btn-link small" onClick={() => setParams({}, { replace: true })}>Clear filters</button></>}
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <SortTh k="score" label="Score" sort={sort} setSort={setSort} />
                <SortTh k="name" label="Account" sort={sort} setSort={setSort} />
                <th>Next step</th>
                <th>Key signals</th>
                <SortTh k="sector" label="Sector" sort={sort} setSort={setSort} />
                <SortTh k="visitors" label="People" sort={sort} setSort={setSort} num />
                <SortTh k="visits" label="Visits" sort={sort} setSort={setSort} num />
                <SortTh k="last_seen" label="Last seen" sort={sort} setSort={setSort} />
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.key} className="clickable" onClick={() => nav(`/account/${encodeURIComponent(a.key)}`)}>
                  <td style={{ width: 170 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <TierPill tier={a.tier} /><ScoreBar score={a.score} />
                    </div>
                  </td>
                  <td>
                    <Link className="acct-name" to={`/account/${encodeURIComponent(a.key)}`} onClick={(e) => e.stopPropagation()}>
                      {a.name}
                    </Link>
                    <div className="small faint">
                      {[a.domain, a.size_band !== "Unknown" ? a.size_band : "", a.countries.slice(0, 2).join(", ")]
                        .filter(Boolean).join(" · ")}
                    </div>
                    {a.flags.map((fl) => <span key={fl} className="pill flag" style={{ marginTop: 4 }}>⚑ {fl}</span>)}
                  </td>
                  <td style={{ minWidth: 180 }}>
                    <div className={`next-step ${a.tier.toLowerCase()}${a.flags.length ? " flagged" : ""}`}>{a.next_step}</div>
                    <div className="small muted">{a.next_why}</div>
                  </td>
                  <td>
                    <div className="chips">
                      {a.conversion_pages.length > 0 && <span className="chip strong">Conversion page</span>}
                      {a.integrations.slice(0, 2).map(([k]) => <span key={k} className="chip strong">{k}</span>)}
                      {a.products.slice(0, 2).map(([k]) => <span key={k} className="chip">{k}</span>)}
                      {a.contacts.length > 0 && <span className="chip">{a.contacts.length} CRM contact{a.contacts.length > 1 ? "s" : ""}</span>}
                    </div>
                  </td>
                  <td className="muted">{a.sector}</td>
                  <td className="num">{a.visitors}</td>
                  <td className="num">{a.visits}</td>
                  <td className="muted tnum" style={{ whiteSpace: "nowrap" }}>{fmtDate(a.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <div className="empty">No accounts match these filters.</div>}
        </div>
      </Card>
    </>
  );
}
