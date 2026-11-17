import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CATEGORY_LABEL, fmt, fmtDate, useData } from "../data.js";
import { Card, SortTh, sortRows } from "../components.jsx";

export default function Visitors() {
  const visitors = useData("visitors");
  const overview = useData("overview");
  const [params, setParams] = useSearchParams();
  const [sort, setSort] = useState({ key: "points", dir: "desc" });
  const q = params.get("q") || "";
  const type = params.get("type") || "";
  const country = params.get("country") || "";
  const conv = params.get("conv") === "1";
  const set = (k, v) => { const p = new URLSearchParams(params); if (v) p.set(k, v); else p.delete(k); setParams(p, { replace: true }); };

  const rows = useMemo(() => {
    if (!visitors) return [];
    const s = q.trim().toLowerCase();
    return sortRows(visitors.filter((v) =>
      (!type || v.network_type === type) && (!country || v.country === country) && (!conv || v.conversion) &&
      (!s || [v.network, v.country, ...v.integrations, ...v.products, ...v.categories].join(" ").toLowerCase().includes(s))), sort);
  }, [visitors, q, type, country, conv, sort]);

  if (!visitors || !overview) return <div className="loading">Loading…</div>;
  const countries = [...new Set(visitors.map((v) => v.country).filter(Boolean))].sort();

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Anonymous high-intent visitors</h1>
          <p>
            Real people who showed buying intent but couldn't be tied to a company with free data: home or office
            broadband, or an enterprise security gateway. This is exactly the gap a commercial identity service
            (6sense, Demandbase, ZoomInfo) fills. Top 500 by intent.
          </p>
        </div>
      </div>

      <div className="callout">
        <b>{fmt(overview.security_gateway_visitors)} visitors</b> came through enterprise security gateways (Zscaler,
        Netskope …). That's almost certainly a corporate employee, but the gateway hides which company.
      </div>

      <Card>
        <div className="filters">
          <input className="search" placeholder="Search network, country, integration, product…" value={q}
                 onChange={(e) => set("q", e.target.value)} aria-label="Search visitors" />
          <select value={type} onChange={(e) => set("type", e.target.value)} aria-label="Network type">
            <option value="">All network types</option>
            {["Internet provider", "Enterprise security gateway", "Unrecognized network"].map((t) => <option key={t}>{t}</option>)}
          </select>
          <select value={country} onChange={(e) => set("country", e.target.value)} aria-label="Country">
            <option value="">All countries</option>
            {countries.map((c) => <option key={c}>{c}</option>)}
          </select>
          <label className="check"><input type="checkbox" checked={conv} onChange={(e) => set("conv", e.target.checked ? "1" : "")} />Viewed a conversion page</label>
        </div>
        <div className="small muted" style={{ marginBottom: 10 }}>{fmt(rows.length)} visitors · IP addresses are masked</div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <SortTh k="points" label="Intent pts" sort={sort} setSort={setSort} num />
                <th>Visitor</th>
                <th>Researched</th>
                <SortTh k="pages" label="Pages" sort={sort} setSort={setSort} num />
                <SortTh k="visits" label="Visits" sort={sort} setSort={setSort} num />
                <SortTh k="last_seen" label="Last seen" sort={sort} setSort={setSort} />
              </tr>
            </thead>
            <tbody>
              {rows.map((v, i) => (
                <tr key={i}>
                  <td className="num"><b>{v.points}</b></td>
                  <td>
                    <div style={{ fontWeight: 500 }}>{v.network || "Unknown network"}</div>
                    <div className="small faint">{v.network_type} · {v.country || "–"} · <code>{v.ip_masked}</code></div>
                  </td>
                  <td>
                    <div className="chips">
                      {v.conversion && <span className="chip strong">Conversion page</span>}
                      {v.integrations.map((k) => <span key={k} className="chip strong">{k}</span>)}
                      {v.products.slice(0, 2).map((k) => <span key={k} className="chip">{k}</span>)}
                      {!v.integrations.length && !v.products.length && !v.conversion &&
                        v.categories.slice(0, 3).map((c) => <span key={c} className="chip">{CATEGORY_LABEL[c] || c}</span>)}
                    </div>
                  </td>
                  <td className="num">{v.pages}</td>
                  <td className="num">{v.visits}</td>
                  <td className="small muted tnum" style={{ whiteSpace: "nowrap" }}>{fmtDate(v.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <div className="empty">No visitors match.</div>}
        </div>
      </Card>
    </>
  );
}
