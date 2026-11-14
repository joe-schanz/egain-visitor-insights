import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CATEGORY_LABEL, SOURCE_LABEL, fmt, fmtDate, fmtDuration, fmtMoney, useData } from "../data.js";
import { Card, HBars, TierPill } from "../components.jsx";

function Breakdown({ parts }) {
  const groups = [["Fit", 30], ["Intent", 50], ["Engagement", 20]];
  return (
    <div className="breakdown">
      {groups.map(([g, max]) => {
        const rows = parts.filter((p) => p.group === g);
        const raw = rows.reduce((s, p) => s + p.points, 0);
        return (
          <div key={g}>
            <div className="bd-group-head">
              <span>{g}</span>
              <span className="tnum">{Math.min(raw, max)} <span className="faint">/ {max}</span></span>
            </div>
            {rows.length === 0 && <div className="bd-row faint">No signals</div>}
            {rows.map((p) => (
              <div className="bd-row" key={p.reason}><span>{p.reason}</span><b>+{p.points}</b></div>
            ))}
            {raw > max && <div className="bd-row faint small"><span>Capped at {max}</span></div>}
          </div>
        );
      })}
    </div>
  );
}

function Visit({ v, open, onToggle }) {
  return (
    <div className="visit">
      <button className="visit-head" onClick={onToggle} aria-expanded={open}>
        <span className={`caret${open ? " open" : ""}`}>▶</span>
        <b className="tnum">{fmtDate(v.start, true)}</b>
        <span className="muted">Person {v.visitor}</span>
        <span className="muted">{v.pages.length} page{v.pages.length !== 1 ? "s" : ""} · {fmtDuration(v.duration_sec)}</span>
        <span className="chip">{SOURCE_LABEL[v.source] || v.source}{v.source_host ? `: ${v.source_host}` : ""}</span>
        {v.campaign && <span className="chip strong">Email: {v.campaign}</span>}
        <span className="faint small" style={{ marginLeft: "auto" }}>{v.device} · {v.browser}</span>
      </button>
      {open && (
        <ul className="visit-pages">
          {v.pages.map((p, i) => (
            <li key={i}>
              <span className="faint tnum small">{p.t.slice(11, 16)}</span>
              <span>{p.title}<br /><code>{p.path}</code></span>
              <span className="chip">{CATEGORY_LABEL[p.category] || p.category}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Account() {
  const { key } = useParams();
  const accounts = useData("accounts");
  const [openVisits, setOpenVisits] = useState({ 0: true });
  if (!accounts) return <div className="loading">Loading…</div>;
  const a = accounts.find((x) => x.key === key);
  if (!a) return <div className="empty">Account not found. <Link to="/">Back to accounts</Link></div>;

  const revenue = fmtMoney(a.revenue, a.revenue_currency);
  const cats = Object.entries(a.category_counts)
    .filter(([c]) => !["asset", "probe", "feed"].includes(c))
    .sort((x, y) => y[1] - x[1]).map(([c, v]) => ({ label: CATEGORY_LABEL[c] || c, value: v }));
  const interests = [
    ["Integrations (likely tech stack)", a.integrations, true],
    ["Products", a.products, false],
    ["Industry content", a.industries, false],
  ].filter(([, xs]) => xs.length);

  return (
    <>
      <Link to="/" className="back">← All accounts</Link>
      <Card>
        <div className="dossier-head">
          <div style={{ flex: 1, minWidth: 260 }}>
            <div className="dossier-title">
              <h1>{a.name}</h1>
              <TierPill tier={a.tier} />
              <span className="faint">#{a.rank} of {accounts.length}</span>
            </div>
            <div className="facts">
              <span><b>{a.sector}</b></span>
              {a.employees && <span><b>{fmt(a.employees)}</b> employees</span>}
              {!a.employees && a.size_band !== "Unknown" && <span>{a.size_band}</span>}
              {revenue && <span><b>{revenue}</b> revenue</span>}
              {a.hq && <span>HQ <b>{a.hq}{a.hq_country ? `, ${a.hq_country}` : ""}</b></span>}
              {a.domain && <span><a href={`https://${a.domain}`} target="_blank" rel="noreferrer">{a.domain}</a></span>}
            </div>
            {a.description && <div className="muted small" style={{ marginTop: 6 }}>{a.description[0].toUpperCase() + a.description.slice(1)}</div>}
            {a.flags.map((f) => <div key={f} className="pill flag" style={{ marginTop: 10 }}>⚑ {f}</div>)}
          </div>
          <div className="bigscore">
            <div className="n tnum">{a.score}</div>
            <div className="faint small">score / 100</div>
          </div>
        </div>
        <p className="headline">{a.headline}</p>
      </Card>

      <div className="grid dossier" style={{ marginTop: 16 }}>
        <div>
          <Card title="Talking points" sub="Generated from what this account read on eGain.com">
            <ul className="points">{a.talking_points.map((t) => <li key={t}>{t}</li>)}</ul>
            <div className="action"><strong>Next step</strong><span>{a.next_action}</span></div>
          </Card>

          {interests.length > 0 && (
            <Card title="What they were interested in">
              <div style={{ display: "grid", gap: 14 }}>
                {interests.map(([label, xs, strong]) => (
                  <div key={label}>
                    <h3 style={{ marginBottom: 8 }}>{label}</h3>
                    <div className="chips">
                      {xs.map(([k, n]) => <span key={k} className={`chip${strong ? " strong" : ""}`}>{k} <b>{n}</b></span>)}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Card title="Visit timeline" sub={`${a.visits} visits by ${a.visitors} ${a.visitors === 1 ? "person" : "people"} · newest first${a.visit_log.length < a.visits ? ` · latest ${a.visit_log.length} shown` : ""}`}
                right={<button className="btn-link small" onClick={() => setOpenVisits(
                  Object.keys(openVisits).length > 1 ? {} : Object.fromEntries(a.visit_log.map((_, i) => [i, true])))}>
                  {Object.keys(openVisits).length > 1 ? "Collapse all" : "Expand all"}</button>}>
            {a.visit_log.map((v, i) => (
              <Visit key={i} v={v} open={!!openVisits[i]}
                     onToggle={() => setOpenVisits((o) => { const n = { ...o }; if (n[i]) delete n[i]; else n[i] = true; return n; })} />
            ))}
          </Card>
        </div>

        <div>
          <Card title="Why this score">
            <Breakdown parts={a.breakdown} />
          </Card>

          <Card title="Pages viewed by type">
            <HBars rows={cats} />
          </Card>

          <Card title="Most-viewed pages">
            <HBars rows={a.top_pages.map(([p, n]) => ({ label: p, value: n }))} />
          </Card>

          <Card title="How they were identified">
            <dl className="kv">
              <dt>Evidence</dt><dd>{a.id_evidence}</dd>
              <dt>Network</dt><dd>{a.network_owner || "–"}</dd>
              <dt>Registry name</dt><dd>{a.raw_name}</dd>
              <dt>Visitor IPs</dt><dd className="tnum">{a.ips}</dd>
              <dt>Countries</dt><dd>{a.countries.join(", ") || "–"}</dd>
              <dt>Traffic sources</dt>
              <dd>{Object.entries(a.sources).map(([k, v]) => `${SOURCE_LABEL[k] || k} ${v}`).join(" · ")}</dd>
              <dt>Firmographics</dt>
              <dd>{a.wikidata_id
                ? <a href={`https://www.wikidata.org/wiki/${a.wikidata_id}`} target="_blank" rel="noreferrer">Wikidata {a.wikidata_id}</a>
                : <span className="faint">No reliable match (left blank rather than guessed)</span>}</dd>
              <dt>Active</dt><dd>{fmtDate(a.first_seen)} – {fmtDate(a.last_seen)} · {a.active_days} day{a.active_days !== 1 ? "s" : ""}</dd>
            </dl>
          </Card>

          {a.contacts.length > 0 && (
            <Card title="Known CRM contacts" sub="Campaign-email recipients who clicked from this account's network">
              {a.contacts.map((u) => <div key={u}><Link to={`/contacts?q=${u}`}><code className="small">{u}</code></Link></div>)}
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
