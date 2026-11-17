# eGain Visitor Insights

**Which companies are researching eGain, what they care about, and who sales should call this week**, built from
a few weeks of eGain.com weblogs using only free data.

**Live prototype:** https://egain-visitor-insights.vercel.app

Built as a take-home exercise for eGain's Senior Sales Engineer role. Total cost to build and host: **$0**.

---

## What a sales rep gets

- **Call this week:** the eight Hot accounts at the top of the page, each with the single strongest reason, such as
  "Viewed the demo request form" or "Came from the Genesys app marketplace".
- **Searchable account list:** search by company, domain, page or integration. Filter by tier, sector, company size,
  visitor country and interest (for example everyone who researched the Genesys integration). Filters live in the
  URL, so any view can be bookmarked or shared.
- **Account dossier:** a one-line summary, talking points, a next step and the score with every point explained.
  It also shows what the account read, a visit timeline grouped by person, and how the company was identified.
- **Email contacts:** campaign clicks split into security-scanner clicks and real people. It includes a follow-up
  list of the contacts who actually engaged.
- **Anonymous visitors:** high-intent visitors on networks that free data can't name.
- **Traffic & data quality:** the cleaning funnel and daily traffic, with the gap in the data shown, as a sanity
  check for anyone using the numbers.

## What the data showed

| | |
|---|---|
| Raw log lines | 530,423 from 91,288 IPs, Feb 1–25, 2025 |
| Machine traffic removed | **82%** of hits: bots, crawlers, monitors, probes and email security scanners |
| Human page views | 95,547 from 30,083 IPs, in 62,217 visits |
| Email "clickers" | 45,736 recipients, but only **151** clicked and then read on; 40,676 were scanner clicks only |
| Missing data | Feb 10–19: two exports joined (confirmed with eGain); about 14 real days |
| Identified organizations | **218**: 8 Hot, 45 Warm, 165 Cold |

## How it works

A Python pipeline does all the processing offline and writes four JSON files. The website is a static React app
that reads them, so there is no server to run and nothing to pay for.

| Step | Script | What it does |
|---|---|---|
| 1. Load | `pipeline/01_load.py` | Reads the Excel weblog into Parquet so later steps run in seconds. |
| 2. Clean | `pipeline/02_clean.py` | Labels every hit with one traffic class (first matching rule wins), separates email-scanner clicks from people, and builds visits (same IP and browser, 30-minute timeout). |
| 3. Identify | `pipeline/03_identify.py` | IPinfo Lite names the owner of every IP's network. For ISP networks, RDAP (the public registry lookup) names the business a block is assigned to. Cloud, VPN and proxy networks are excluded, including proxy farms caught by their behavior. |
| 4. Enrich | `pipeline/04_enrich.py` | Wikidata adds industry, headcount, revenue and HQ, matched by official website first, then exact name with a country check. No match is left blank rather than guessed. |
| 5. Score | `pipeline/05_score.py` | Score = Fit (30) + Intent (50) + Engagement (20). Hot needs 60+ **and** a target sector. Writes talking points from rules and exports the JSON for the site. |

Shared rule sets live in `pipeline/taxonomy.py` (page categories and intent weights) and `pipeline/networks.py`
(network types).

**Every design decision**, with the numbers behind it and the alternatives rejected, is in
[`docs/DECISIONS.md`](docs/DECISIONS.md).

## Repository layout

```
pipeline/            Python steps 01–05 plus shared rules
docs/DECISIONS.md    decision log (D-001 … D-017)
data/processed/      cleaning_report.json (funnel numbers)
web/                 React + Vite app; web/public/data/ holds the generated JSON
requirements.txt     Python dependencies
```

Raw logs, intermediate files and lookup caches (`data/raw`, `data/interim`, `data/reference`) are git-ignored. The
weblog is eGain's data and is not published here.

## Run it yourself

**Prerequisites:** Python 3.9+, Node 18+, the weblog `.xlsx`, and a free IPinfo account.

1. Set up Python:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
   ```
2. Put the weblog in `data/raw/` (any `.xlsx` file name).
3. Download the free IPinfo Lite database to `data/reference/ipinfo_lite.mmdb`. Sign up at ipinfo.io, then use the
   download link on your dashboard. Keep the token out of the repo (`.env` is git-ignored).
4. Run the pipeline in order:
   ```bash
   python pipeline/01_load.py
   python pipeline/02_clean.py
   python pipeline/03_identify.py --rdap-budget 7000
   python pipeline/04_enrich.py
   python pipeline/05_score.py
   ```
   Step 3 makes about one RDAP lookup per second, so a first full run takes a couple of hours. Results are cached
   in `data/reference/`, so reruns are fast. The other steps take seconds to a minute.
5. Run the site:
   ```bash
   cd web && npm install && npm run dev
   ```

**Deployment:** Vercel (free Hobby plan), root directory `web`, Vite preset. Every push to `main` redeploys.
`web/vercel.json` sends deep links such as `/account/…` to the app.

## Limits, and the path to production

Free data finds the strongest signals but can't name everyone. About two thirds of human visitor IPs are on cloud,
VPN or proxy networks. Of 30,083 human visitor IPs, 10,054 are on networks that can be identified, and 218
organizations came out of those.

1. **Commercial identity data** (6sense, Demandbase, ZoomInfo or Dealfront) plugs into step 3 to name home-office
   and proxy traffic.
2. **CRM sync** (Dynamics or Salesforce). Campaign links already carry the CRM contact ID, so this adds real
   contact names, the account owner and open opportunities, and writes the score back to the account.
3. **Live pipeline and alerts:** nightly runs with history, plus a Slack or CRM alert when an account turns Hot.
4. **Flag current customers:** buying signals from existing customers go to the account manager as upsell leads,
   and help-seeking goes to Support, so nobody cold-calls a customer.
5. **Tune the score** against closed-won deals, keeping every point explainable.
6. **Access and privacy:** SSO login, company-level data only, a GDPR and CCPA review, and retention limits.

## Privacy

The app shows company-level data only, and visitor IP addresses are masked (`16.98.8.x`). Every page and data file
sits behind a sign-in page (`web/middleware.js`, run by Vercel in front of each request): an @egain.com email address
plus a shared password kept in the `SITE_PASSWORD` environment variable, never in the code. Sessions last 7 days, and
changing the password signs everyone out. A production version would use eGain's single sign-on instead.

## Stack

Python 3.9 · pandas · PyArrow · maxminddb · IPinfo Lite · RDAP · Wikidata · React 19 · Vite 6 · Recharts ·
React Router · Vercel
