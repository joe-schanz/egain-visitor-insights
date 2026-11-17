import { Link } from "react-router-dom";
import { REPO_URL } from "../data.js";
import { Card } from "../components.jsx";

const STEPS = [
  ["Load", "530,423 log lines (Feb 1–25, 2025) converted to Parquet. The log has a 10-day hole (Feb 10–19): two exports joined, confirmed with eGain. Charts show the gap instead of hiding it."],
  ["Remove machines", "Layered rules, first match wins: declared bots, uptime monitors, crawlers, vulnerability probes, a distributed bot using one outdated Chrome version on 54K IPs, and email security gateways that open every link in an email. 82% of traffic is removed; every rule is readable."],
  ["Separate people from scanners in email clicks", "Campaign links carry the recipient's CRM ID. An IP clicking links for 5+ different recipients, or opening 3+ links in the same second, is a scanner. Only 151 of 45,736 'clickers' provably engaged."],
  ["Build visits", "Same IP + browser, 30-minute inactivity timeout (the Google Analytics standard)."],
  ["Identify organizations", "IPinfo Lite (free) names every IP's network owner. When the owner is the organization itself (a bank, an agency), that's the account. On ISP networks, the regional registries (RDAP) often show the business a block is assigned to. Cloud, VPN and proxy networks are excluded; proxy farms that register blocks under innocent-sounding names are caught by behavior."],
  ["Add firmographics", "Wikidata (free, open): industry, headcount, revenue, HQ. Matched by official website first, exact name second, with a country check. No match is left blank, never guessed."],
  ["Score and brief", "Score = Fit (30) + Intent (50) + Engagement (20), with every point explained. Talking points are generated from rules: integrations viewed reveal the likely tech stack, conversion pages mean active evaluation, several people mean a buying group."],
];

const NEXT = [
  ["Commercial identity resolution", "6sense, Demandbase, ZoomInfo or Dealfront plug into the identification step. They resolve home-office, VPN and gateway traffic that free data can't, so far more visits get a company name."],
  ["Live pipeline", "Run nightly on the log stream (or a tag on the site), keep history, and alert account owners in Slack/CRM when an account turns Hot."],
  ["CRM sync", "Match campaign contact IDs and accounts to Dynamics/Salesforce records; show owner, open opportunities and last activity; write the score back to CRM."],
  ["Flag current customers", "Visits from existing customers (support, login and community pages) are flagged: buying signals go to the account manager as upsell leads, help-seeking goes to Support or the CSM, and nobody cold-calls a customer."],
  ["Tune the score on outcomes", "Re-weight Fit/Intent/Engagement against closed-won pipeline once there are labels; keep the explanation."],
  ["First-party identity", "Form fills and authenticated sessions (a cookie ID) would remove most IP guesswork for known contacts."],
  ["Privacy & compliance", "Company-level only, IPs masked in the UI, GDPR/CCPA review, retention limits, opt-out honored."],
];

export default function Method() {
  return (
    <div className="method">
      <div className="page-head">
        <div>
          <h1>How it works</h1>
          <p>A Python pipeline turns the raw weblog into precomputed data; this site is static, fast and free to host. Every design decision, with the numbers behind it, is in the repository's decision log.</p>
        </div>
      </div>
      <div className="grid grid-2">
        <Card title="Pipeline" style={{ marginTop: 0 }}>
          <ol>{STEPS.map(([t, d]) => <li key={t}><b>{t}.</b> <span className="muted">{d}</span></li>)}</ol>
        </Card>
        <div>
          <Card title="What would make it production-grade" style={{ marginTop: 0 }}>
            <ol>{NEXT.map(([t, d]) => <li key={t}><b>{t}.</b> <span className="muted">{d}</span></li>)}</ol>
          </Card>
          <Card title="Stack & cost">
            <dl className="kv">
              <dt>Pipeline</dt><dd>Python, pandas, Parquet</dd>
              <dt>Identification</dt><dd>IPinfo Lite · RDAP (ARIN/RIPE/APNIC …) · Wikidata</dd>
              <dt>Front end</dt><dd>React, Vite, Recharts · static JSON</dd>
              <dt>Hosting</dt><dd>Vercel (free tier)</dd>
              <dt>Total cost</dt><dd><b>$0</b></dd>
            </dl>
            <p style={{ marginBottom: 0 }}>
              <a href={REPO_URL} target="_blank" rel="noreferrer">Source code, README and decision log →</a>
            </p>
          </Card>
        </div>
      </div>
      <p className="small faint" style={{ marginTop: 16 }}>
        Start with the <Link to="/">accounts list</Link>, or open the top account to see a full dossier.
      </p>
    </div>
  );
}
