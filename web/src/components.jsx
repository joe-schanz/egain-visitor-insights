import { fmt } from "./data.js";

export function TierPill({ tier }) {
  return <span className={`pill ${tier.toLowerCase()}`}>{tier === "Hot" ? "▲ " : tier === "Warm" ? "● " : "○ "}{tier}</span>;
}

export function ScoreBar({ score }) {
  return (
    <div className="scorebar" title={`Score ${score} / 100`}>
      <b>{score}</b>
      <div className="scorebar-track"><div className="scorebar-fill" style={{ width: `${score}%` }} /></div>
    </div>
  );
}

export function Kpi({ label, value, note }) {
  return (
    <div className="card kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value tnum">{value}</div>
      {note && <div className="kpi-note">{note}</div>}
    </div>
  );
}

export function Card({ title, sub, right, children, style }) {
  return (
    <section className="card" style={style}>
      {(title || right) && (
        <div className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {sub && <p>{sub}</p>}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

/** Horizontal bar list: one hue (magnitude), value labels on every bar, native tooltip. */
export function HBars({ rows, accent = false, format = fmt, max }) {
  const m = max ?? Math.max(...rows.map((r) => r.value), 1);
  return (
    <div className="hbars">
      {rows.map((r) => (
        <div className="hbar" key={r.label} title={`${r.label}: ${format(r.value)}`}>
          <div className="hbar-label">{r.label}</div>
          <div className="hbar-track">
            <div className={`hbar-fill${accent ? " accent" : ""}`} style={{ width: `${(r.value / m) * 100}%` }} />
          </div>
          <div className="hbar-val">{format(r.value)}</div>
        </div>
      ))}
    </div>
  );
}

export function SortTh({ k, label, sort, setSort, num }) {
  const active = sort.key === k;
  return (
    <th className={`sortable${num ? " num" : ""}`}
        onClick={() => setSort({ key: k, dir: active && sort.dir === "desc" ? "asc" : "desc" })}
        aria-sort={active ? (sort.dir === "desc" ? "descending" : "ascending") : "none"}>
      {label}{active ? (sort.dir === "desc" ? " ↓" : " ↑") : ""}
    </th>
  );
}

export function sortRows(rows, { key, dir }) {
  const s = [...rows].sort((a, b) => {
    const x = a[key], y = b[key];
    if (typeof x === "string") return x.localeCompare(y);
    return (x ?? -Infinity) - (y ?? -Infinity);
  });
  return dir === "desc" ? s.reverse() : s;
}
