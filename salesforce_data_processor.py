"""
Salesforce Data Processor — Cleans, validates, and transforms raw SF exports.

Reads multiple Salesforce export CSVs (Accounts, Contacts, Activities),
joins them into a single analysis-ready master dataset with derived metrics.

Usage:
    python salesforce_data_processor.py \
        --accounts data/sf_accounts.csv \
        --contacts data/sf_contacts.csv \
        --activities data/sf_activities.csv \
        --output data/processed_master.csv
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class SalesforceDataProcessor:
    """Clean, validate, and merge Salesforce export files."""

    def __init__(self):
        self.accounts = None
        self.contacts = None
        self.activities = None
        self.master = None
        self.quality_log: list[str] = []

    def load_accounts(self, path: str) -> pd.DataFrame:
        df = self._read_csv(path, "Accounts")
        self._check_required(df, ["Account_ID", "Account_Name", "Territory"], "Accounts")
        df = self._deduplicate(df, "Account_ID", "Accounts")
        df = self._validate_dates(df, ["Created_Date", "Last_Activity_Date"])
        self.accounts = df
        return df

    def load_contacts(self, path: str) -> pd.DataFrame:
        df = self._read_csv(path, "Contacts")
        self._check_required(df, ["Contact_ID", "Account_ID", "Full_Name"], "Contacts")
        df = self._deduplicate(df, "Contact_ID", "Contacts")
        self.contacts = df
        return df

    def load_activities(self, path: str) -> pd.DataFrame:
        df = self._read_csv(path, "Activities")
        self._check_required(df, ["Activity_ID", "Account_ID", "Activity_Type", "Activity_Date"], "Activities")
        df = self._validate_dates(df, ["Activity_Date"])
        self.activities = df
        return df

    def _compute_activity_summary(self) -> pd.DataFrame:
        if self.activities is None:
            return pd.DataFrame()
        return (
            self.activities.groupby("Account_ID")
            .agg(
                Total_Interactions=("Activity_ID", "count"),
                Last_Contact=("Activity_Date", "max"),
                First_Contact=("Activity_Date", "min"),
                Calls=("Activity_Type", lambda x: (x == "Call").sum()),
                Emails=("Activity_Type", lambda x: (x == "Email").sum()),
                Meetings=("Activity_Type", lambda x: (x == "Meeting").sum()),
            )
            .reset_index()
        )

    def build_master(self) -> pd.DataFrame:
        if self.accounts is None:
            logger.error("Accounts not loaded.")
            sys.exit(1)

        master = self.accounts.copy()

        if self.contacts is not None:
            primary = (
                self.contacts.sort_values("Contact_ID")
                .drop_duplicates(subset="Account_ID", keep="first")
            )
            master = master.merge(
                primary[["Account_ID", "Full_Name", "Phone", "Email"]],
                on="Account_ID", how="left",
            )

        if self.activities is not None:
            master = master.merge(
                self._compute_activity_summary(), on="Account_ID", how="left"
            )

        for col in ["Total_Interactions", "Calls", "Emails", "Meetings",
                     "Company_Size", "Revenue_Potential"]:
            if col in master.columns:
                master[col] = master[col].fillna(0).astype(int)

        self.master = master
        logger.info("Master dataset: %d rows, %d columns", len(master), len(master.columns))
        return master

    def save(self, output_path: str) -> None:
        if self.master is None:
            logger.error("Master dataset not built yet.")
            return
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self.master.to_csv(output_path, index=False)
        logger.info("Saved -> %s", output_path)

    def print_quality_report(self) -> None:
        if not self.quality_log:
            print("No data quality issues found.")
            return
        print(f"\n{'='*50}")
        print("  DATA QUALITY REPORT")
        print(f"{'='*50}")
        for issue in self.quality_log:
            print(f"  - {issue}")
        print(f"{'='*50}\n")

    # --- Helpers ---

    def _read_csv(self, path, label):
        p = Path(path)
        if not p.exists():
            logger.error("%s not found: %s", label, p)
            sys.exit(1)
        df = pd.read_csv(p)
        logger.info("Loaded %s: %d rows", label, len(df))
        return df

    def _check_required(self, df, cols, label):
        missing = [c for c in cols if c not in df.columns]
        if missing:
            logger.error("%s missing columns: %s", label, missing)
            sys.exit(1)

    def _deduplicate(self, df, key, label):
        dupes = df.duplicated(subset=key).sum()
        if dupes:
            self.quality_log.append(f"{label}: removed {dupes} duplicate(s) on {key}")
            df = df.drop_duplicates(subset=key, keep="first")
        return df

    def _validate_dates(self, df, cols):
        for col in cols:
            if col in df.columns:
                before = df[col].notna().sum()
                df[col] = pd.to_datetime(df[col], errors="coerce")
                bad = before - df[col].notna().sum()
                if bad:
                    self.quality_log.append(f"Coerced {bad} invalid date(s) in {col}")
        return df


def main():
    parser = argparse.ArgumentParser(description="Process Salesforce exports.")
    parser.add_argument("--accounts", required=True)
    parser.add_argument("--contacts", default=None)
    parser.add_argument("--activities", default=None)
    parser.add_argument("--output", default="data/processed_master.csv")
    args = parser.parse_args()

    proc = SalesforceDataProcessor()
    proc.load_accounts(args.accounts)
    if args.contacts:
        proc.load_contacts(args.contacts)
    if args.activities:
        proc.load_activities(args.activities)
    proc.build_master()
    proc.save(args.output)
    proc.print_quality_report()


if __name__ == "__main__":
    main()
