"""
Call Sheet Generator — Transforms Salesforce data into prioritized daily call lists.

This script:
1. Reads Salesforce export CSV files
2. Scores prospects based on engagement history and LTV potential
3. Applies tiered prioritization (Tier 1 / Tier 2 / Tier 3)
4. Assigns calls to reps based on territory and capacity
5. Outputs call sheet as Excel or CSV

Usage:
    python call_sheet_generator.py --data data/sf_export.csv --output excel
    python call_sheet_generator.py --data data/sf_export.csv --output csv --date 2026-03-04

Author: JB
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import logging
import json
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = "config/call_sheet_config.json"


class CallSheetGenerator:
    """Generate daily prioritized call sheets from Salesforce data.

    Scoring model:
        Priority = (w_engagement × Engagement) + (w_ltv × LTV) + (w_fit × Fit)

    Tier thresholds (configurable):
        Tier 1: combined >= 7.0  (high-value — call first)
        Tier 2: combined >= 4.5  (medium-value)
        Tier 3: everything else  (standard outreach)
    """

    WEIGHT_ENGAGEMENT = 0.40
    WEIGHT_LTV = 0.35
    WEIGHT_FIT = 0.25
    TIER_1_THRESHOLD = 7.0
    TIER_2_THRESHOLD = 4.5
    DEFAULT_CAPACITY = 25

    def __init__(self, data_path: str, config_path: str | None = None):
        """Initialize with Salesforce export file and optional config.

        Args:
            data_path: Path to the Salesforce export CSV.
            config_path: Optional JSON config for thresholds, territories, capacity.
        """
        self.data_path = Path(data_path)
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.config = self._load_config(config_path)
        self.df = self._load_data()

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------

    def _load_config(self, config_path: str | None) -> dict:
        """Load config JSON or return sensible defaults."""
        defaults = {
            "tier_1_threshold": self.TIER_1_THRESHOLD,
            "tier_2_threshold": self.TIER_2_THRESHOLD,
            "weight_engagement": self.WEIGHT_ENGAGEMENT,
            "weight_ltv": self.WEIGHT_LTV,
            "weight_fit": self.WEIGHT_FIT,
            "default_capacity": self.DEFAULT_CAPACITY,
            "territories": {},
        }
        if config_path and Path(config_path).exists():
            with open(config_path, "r") as f:
                loaded = json.load(f)
            defaults.update(loaded)
            logger.info("Loaded config from %s", config_path)
        return defaults

    def _load_data(self) -> pd.DataFrame:
        """Read and validate the Salesforce CSV export."""
        if not self.data_path.exists():
            logger.error("Data file not found: %s", self.data_path)
            sys.exit(1)

        df = pd.read_csv(self.data_path)
        logger.info("Loaded %d records from %s", len(df), self.data_path)

        required = [
            "Prospect_Name", "Rep_Name", "Territory",
            "Campaign_Type", "Last_Contact",
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            logger.error("Missing required columns: %s", missing)
            sys.exit(1)

        df["Last_Contact"] = pd.to_datetime(df["Last_Contact"], errors="coerce")

        for col in ["Total_Interactions", "Company_Size",
                     "Historical_Conversion_Rate", "Revenue_Potential"]:
            if col not in df.columns:
                df[col] = 0
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        return df

    # ------------------------------------------------------------------
    # Scoring engine
    # ------------------------------------------------------------------

    def calculate_engagement_score(self, row: pd.Series) -> float:
        """Score prospect engagement on a 0-10 scale.

        Factors:
            - Recency of last contact (60%)
            - Interaction frequency   (40%)
        """
        if pd.isna(row["Last_Contact"]):
            return 0.0

        days_since = (datetime.now() - row["Last_Contact"]).days
        recency = max(0.0, 10.0 - (days_since / 5.0))
        frequency = min(10.0, row["Total_Interactions"] / 2.0)

        return round((recency * 0.6) + (frequency * 0.4), 2)

    def calculate_ltv_score(self, row: pd.Series) -> float:
        """Score lifetime-value potential on a 0-10 scale.

        Factors:
            - Company size              (40%)
            - Revenue potential          (35%)
            - Historical conversion rate (25%)
        """
        size = min(10.0, row["Company_Size"] / 100.0)
        revenue = min(10.0, row["Revenue_Potential"] / 10000.0)
        conversion = min(10.0, row["Historical_Conversion_Rate"] * 10.0)

        return round((size * 0.40) + (revenue * 0.35) + (conversion * 0.25), 2)

    def calculate_fit_score(self, row: pd.Series) -> float:
        """Score prospect-product fit on a 0-10 scale.

        Uses campaign type as a proxy for purchase intent:
            Subscription Winback  → 8  (high intent)
            Expired with Payment  → 7  (demonstrated willingness)
            Acquisition Winback   → 6
            Other                 → 5
        """
        campaign_scores = {
            "Subscription Winback": 8.0,
            "Acquisition Winback": 6.0,
            "Expired with Payment": 7.0,
        }
        return campaign_scores.get(row.get("Campaign_Type", ""), 5.0)

    def assign_tier(self, combined: float) -> int:
        """Map combined score to priority tier (1 = highest)."""
        if combined >= self.config["tier_1_threshold"]:
            return 1
        elif combined >= self.config["tier_2_threshold"]:
            return 2
        return 3

    # ------------------------------------------------------------------
    # Sheet generation
    # ------------------------------------------------------------------

    def generate(self, output_format: str = "excel",
                 date: str | None = None) -> pd.DataFrame:
        """Score, tier, and sort prospects into a daily call sheet.

        Args:
            output_format: 'excel' or 'csv'.
            date: Date string for the filename (defaults to today).

        Returns:
            Prioritized call sheet DataFrame.
        """
        run_date = date or self.today
        logger.info("Generating call sheet for %s ...", run_date)

        self.df["Engagement_Score"] = self.df.apply(
            self.calculate_engagement_score, axis=1
        )
        self.df["LTV_Score"] = self.df.apply(self.calculate_ltv_score, axis=1)
        self.df["Fit_Score"] = self.df.apply(self.calculate_fit_score, axis=1)

        w = self.config
        self.df["Combined_Score"] = (
            self.df["Engagement_Score"] * w["weight_engagement"]
            + self.df["LTV_Score"] * w["weight_ltv"]
            + self.df["Fit_Score"] * w["weight_fit"]
        ).round(2)

        self.df["Tier"] = self.df["Combined_Score"].apply(self.assign_tier)

        # Sort: tier asc, then combined desc within each tier
        call_sheet = self.df.sort_values(
            ["Tier", "Combined_Score"], ascending=[True, False]
        ).reset_index(drop=True)

        # Cap calls per rep
        capacity = self.config["default_capacity"]
        if capacity:
            call_sheet = (
                call_sheet.groupby("Rep_Name")
                .head(capacity)
                .reset_index(drop=True)
            )

        output_cols = [
            "Rep_Name", "Territory", "Prospect_Name", "Campaign_Type",
            "Tier", "Combined_Score", "Engagement_Score", "LTV_Score",
            "Fit_Score", "Last_Contact",
        ]
        for optional in ["Phone", "Email"]:
            if optional in call_sheet.columns:
                output_cols.append(optional)
        call_sheet = call_sheet[[c for c in output_cols if c in call_sheet.columns]]

        out_dir = Path("output")
        out_dir.mkdir(exist_ok=True)

        if output_format == "excel":
            filename = out_dir / f"call_sheet_{run_date}.xlsx"
            call_sheet.to_excel(filename, index=False, sheet_name="Call Sheet")
        else:
            filename = out_dir / f"call_sheet_{run_date}.csv"
            call_sheet.to_csv(filename, index=False)

        logger.info("Saved -> %s", filename)
        self._print_summary(call_sheet)
        return call_sheet

    def _print_summary(self, sheet: pd.DataFrame) -> None:
        """Print a quick summary to stdout."""
        print(f"\n{'='*50}")
        print(f"  CALL SHEET  —  {self.today}")
        print(f"{'='*50}")
        print(f"  Total prospects : {len(sheet)}")
        print(f"\n  Tier breakdown:")
        for tier, count in sheet["Tier"].value_counts().sort_index().items():
            label = {1: "High", 2: "Medium", 3: "Standard"}.get(tier, "?")
            print(f"    Tier {tier} ({label:>8s}) : {count}")
        print(f"\n  Rep distribution:")
        for rep, count in sheet["Rep_Name"].value_counts().items():
            print(f"    {rep:<20s} : {count} calls")
        print(f"{'='*50}\n")


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate daily prioritized call sheet from Salesforce data."
    )
    parser.add_argument("--data", required=True, help="Path to Salesforce export CSV")
    parser.add_argument(
        "--output", choices=["excel", "csv"], default="excel",
        help="Output format (default: excel)",
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Path to config JSON")
    parser.add_argument("--date", default=None, help="Date for filename (YYYY-MM-DD)")
    args = parser.parse_args()

    generator = CallSheetGenerator(args.data, config_path=args.config)
    generator.generate(output_format=args.output, date=args.date)


if __name__ == "__main__":
    main()
