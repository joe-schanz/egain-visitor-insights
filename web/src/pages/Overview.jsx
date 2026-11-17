import { Bar, BarChart, CartesianGrid, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CATEGORY_LABEL, SOURCE_LABEL, fmt, useData } from "../data.js";
import { Card, HBars } from "../components.jsx";

const CLASS_LABEL = {
  bot_distributed: "Distributed bot (one fake Chrome on 54K IPs)", email_scanner: "Email security scanners",
  bot_declared: "Self-declared bots & scripts", human: "Humans", crawler: "Crawlers & scrapers",
  monitor: "Uptime / page monitors", probe: "Vulnerability probes", bot_suspected: "Legacy-browser bots",
  asset: "Static files",
};
const NET_LABEL = {
  hosting: "Cloud, VPN & proxy networks", isp: "Internet providers (unidentified)",
  unverified: "Unrecognized networks", security_proxy: "Enterprise security gateways",
  organization: "Organizations' own networks", egain: "eGain's own offices",
};
const SERIES = [["human", "Humans", "var(--series-1)"], ["email_scanner", "Email scanners", "var(--series-2)"], ["bot", "Other bots", "var(--series-3)"]];

function DailyTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="tooltip">
      <div className="tooltip-title">{new Date(label + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })}</div>
      {d.in_gap ? <div className="muted">No data in the log export</div> :
        [...payload].reverse().map((p) => (
          <div className="tooltip-row" key={p.dataKey}><span>{p.name}</span><b>{fmt(p.value)}</b></div>
        ))}
    </div>
  );
}

export default function Overview() {
  const o = useData("overview");
  if (!o) return <div className="loading">Loading…</div>;
  const total = Object.values(o.traffic_classes).reduce((s, v) => s + v, 0);
  const funnelMax = o.funnel[0].value;
  const gapDays = o.daily.filter((d) => d.in_gap).map((d) => d.date);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Traffic &amp; data quality</h1>
          <p>
            Before any insight, the noise has to go. {Math.round((1 - o.traffic_classes.human / total) * 100)}% of eGain.com's
            logged traffic is not a person. Every class below was removed with readable rules (see How it works).
          </p>
        </div>
      </div>

      <Card title="From raw log to named accounts" sub="Each step keeps only what a rep can trust">
        <div className="funnel">
          {o.funnel.map((f) => (
            <div className="funnel-row" key={f.label} title={`${f.label}: ${fmt(f.value)}`}>
              <div className="muted">{f.label}</div>
              <div className="funnel-track"><div className="funnel-bar" style={{ width: `${Math.max(0.4, (f.value / funnelMax) * 100)}%` }} /></div>
              <div className="tnum" style={{ textAlign: "right", fontWeight: 600 }}>{fmt(f.value)}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Daily traffic by type" sub="Hits per day (UTC). The log has no data for Feb 10–19: two exports joined, ~14 days covered.">
        <div className="legend">
          {SERIES.map(([k, l, c]) => <span key={k}><i style={{ background: c }} />{l}</span>)}
          <span><i style={{ background: "var(--surface-2)", border: "1px dashed var(--text-3)" }} />No data (export gap)</span>
        </div>
        <div style={{ height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={o.daily} margin={{ left: 0, right: 8, top: 8, bottom: 0 }} barCategoryGap={3}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="date" tickFormatter={(d) => d.slice(8).replace(/^0/, "")} tick={{ fill: "var(--text-3)", fontSize: 12 }}
                     axisLine={{ stroke: "var(--border)" }} tickLine={false} interval={0} />
              <YAxis tickFormatter={(v) => (v >= 1000 ? `${v / 1000}K` : v)} tick={{ fill: "var(--text-3)", fontSize: 12 }} axisLine={false} tickLine={false} width={40} />
              <ReferenceArea x1={gapDays[0]} x2={gapDays[gapDays.length - 1]} fill="var(--surface-2)" fillOpacity={1}
                             stroke="var(--text-3)" strokeDasharray="4 4" strokeOpacity={0.5}
                             label={{ value: "No data in export", fill: "var(--text-3)", fontSize: 12, position: "center" }} />
              <Tooltip content={<DailyTip />} cursor={{ fill: "var(--surface-2)" }} />
              {SERIES.map(([k, l, c], i) => (
                <Bar key={k} dataKey={k} name={l} stackId="d" fill={c} stroke="var(--surface)" strokeWidth={1}
                     radius={i === SERIES.length - 1 ? [4, 4, 0, 0] : 0} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="small faint" style={{ marginTop: 6 }}>Feb 6 and Feb 20 spikes are campaign send days, almost all scanner clicks.</div>
      </Card>

      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <Card title="What made up the 530K hits" sub="Hits by traffic class" style={{ marginTop: 0 }}>
          <HBars rows={Object.entries(o.traffic_classes).map(([k, v]) => ({ label: CLASS_LABEL[k] || k, value: v }))} />
        </Card>
        <Card title="Who the human visitors are" sub="Human visitor IPs by network owner" style={{ marginTop: 0 }}>
          <HBars rows={Object.entries(o.network_types).map(([k, v]) => ({ label: NET_LABEL[k] || k, value: v }))} />
        </Card>
        <Card title="Integration interest" sub="Human visits that viewed an integration page: the prospect's likely platform" style={{ marginTop: 0 }}>
          <HBars accent rows={o.integration_interest.map(([k, v]) => ({ label: k, value: v }))} />
        </Card>
        <Card title="What humans read" sub="Human page views by content type" style={{ marginTop: 0 }}>
          <HBars rows={Object.entries(o.categories).map(([k, v]) => ({ label: CATEGORY_LABEL[k] || k, value: v }))} />
        </Card>
        <Card title="How humans arrived" sub="Visits by traffic source" style={{ marginTop: 0 }}>
          <HBars rows={Object.entries(o.referrers).map(([k, v]) => ({ label: SOURCE_LABEL[k] || k, value: v }))} />
        </Card>
        <Card title="Top pages (human, excluding noise)" style={{ marginTop: 0 }}>
          <HBars rows={o.top_pages.slice(0, 12).map(([p, , n]) => ({ label: p, value: n }))} />
        </Card>
      </div>
    </>
  );
}
