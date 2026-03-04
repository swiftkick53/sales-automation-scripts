"""
Compensation Calculator — Territory-specific commission calculations.

Reads sales data and a JSON compensation plan, calculates per-rep commission
for retention (F98) and new acquisition revenue, and outputs statements.

Usage:
    python compensation_calculator.py \
        --sales_data data/master_sales_log.csv \
        --comp_plan config/compensation_rules.json \
        --period 2026-03
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import argparse
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class CompensationCalculator:
    """Calculate rep compensation using territory-specific rules.

    The plan weights F98 revenue (retention) more heavily than new
    acquisition to incentivize customer retention.
    """

    def __init__(self, comp_plan_path: str):
        self.plan = self._load_plan(comp_plan_path)

    def _load_plan(self, path: str) -> dict:
        p = Path(path)
        if not p.exists():
            logger.error("Compensation plan not found: %s", p)
            sys.exit(1)
        with open(p) as f:
            plan = json.load(f)
        logger.info("Loaded compensation plan with %d territories",
                     len(plan.get("territories", {})))
        return plan

    def calculate(self, sales_path: str, period: str) -> pd.DataFrame:
        """Calculate compensation for every rep in the given period.

        Args:
            sales_path: Path to master sales log CSV.
            period: Period string like '2026-03' to filter data.

        Returns:
            DataFrame with per-rep compensation breakdown.
        """
        df = pd.read_csv(sales_path)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        # Filter to the requested period
        df["Period"] = df["Date"].dt.to_period("M").astype(str)
        period_data = df[df["Period"] == period].copy()

        if period_data.empty:
            logger.warning("No data found for period %s", period)
            return pd.DataFrame()

        logger.info("Processing %d records for period %s",
                     len(period_data), period)

        results = []
        for (rep, territory), group in period_data.groupby(["Rep_Name", "Territory"]):
            territory_rules = self.plan.get("territories", {}).get(territory)
            if territory_rules is None:
                logger.warning("No comp rules for territory '%s', using defaults", territory)
                territory_rules = {
                    "retention_weight": 0.6,
                    "acquisition_weight": 0.4,
                    "retention_goal": 50000,
                    "acquisition_goal": 30000,
                    "base_rate": 0.08,
                }

            retention_rev = group.loc[
                group["Revenue_Type"] == "Retention", "Revenue"
            ].sum()
            acquisition_rev = group.loc[
                group["Revenue_Type"] == "Acquisition", "Revenue"
            ].sum()

            retention_commission = retention_rev * territory_rules["base_rate"] * territory_rules["retention_weight"]
            acquisition_commission = acquisition_rev * territory_rules["base_rate"] * territory_rules["acquisition_weight"]
            total_commission = round(retention_commission + acquisition_commission, 2)

            # Goal attainment
            retention_pct = round(retention_rev / territory_rules["retention_goal"] * 100, 1) if territory_rules["retention_goal"] else 0
            acquisition_pct = round(acquisition_rev / territory_rules["acquisition_goal"] * 100, 1) if territory_rules["acquisition_goal"] else 0

            results.append({
                "Rep_Name": rep,
                "Territory": territory,
                "Period": period,
                "Retention_Revenue": retention_rev,
                "Acquisition_Revenue": acquisition_rev,
                "Retention_Commission": round(retention_commission, 2),
                "Acquisition_Commission": round(acquisition_commission, 2),
                "Total_Commission": total_commission,
                "Retention_Goal_Pct": retention_pct,
                "Acquisition_Goal_Pct": acquisition_pct,
            })

        result_df = pd.DataFrame(results)
        result_df = result_df.sort_values("Total_Commission", ascending=False)
        return result_df

    def save_statements(self, results: pd.DataFrame, output_dir: str = "output"):
        """Save compensation results to Excel."""
        out = Path(output_dir)
        out.mkdir(exist_ok=True)

        if results.empty:
            logger.warning("No results to save.")
            return

        period = results["Period"].iloc[0]
        filename = out / f"compensation_{period}.xlsx"
        results.to_excel(filename, index=False, sheet_name="Compensation")
        logger.info("Saved -> %s", filename)

        self._print_summary(results)

    def _print_summary(self, df: pd.DataFrame):
        print(f"\n{'='*60}")
        print(f"  COMPENSATION SUMMARY — {df['Period'].iloc[0]}")
        print(f"{'='*60}")
        for _, row in df.iterrows():
            print(f"  {row['Rep_Name']:<18s} | {row['Territory']:<8s} | "
                  f"Retention ${row['Retention_Revenue']:>8,.0f} | "
                  f"Acquisition ${row['Acquisition_Revenue']:>8,.0f} | "
                  f"Commission ${row['Total_Commission']:>8,.2f}")
        total = df["Total_Commission"].sum()
        print(f"{'─'*60}")
        print(f"  {'TOTAL':<18s} | {'':8s} | {'':>22s} | "
              f"Commission ${total:>8,.2f}")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Calculate sales compensation.")
    parser.add_argument("--sales_data", required=True, help="Master sales log CSV")
    parser.add_argument("--comp_plan", required=True, help="Compensation rules JSON")
    parser.add_argument("--period", required=True, help="Period (YYYY-MM)")
    parser.add_argument("--output", default="output", help="Output directory")
    args = parser.parse_args()

    calc = CompensationCalculator(args.comp_plan)
    results = calc.calculate(args.sales_data, args.period)
    calc.save_statements(results, args.output)


if __name__ == "__main__":
    main()
