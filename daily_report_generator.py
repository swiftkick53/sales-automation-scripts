"""
Daily Report Generator — Aggregates metrics and produces formatted reports.

Reads the master sales log, computes daily KPIs (conversion rates, pipeline
velocity, top performers), and optionally emails the summary to leadership.

Usage:
    python daily_report_generator.py --data_source data/master_sales_log.csv
    python daily_report_generator.py --data_source data/master_sales_log.csv --send
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class DailyReportGenerator:
    """Generate daily performance reports from the master sales log."""

    def __init__(self, data_path: str):
        self.df = pd.read_csv(data_path)
        self.df["Date"] = pd.to_datetime(self.df["Date"], errors="coerce")
        self.today = datetime.now().date()
        self.report_data = {}

    def compute_daily_metrics(self, target_date=None) -> dict:
        """Compute KPIs for a single day.

        Returns dict with calls, connects, conversions, conversion rate,
        revenue, and per-rep breakdowns.
        """
        target = pd.Timestamp(target_date or self.today)
        day_data = self.df[self.df["Date"].dt.date == target.date()]

        metrics = {
            "date": str(target.date()),
            "total_calls": len(day_data),
            "connects": len(day_data[day_data["Outcome"] == "Connected"]),
            "qualified": len(day_data[day_data["Outcome"] == "Qualified"]),
            "converted": len(day_data[day_data["Outcome"] == "Converted"]),
            "revenue": day_data["Revenue"].sum() if "Revenue" in day_data.columns else 0,
        }

        metrics["conversion_rate"] = (
            round(metrics["converted"] / metrics["total_calls"] * 100, 1)
            if metrics["total_calls"] > 0 else 0.0
        )
        metrics["connect_rate"] = (
            round(metrics["connects"] / metrics["total_calls"] * 100, 1)
            if metrics["total_calls"] > 0 else 0.0
        )

        # Per-rep breakdown
        if not day_data.empty:
            rep_summary = (
                day_data.groupby("Rep_Name")
                .agg(
                    Calls=("Outcome", "count"),
                    Conversions=("Outcome", lambda x: (x == "Converted").sum()),
                    Revenue=("Revenue", "sum") if "Revenue" in day_data.columns
                    else ("Outcome", lambda x: 0),
                )
                .reset_index()
                .sort_values("Conversions", ascending=False)
            )
            metrics["rep_breakdown"] = rep_summary.to_dict("records")
        else:
            metrics["rep_breakdown"] = []

        # Campaign type breakdown
        if "Campaign_Type" in day_data.columns and not day_data.empty:
            campaign = (
                day_data.groupby("Campaign_Type")
                .agg(
                    Calls=("Outcome", "count"),
                    Conversions=("Outcome", lambda x: (x == "Converted").sum()),
                )
                .reset_index()
            )
            metrics["campaign_breakdown"] = campaign.to_dict("records")
        else:
            metrics["campaign_breakdown"] = []

        self.report_data = metrics
        return metrics

    def compute_weekly_trend(self) -> pd.DataFrame:
        """Compute daily totals for the last 7 calendar days."""
        end = pd.Timestamp(self.today)
        start = end - timedelta(days=6)
        week = self.df[
            (self.df["Date"].dt.date >= start.date())
            & (self.df["Date"].dt.date <= end.date())
        ]
        if week.empty:
            return pd.DataFrame()

        trend = (
            week.groupby(week["Date"].dt.date)
            .agg(
                Calls=("Outcome", "count"),
                Conversions=("Outcome", lambda x: (x == "Converted").sum()),
            )
            .reset_index()
        )
        trend["Conversion_Rate"] = (
            (trend["Conversions"] / trend["Calls"] * 100).round(1)
        )
        return trend

    def format_report(self) -> str:
        """Format the daily metrics into a readable text report."""
        m = self.report_data
        if not m:
            return "No report data computed yet."

        lines = [
            f"{'='*55}",
            f"  DAILY SALES REPORT — {m['date']}",
            f"{'='*55}",
            "",
            f"  Total Calls      : {m['total_calls']}",
            f"  Connects         : {m['connects']}  ({m['connect_rate']}%)",
            f"  Qualified        : {m['qualified']}",
            f"  Converted        : {m['converted']}  ({m['conversion_rate']}%)",
            f"  Revenue          : ${m['revenue']:,.2f}",
            "",
        ]

        if m["rep_breakdown"]:
            lines.append("  REP BREAKDOWN:")
            lines.append(f"  {'Rep':<18s} {'Calls':>6s} {'Conv':>6s} {'Rev':>10s}")
            lines.append(f"  {'─'*42}")
            for r in m["rep_breakdown"]:
                rev = r.get("Revenue", 0)
                lines.append(
                    f"  {r['Rep_Name']:<18s} {r['Calls']:>6d} "
                    f"{r['Conversions']:>6d} ${rev:>9,.2f}"
                )
            lines.append("")

        if m["campaign_breakdown"]:
            lines.append("  CAMPAIGN BREAKDOWN:")
            for c in m["campaign_breakdown"]:
                rate = round(c["Conversions"] / c["Calls"] * 100, 1) if c["Calls"] else 0
                lines.append(f"    {c['Campaign_Type']:<25s} {c['Calls']} calls, "
                             f"{c['Conversions']} conv ({rate}%)")
            lines.append("")

        lines.append(f"{'='*55}")
        return "\n".join(lines)

    def save_report(self, output_dir: str = "output") -> str:
        """Save the formatted report to a text file."""
        out = Path(output_dir)
        out.mkdir(exist_ok=True)
        date_str = self.report_data.get("date", str(self.today))
        filename = out / f"daily_report_{date_str}.txt"
        report_text = self.format_report()
        filename.write_text(report_text)
        logger.info("Saved report -> %s", filename)
        return str(filename)


def main():
    parser = argparse.ArgumentParser(description="Generate daily sales report.")
    parser.add_argument("--data_source", required=True, help="Master sales log CSV")
    parser.add_argument("--date", default=None, help="Report date (YYYY-MM-DD)")
    parser.add_argument("--send", action="store_true", help="Send via email (requires SMTP config)")
    args = parser.parse_args()

    gen = DailyReportGenerator(args.data_source)
    gen.compute_daily_metrics(target_date=args.date)
    print(gen.format_report())
    gen.save_report()

    if args.send:
        logger.info("Email sending requires SMTP configuration in .env")


if __name__ == "__main__":
    main()
