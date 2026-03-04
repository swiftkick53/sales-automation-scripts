# Sales Automation Scripts

Python-based automation tools for sales operations, data processing, and workflow optimization. These scripts power the daily operations of a distributed sales team, transforming raw Salesforce data into actionable intelligence.

## Overview

This repository contains production-ready Python scripts that automate:
- Daily call sheet generation with intelligent prioritization
- Salesforce data export and transformation
- Compensation calculations and tracking
- Performance metrics aggregation
- Email delivery of reports and call lists

**Goal**: Replace manual data processing with reliable, repeatable automation that frees up time for strategy.

## Current Scripts

### 1. `call_sheet_generator.py`
Generates daily prioritized call sheets from Salesforce data using a tiered scoring algorithm.

**What it does**:
- Imports Salesforce export CSV
- Scores prospects based on engagement history, territory, and campaign type
- Applies tiered prioritization (Tier 1, 2, 3)
- Assigns calls to reps based on territory and capacity
- Outputs call sheet as CSV or Excel

**Usage**:
```bash
python call_sheet_generator.py \
  --salesforce_export "data/sf_export.csv" \
  --output_format "excel" \
  --date "2026-03-04"
```

**Key Features**:
- Three-tier prioritization system (high/medium/standard value)
- Territory-aware assignment
- Intelligent sorting for maximum efficiency
- Generates ~200 prioritized calls/day in <30 seconds

**Sample Output**:
```
Rep,Territory,Prospect_Name,Call_Priority,Last_Contact,LTV_Score
Alice,East,ABC Contractors,Tier 1,2026-02-28,8.5
Bob,West,XYZ Services,Tier 1,2026-02-25,7.8
Alice,East,Quick Repairs,Tier 2,2026-01-15,5.2
...
```

### 2. `salesforce_data_processor.py`
Cleans, validates, and transforms raw Salesforce exports into analysis-ready format.

**What it does**:
- Reads multiple Salesforce export files (Accounts, Contacts, Activities, Opportunities)
- Validates data quality and consistency
- Joins data across related objects
- Calculates derived metrics (LTV, engagement score, conversion likelihood)
- Outputs clean master dataset

**Usage**:
```bash
python salesforce_data_processor.py \
  --accounts "data/sf_accounts.csv" \
  --contacts "data/sf_contacts.csv" \
  --activities "data/sf_activities.csv" \
  --output "data/processed_master.csv"
```

**Data Validation**:
- Checks for required fields
- Validates date formats
- Removes duplicates
- Flags suspicious values
- Logs all data quality issues

**Output Includes**:
- Account data with calculated LTV
- Contact history and engagement metrics
- Activity summaries (calls, emails, meetings)
- Opportunity stage and probability
- Derived scoring metrics

### 3. `compensation_calculator.py`
Calculates rep compensation based on flexible, territory-specific rules.

**What it does**:
- Reads sales data and compensation plan rules
- Calculates F98 revenue (retention) and new acquisition separately
- Applies territory-specific multipliers and goals
- Generates compensation statement per rep
- Tracks YTD totals and projected earnings

**Usage**:
```bash
python compensation_calculator.py \
  --sales_data "data/master_sales_log.csv" \
  --comp_plan "config/compensation_rules.json" \
  --period "2026-03"
```

**Compensation Plan Format**:
```json
{
  "territories": {
    "East": {
      "retention_weight": 0.6,
      "acquisition_weight": 0.4,
      "retention_goal": 50000,
      "acquisition_goal": 30000,
      "base_rate": 0.08
    }
  }
}
```

**Output**:
```
Rep,Territory,Retention_Revenue,Acquisition_Revenue,Commission,YTD_Total
Alice,East,48000,25000,6040,18120
Bob,West,52000,28000,6400,19200
...
```

### 4. `daily_report_generator.py`
Generates comprehensive daily performance reports and distributes via email.

**What it does**:
- Aggregates metrics from master data log
- Calculates daily conversion rates, pipeline velocity
- Generates summary statistics and trends
- Creates formatted email with key metrics
- Sends to leadership team automatically

**Usage**:
```bash
python daily_report_generator.py \
  --data_source "data/master_sales_log.csv" \
  --recipient_list "config/recipients.txt" \
  --send True
```

