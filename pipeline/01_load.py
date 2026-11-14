"""Step 1 — Load the raw Excel weblog into a typed Parquet file.

Why: the .xlsx takes ~60s to parse every time; Parquet loads in under a second
and keeps column types, so every later step iterates quickly.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = sorted((ROOT / "data" / "raw").glob("*.xlsx"))
OUT = ROOT / "data" / "interim" / "hits.parquet"

COLS = {
    "IP": "ip",
    "Domain": "domain",
    "Date & Time (UTC)": "ts_raw",
    "Request Type": "method",
    "Page URL": "url",
    "Referral URL": "referrer",
    "User Agent": "user_agent",
}


def main() -> None:
    frames = []
    for f in RAW:  # supports a "file 2" if eGain sends one
        df = pd.read_excel(f, dtype=str).rename(columns=COLS)
        df["source_file"] = f.name
        frames.append(df)
        print(f"loaded {f.name}: {len(df):,} rows")
    df = pd.concat(frames, ignore_index=True)

    for c in ["ip", "domain", "url", "referrer", "user_agent"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    df["ts"] = pd.to_datetime(df["ts_raw"], format="%d/%b/%Y:%H:%M:%S", utc=True)
    df = df.drop(columns=["ts_raw"]).sort_values("ts").reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(df):,} rows, {df.ip.nunique():,} IPs, "
          f"{df.ts.min()} -> {df.ts.max()}")


if __name__ == "__main__":
    main()
