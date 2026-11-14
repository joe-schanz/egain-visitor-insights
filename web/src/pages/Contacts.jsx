import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmt, fmtDate, useData } from "../data.js";
import { Card, Kpi } from "../components.jsx";

const STATUS = [
  ["scanner_only", "Scanner only", "var(--series-1)"],
  ["clicked", "Clicked, no browsing", "var(--series-2)"],
  ["engaged", "Engaged", "var(--series-3)"],
];

function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + p.value, 0);
  return (
    <div className="tooltip">
      <div className="tooltip-title">{label}</div>
      {[...payload].reverse().map((p) => (
        <div className="tooltip-row" key={p.dataKey}>
          <span><i style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: p.color, marginRight: 6 }} />{p.name}</span>
          <b>{fmt(p.value)}</b>
        </div>
      ))}
      <div className="tooltip-row" style={{ borderTop: "1px solid var(--border)", marginTop: 4, paddingTop: 4 }}>
        <span>Recipients</span><b>{fmt(total)}</b>
      </div>
    </div>
  );
}

export default function Contacts() {
  const contacts = useData("contacts");
  const overview = useData("overview");
  const accounts = useData("accounts");
  const [params, setParams] = useSearchParams();
  const [limit, setLimit] = useState(100);
  const q = params.get("q") || "";
  const status = params.get("status") || "engaged";
  const campaign = params.get("campaign") || "";
  const set = (k, v) => { const p = new URLSearchParams(params); if (v) p.set(k, v); else p.delete(k); setParams(p, { replace: true }); setLimit(100); };

  const acctName = useMemo(() => Object.fromEntries((accounts || []).map((a) => [a.key, a.name])), [accounts]);
  const rows = useMemo(() => {
    if (!contacts) return [];
    const s = q.trim().toLowerCase();
    return contacts.filter((c) =>
      (status === "all" || c.status === status) &&
      (!campaign || c.campaigns.includes(campaign)) &&
      (!s || [c.uid, c.region, c.network, c.country, acctName[c.account_key] || "", ...c.pages, ...c.campaigns]
        .join(" ").toLowerCase().includes(s)));
  }, [contacts, q, status, campaign, acctName]);

  if (!contacts || !overview || !accounts) return <div className="loading">Loading contacts…</div>;
  const st = overview.contacts_by_status;
  const total = st.scanner_only + st.clicked + st.engaged;
  const camp = [...overview.campaigns]
    .map((c) => ({ ...c, total: c.scanner_only + c.clicked + c.engaged }))
    .sort((a, b) => b.total - a.total);
  const campTop = camp.slice(0, 8);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Email campaign contacts</h1>
          <p>
            Every campaign link carries the recipient's CRM ID. Most "clicks" are corporate email-security gateways
            opening links to scan them. These are separated from real people, so reps only chase contacts who actually engaged.
          </p>
        </div>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <Kpi label="Recipients with a recorded click" value={fmt(total)} note="what a raw marketing report shows" />
        <Kpi label="Machine clicks only" value={`${Math.round((st.scanner_only / total) * 100)}%`} note={`${fmt(st.scanner_only)} contacts: email delivered, no proof a human saw it`} />
        <Kpi label="Clicked, no further browsing" value={fmt(st.clicked)} note="plausibly human, unverified" />
        <Kpi label="Engaged" value={fmt(st.engaged)} note="clicked, then read more pages ≥ 5s later" />
      </div>

      <Card title="Clicks by campaign" sub={`Contacts per campaign, by what actually happened after the click · top ${campTop.length} of ${camp.length} campaigns`}>
        <div className="legend">
          {STATUS.map(([k, l, c]) => <span key={k}><i style={{ background: c }} />{l}</span>)}
        </div>
        <div style={{ height: campTop.length * 38 + 30 }}>
          <ResponsiveContainer>
            <BarChart data={campTop} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }} barCategoryGap={8}>
              <CartesianGrid horizontal={false} stroke="var(--grid)" />
              <XAxis type="number" tickFormatter={fmt} tick={{ fill: "var(--text-3)", fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="campaign" width={190} tick={{ fill: "var(--text-2)", fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTip />} cursor={{ fill: "var(--surface-2)" }} />
              {STATUS.map(([k, l, c], i) => (
                <Bar key={k} dataKey={k} name={l} stackId="s" fill={c} stroke="var(--surface)" strokeWidth={1}
                     radius={i === STATUS.length - 1 ? [0, 4, 4, 0] : 0} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card title="Contacts to follow up" sub="Only contacts with a human click are listed. IDs match the CRM contact record.">
        <div className="filters">
          <input className="search" placeholder="Search contact ID, page, network, account…" value={q}
                 onChange={(e) => set("q", e.target.value)} aria-label="Search contacts" />
          <div className="seg" role="group" aria-label="Status">
            {[["engaged", "Engaged"], ["clicked", "Clicked"], ["all", "Both"]].map(([k, l]) => (
              <button key={k} className={status === k ? "on" : ""} onClick={() => set("status", k === "engaged" ? "" : k)}>{l}</button>
            ))}
          </div>
          <select value={campaign} onChange={(e) => set("campaign", e.target.value)} aria-label="Campaign">
            <option value="">All campaigns</option>
            {camp.map((c) => <option key={c.campaign}>{c.campaign}</option>)}
          </select>
        </div>
        <div className="small muted" style={{ marginBottom: 10 }}>{fmt(rows.length)} contacts</div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Contact (CRM ID)</th><th>Status</th><th>Campaign</th><th>First click</th><th>Pages read</th><th>Network</th></tr>
            </thead>
            <tbody>
              {rows.slice(0, limit).map((c) => (
                <tr key={c.uid}>
                  <td><code className="small">{c.uid}</code><div className="small faint">{c.region}</div></td>
                  <td>{c.status === "engaged" ? <span className="pill good">✓ Engaged</span> : <span className="pill cold">Clicked</span>}</td>
                  <td className="small">{c.campaigns.join(", ")}</td>
                  <td className="small muted tnum" style={{ whiteSpace: "nowrap" }}>{fmtDate(c.first_click, true)}</td>
                  <td className="small" style={{ maxWidth: 320 }}>{c.pages.slice(0, 5).join(" → ") || <span className="faint">–</span>}</td>
                  <td className="small">
                    {c.account_key
                      ? <Link to={`/account/${encodeURIComponent(c.account_key)}`}>{acctName[c.account_key]}</Link>
                      : <span className="muted">{c.network || "–"}</span>}
                    <div className="faint">{c.country}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <div className="empty">No contacts match.</div>}
          {rows.length > limit && (
            <div className="empty"><button className="btn-link" onClick={() => setLimit(limit + 200)}>Show more ({fmt(rows.length - limit)} remaining)</button></div>
          )}
        </div>
      </Card>
    </>
  );
}