**Report Includes**:
- Daily calls, connects, conversations, conversions
- Conversion rate by campaign type
- Territory performance comparison
- Top performers and struggles
- Weekly/monthly trends
- Forecast vs. actual

### 5. `lead_prioritization_engine.py`
Advanced lead scoring combining multiple factors for intelligent prospect ranking.

**What it does**:
- Calculates engagement score (recency, frequency, interaction types)
- Computes LTV potential based on account characteristics
- Evaluates fit based on industry and company size
- Combines scores into final priority ranking
- Identifies "next best actions" for each prospect

**Scoring Model**:
```
Priority Score = (0.4 × Engagement) + (0.35 × LTV_Potential) + (0.25 × Fit)
```

**Output**:
```
Prospect,Engagement_Score,LTV_Score,Fit_Score,Priority_Rank
ABC Contractors,8.5,7.2,8.0,1
XYZ Services,7.1,8.5,7.5,2
...
```

## Installation

### Requirements
- Python 3.8+
- pandas
- numpy
- python-dotenv (for API keys)
- openpyxl (for Excel output)
- requests (for Salesforce API)

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/sales-automation-scripts.git
cd sales-automation-scripts

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your Salesforce credentials
```

## Configuration

### Salesforce API Setup
1. Create a Salesforce Connected App
2. Get your Client ID and Client Secret
3. Add to `.env`:
```
SALESFORCE_DOMAIN=https://your-instance.salesforce.com
SALESFORCE_CLIENT_ID=your_client_id
SALESFORCE_CLIENT_SECRET=your_client_secret
SALESFORCE_USERNAME=your_username
SALESFORCE_PASSWORD=your_password
```

### Compensation Plan Rules
Edit `config/compensation_rules.json` to match your commission structure:
- Adjust territory multipliers
- Update goals and base rates
- Modify weighting between retention and acquisition

### Call Sheet Preferences
Edit `config/call_sheet_config.json`:
- Tier thresholds
- Territory assignments
- Rep capacity (calls per day)
- Sort preferences

## Workflow Integration

### Automated Daily Execution (via GitHub Actions)

Create `.github/workflows/daily_call_sheet.yml`:

```yaml
name: Daily Call Sheet Generation

on:
  schedule:
    - cron: '0 6 * * 1-5'  # 6 AM on weekdays

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Download Salesforce data
        run: python scripts/download_sf_data.py
      - name: Generate call sheet
        run: python call_sheet_generator.py
      - name: Send email
        run: python scripts/send_email.py
```

### Manual Execution

```bash
# Generate call sheet for today
python call_sheet_generator.py

# Process all data and generate reports
python salesforce_data_processor.py && \
  python compensation_calculator.py && \
  python daily_report_generator.py
```

## Performance Metrics

- **Call Sheet Generation**: ~30 seconds for 200+ prospects
- **Data Processing**: ~2 minutes for 10k+ records
- **Compensation Calculations**: <1 second for 20 reps
- **Report Generation**: ~15 seconds

## Time Impact

| Task | Before | After | Savings |
|------|--------|-------|---------|
| Daily call sheet | 45 min | 1 min | 44 min |
| Data processing | 60 min | 2 min | 58 min |
| Compensation tracking | 30 min | 30 sec | 29.5 min |
| Report generation | 20 min | 15 sec | 19.75 min |
| **Daily Total** | **155 min** | **3.5 min** | **151.5 min** |

## Roadmap

- [ ] Real-time Salesforce API integration (eliminate manual exports)
- [ ] Advanced ML-based lead scoring
- [ ] Predictive pipeline forecasting
- [ ] Slack integration for notifications
- [ ] Web dashboard for real-time metrics
- [ ] A/B testing framework for call scripts
- [ ] Automated rep coaching based on performance patterns

## Code Quality

- Type hints throughout
- Comprehensive docstrings
- Unit tests (run with `pytest`)
- Linting with `pylint`
- Error handling and logging

## Contributing

This is a personal/team project, but happy to discuss approaches or share learnings. Reach out if you're building similar sales automation systems.

## License

MIT License — feel free to adapt and use these approaches in your own sales operations.

---

**Tech Stack**: Python 3.9+, Pandas, NumPy, Salesforce API
**Skills Demonstrated**: Python Development, Data Engineering, API Integration, Process Automation, Sales Operations
