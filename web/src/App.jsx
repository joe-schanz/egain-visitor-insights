import { useEffect } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import Accounts from "./pages/Accounts.jsx";
import Account from "./pages/Account.jsx";
import Contacts from "./pages/Contacts.jsx";
import Visitors from "./pages/Visitors.jsx";
import Overview from "./pages/Overview.jsx";
import Method from "./pages/Method.jsx";

import { REPO_URL } from "./data.js";

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

export default function App() {
  return (
    <>
      <ScrollTop />
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand">
            <span className="brand-mark">
              <svg width="16" height="16" viewBox="0 0 32 32" aria-hidden="true">
                <path d="M6 22l6-7 5 5 9-11" stroke="white" strokeWidth="3.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            Visitor Insights <small>for eGain sales</small>
          </Link>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>Accounts</NavLink>
            <NavLink to="/contacts">Email contacts</NavLink>
            <NavLink to="/visitors">Anonymous visitors</NavLink>
            <NavLink to="/overview">Traffic &amp; data quality</NavLink>
            <NavLink to="/method">How it works</NavLink>
          </nav>
          <div className="topbar-meta">eGain.com weblog · Feb 1–25, 2025 · <a href="/logout">Sign out</a></div>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Accounts />} />
          <Route path="/account/:key" element={<Account />} />
          <Route path="/contacts" element={<Contacts />} />
          <Route path="/visitors" element={<Visitors />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/method" element={<Method />} />
          <Route path="*" element={<div className="empty">Page not found. <Link to="/">Back to accounts</Link></div>} />
        </Routes>
        <div className="foot">
          Prototype built from 530,423 log lines · identification by IPinfo Lite, RDAP and Wikidata ·{" "}
          <a href={REPO_URL} target="_blank" rel="noreferrer">Source on GitHub</a>
        </div>
      </main>
    </>
  );
}
