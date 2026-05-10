# XRTM Team Workflows

This guide documents realistic multi-user and desk-style workflows for XRTM, based on institutional user studies. It shows what teams can accomplish today using XRTM's existing features—profiles, runs, exports, and conventions—while being transparent about current limitations.

## Status: Current Capabilities and Honest Limitations

**What XRTM provides today:**
- Local-first architecture with comprehensive run artifacts
- Profile system for reproducible analyst workflows
- Built-in performance metrics (Brier scores, calibration)
- Structured JSON export plus custom downstream transforms when teams need CSV or database reshaping
- Event streams for run-level audit trails
- Command-line automation capabilities

**What XRTM does NOT provide (yet):**
- Built-in user management or attribution
- Shared database or aggregation layer
- Access control, quotas, or role-based permissions
- Multi-user concurrency features
- Team dashboards or consolidated reporting
- Audit trails across users (only per-run events)

**Team deployment reality:** Teams can productively use XRTM today by combining existing features with conventions and modest custom integration. This requires 2-4 weeks of initial engineering for institutional deployment, but the foundation is solid.

---

## Team Workflow Pattern: Prediction Desk

This pattern is based on a macro research team study where analysts needed consistent forecast generation, performance tracking, and shared results.

### Pattern Overview

**Audience:** 3-10 analysts on a prediction desk, macro research team, or risk assessment group

**Team Goals:**
- Consistent forecast generation across analysts
- Performance tracking and comparison
- Reproducible workflows
- Export to shared reporting systems
- Basic audit capability

**What This Pattern Uses:**
- Named profiles per analyst
- Structured run directories
- Export to shared database (custom integration)
- File system conventions for attribution
- Scripted aggregation

---

## Setup: Team Environment

### 1. Shared Installation

Each analyst works in the same Python environment or uses identical virtual environments:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install xrtm==0.3.2
xrtm doctor
```

### 2. Analyst Profiles

Create a profile for each team member to ensure consistent settings:

```bash
# Analyst profiles with naming convention
xrtm profile create analyst-jane --provider mock --limit 10 --runs-dir runs
xrtm profile create analyst-bob --provider mock --limit 10 --runs-dir runs
xrtm profile create analyst-maria --provider mock --limit 10 --runs-dir runs
```

**Convention:** Use consistent profile naming like `analyst-<name>` so you can identify who ran what.

List all team profiles:

```bash
xrtm profile list
```

### 3. Shared Runs Directory

All analysts write to a shared `runs/` directory. Use file system permissions to control access:

```bash
mkdir -p runs
chmod 770 runs  # Team-writable
```

---

## Daily Workflow: Analyst Operations

### Running Forecasts

Each analyst runs forecasts using their profile:

```bash
source .venv/bin/activate
xrtm run profile analyst-jane
```

**Output example:**
```
Run: runs/20260501T101710Z-d8967e54
Forecast records: 10
Eval Brier: 0.287334
Duration: 0.124s
```

**Key information to record:**
- Run ID: `20260501T101710Z-d8967e54`
- Analyst: `analyst-jane` (from profile used)
- Timestamp: embedded in run ID
- Performance: Brier score 0.287334

**Best practice:** Document run IDs in your notes or ticket system for later reference.

### Reviewing Your Forecasts

View run details:

```bash
xrtm runs show runs/20260501T101710Z-d8967e54
```

Generate HTML report:

```bash
xrtm report html runs/20260501T101710Z-d8967e54
```

This opens a comprehensive report in your browser with:
- All forecasts and reasoning
- Calibration plots
- Brier score breakdown
- Event timeline

### Comparing Performance

Compare two runs (yours or between analysts):

```bash
xrtm runs compare runs/20260501T101710Z-d8967e54 runs/20260501T102315Z-ab123cd4
```

This shows differences in:
- Forecast counts
- Brier scores
- Provider settings
- Duration
- Warnings/errors

---

## Data Export and Aggregation

### Individual Run Export

Released `xrtm runs export` supports both JSON and CSV in `0.3.1`:

```bash
xrtm runs export runs/20260501T101710Z-d8967e54 --output exports/jane-2026-05-01.json
xrtm runs export runs/20260501T101710Z-d8967e54 --output exports/jane-2026-05-01.csv --format csv
```

Use JSON as the full-fidelity integration bundle, and use CSV when you need quick spreadsheet-friendly rows.

### Team Database Integration

XRTM does not provide a built-in shared database, but the structured export format makes custom integration straightforward.

**Example integration script** (based on prediction desk study):

```python
#!/usr/bin/env python3
"""Import XRTM runs into team database."""
import json
import sqlite3
from pathlib import Path

def setup_team_database(db_path="team_forecasts.db"):
    """Create shared database schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analyst TEXT NOT NULL,
            run_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            question_title TEXT,
            probability REAL NOT NULL,
            reasoning TEXT,
            recorded_at TIMESTAMP NOT NULL,
            brier_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS run_metadata (
            run_id TEXT PRIMARY KEY,
            analyst TEXT NOT NULL,
            provider TEXT NOT NULL,
            forecast_count INTEGER,
            eval_brier REAL,
            total_seconds REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    return conn

def import_xrtm_run(conn, analyst_name, run_dir):
    """Import an XRTM run into the team database."""
    run_path = Path(run_dir)
    
    # Load run summary
    with open(run_path / "run_summary.json") as f:
        summary = json.load(f)
    
    # Load forecasts
    forecasts = []
    with open(run_path / "forecasts.jsonl") as f:
        for line in f:
            forecasts.append(json.loads(line))
    
    # Load questions
    questions = {}
    with open(run_path / "questions.jsonl") as f:
        for line in f:
            q = json.loads(line)
            questions[q["id"]] = q
    
    cursor = conn.cursor()
    
    # Insert run metadata
    cursor.execute("""
        INSERT INTO run_metadata 
        (run_id, analyst, provider, forecast_count, eval_brier, total_seconds)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        run_path.name,
        analyst_name,
        summary.get("provider", "unknown"),
        summary.get("forecast_count", 0),
        summary.get("eval", {}).get("brier_score"),
        summary.get("duration_seconds")
    ))
    
    # Insert forecasts
    for fc in forecasts:
        question_id = fc["question_id"]
        question = questions.get(question_id, {})
        
        cursor.execute("""
            INSERT INTO forecasts 
            (analyst, run_id, question_id, question_title, 
             probability, reasoning, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            analyst_name,
            run_path.name,
            question_id,
            question.get("title", "Unknown"),
            fc["output"]["probability"],
            fc["output"]["reasoning"],
            fc["recorded_at"]
        ))
    
    conn.commit()
    print(f"✓ Imported {len(forecasts)} forecasts from {analyst_name}")

if __name__ == "__main__":
    conn = setup_team_database("team_forecasts.db")
    
    # Import runs - adjust paths as needed
    import_xrtm_run(conn, "analyst-jane", "runs/20260501T101710Z-d8967e54")
    import_xrtm_run(conn, "analyst-bob", "runs/20260501T102315Z-ab123cd4")
    
    conn.close()
```

### Team Performance Reporting

Once data is in a shared database, generate team reports:

```sql
-- Analyst performance summary
SELECT analyst, 
       COUNT(*) as total_forecasts,
       AVG(eval_brier) as avg_brier
FROM run_metadata
GROUP BY analyst
ORDER BY avg_brier ASC;

-- Recent activity
SELECT analyst, run_id, forecast_count, eval_brier, created_at
FROM run_metadata
ORDER BY created_at DESC
LIMIT 10;

-- Forecast distribution
SELECT analyst, question_title, AVG(probability) as avg_prob
FROM forecasts
GROUP BY analyst, question_title
ORDER BY question_title, analyst;
```

---

## Workflow Conventions

Since XRTM doesn't have built-in user management, teams use these conventions:

### 1. Profile Naming

**Pattern:** `analyst-<name>` or `desk-<name>`

Example:
```bash
xrtm profile create analyst-jane --provider mock --limit 10
xrtm profile create analyst-bob --provider openai --limit 20
```

### 2. Run Tracking

**Maintain a spreadsheet or ticket system** mapping:
- Run ID → Analyst
- Run ID → Purpose/ticket
- Run ID → Date
- Run ID → Key findings

Example log:

| Run ID | Analyst | Date | Purpose | Brier |
|--------|---------|------|---------|-------|
| 20260501T101710Z-d8967e54 | jane | 2026-05-01 | Weekly forecast | 0.287 |
| 20260501T102315Z-ab123cd4 | bob | 2026-05-01 | Quarterly review | 0.312 |

### 3. Export Conventions

**Directory structure:**
```
exports/
  2026-05/
    jane/
      2026-05-01-weekly.json
      2026-05-01-weekly.csv
    bob/
      2026-05-01-quarterly.json
```

### 4. Shared Runs Directory

**File system layout:**
```
runs/
  20260501T101710Z-d8967e54/   # Jane's run
  20260501T102315Z-ab123cd4/   # Bob's run
  20260501T143722Z-ef567gh8/   # Maria's run
```

**Access control:** Use file system permissions or network shares to manage who can read/write runs.

---

## Review and Collaboration Flow

### Peer Review Process

1. **Analyst generates forecast:**
   ```bash
   xrtm run profile analyst-jane
   # Note run ID: runs/20260501T101710Z-d8967e54
   ```

2. **Analyst exports for review:**
   ```bash
   xrtm runs export runs/20260501T101710Z-d8967e54 --output reviews/jane-2026-05-01.json
   ```

3. **Reviewer examines forecasts:**
   ```bash
   xrtm runs show runs/20260501T101710Z-d8967e54
   xrtm report html runs/20260501T101710Z-d8967e54
   ```

4. **Team compares approaches:**
   ```bash
   xrtm runs compare runs/20260501T101710Z-d8967e54 runs/20260501T102315Z-ab123cd4
   ```

### Weekly Team Review

**Workflow:**

1. Each analyst runs weekly forecasts using their profile
2. Export results to shared location
3. Import into team database (using script above)
4. Generate team performance report
5. Discuss calibration and Brier scores
6. Adjust strategies for next week

**Example team meeting script:**

```bash
#!/bin/bash
# Weekly team review automation

# List all runs from this week
xrtm runs list --runs-dir runs | grep "2026-05-01"

# Export each analyst's latest run
for analyst in jane bob maria; do
    # Find latest run for analyst (using naming convention)
    run_id=$(xrtm runs list --runs-dir runs | grep $analyst | head -1 | awk '{print $1}')
    xrtm runs export runs/$run_id --output exports/$analyst-weekly.json
done

# Import to team database
python import_team_runs.py

# Generate performance report
sqlite3 team_forecasts.db "SELECT analyst, AVG(eval_brier) FROM run_metadata WHERE created_at > date('now', '-7 days') GROUP BY analyst;"
```

---

## Audit and Compliance

### Run-Level Audit Trail

Each run includes `events.jsonl` with timestamped events:

```bash
cat runs/20260501T101710Z-d8967e54/events.jsonl | jq .
```

**Event types available:**
- `run_started`
- `provider_request_started`
- `provider_request_completed`
- `forecast_written`
- `eval_completed`
- `warning`
- `error`

**Example event:**
```json
{
  "schema_version": "xrtm.events.v1",
  "event_id": "evt_abc123",
  "timestamp": "2026-05-01T10:17:10.123Z",
  "event_type": "forecast_written",
  "forecast_id": "fc_xyz789",
  "question_id": "q_123"
}
```

### Cross-Run Audit

**Current limitation:** No built-in cross-run audit view.

**Workaround:** Aggregate events from all runs:

```bash
#!/bin/bash
# Aggregate all events into single audit log

for run_dir in runs/*/; do
    analyst=$(basename $run_dir | cut -d'-' -f1)  # Extract from run ID
    cat "$run_dir/events.jsonl" | jq -c ". + {analyst: \"$analyst\", run_id: \"$(basename $run_dir)\"}"
done > team_audit.jsonl
```

Then query with `jq` or import into database for compliance reporting.

---

## Production Deployment Patterns

### Pattern 1: Shared File System

**Architecture:**
- Network file share (NFS, CIFS, or cloud storage)
- All analysts mount same `runs/` directory
- Use file locks for concurrency safety

**Pros:**
- Simple setup
- No custom backend needed
- Works with existing infrastructure

**Cons:**
- No real-time collaboration features
- Requires good network connectivity
- File permission management needed

**Setup:**
```bash
# Mount shared storage
sudo mount -t nfs server:/xrtm/runs /mnt/xrtm-runs

# Configure XRTM to use shared directory
xrtm profile create analyst-jane --provider mock --runs-dir /mnt/xrtm-runs
```

### Pattern 2: Centralized Database

**Architecture:**
- XRTM runs locally per analyst
- Export results to central database (PostgreSQL/MySQL)
- BI tools query database for reports

**Pros:**
- Better for large teams (10+ analysts)
- Enables rich queries and dashboards
- Supports compliance requirements

**Cons:**
- Requires custom integration code (2-4 weeks)
- Additional infrastructure (database server)
- Maintenance overhead

**Setup:** Use the integration script pattern shown earlier, adapted for PostgreSQL:

```python
import psycopg2

conn = psycopg2.connect("postgresql://user:pass@server/xrtm_team")
# ... same schema and import logic as SQLite example
```

### Pattern 3: Hybrid (Local + Export)

**Architecture:**
- Each analyst works in local `runs/` directory
- Scheduled export to shared system (nightly cron)
- Centralized reporting on exported data

**Pros:**
- Analysts have fast local workflows
- Network outages don't block work
- Flexible aggregation options

**Cons:**
- Not real-time
- Sync complexity
- Potential for conflicts

**Setup:**
```bash
# Cron job for each analyst
0 2 * * * /usr/local/bin/xrtm-export-daily.sh
```

```bash
#!/bin/bash
# xrtm-export-daily.sh
# Export yesterday's runs to shared database

ANALYST="jane"
YESTERDAY=$(date -d "yesterday" +%Y%m%d)

for run_dir in runs/${YESTERDAY}*; do
    xrtm runs export $run_dir --output /mnt/shared/exports/${ANALYST}-$(basename $run_dir).json
done

python /usr/local/bin/import_to_team_db.py /mnt/shared/exports/
```

---

## Cost Management

**Current limitation:** XRTM does not track API costs per user.

**Workarounds:**

### 1. Profile-Based Estimation

Track which profiles use which providers:

```bash
# List all profiles and their providers
xrtm profile list | grep provider
```

Map runs to costs:

```python
# Estimate costs from run_summary.json
import json

def estimate_cost(run_dir):
    with open(f"{run_dir}/run_summary.json") as f:
        summary = json.load(f)
    
    provider = summary.get("provider")
    total_tokens = summary.get("token_total", 0)
    
    # Example pricing (adjust for your provider)
    if provider == "openai":
        cost = total_tokens * 0.00002  # $0.02 per 1K tokens
    else:
        cost = 0.0
    
    return cost

# Total cost for analyst
analyst_runs = ["runs/20260501T101710Z-d8967e54", ...]
total_cost = sum(estimate_cost(r) for r in analyst_runs)
```

### 2. Quota Enforcement via Wrapper Script

Wrap `xrtm run` with quota checking:

```bash
#!/bin/bash
# xrtm-quota-run.sh
# Check quota before running forecast

ANALYST=$1
PROFILE=$2
QUOTA_FILE="/var/xrtm/quotas/${ANALYST}.quota"

current=$(cat $QUOTA_FILE)
if [ "$current" -le 0 ]; then
    echo "ERROR: Quota exceeded for $ANALYST"
    exit 1
fi

xrtm run profile $PROFILE

# Decrement quota
echo $((current - 1)) > $QUOTA_FILE
```

---

## Monitoring and Alerts

**Current limitation:** No built-in team monitoring dashboard.

**Workarounds:**

### Monitor Individual Forecasts

Use XRTM's built-in monitor for key forecasts:

```bash
xrtm monitor start --provider mock --limit 5 --runs-dir runs
xrtm monitor daemon runs/20260501T101710Z-d8967e54 --cycles 10 --interval-seconds 3600
```

### Aggregate Monitoring

Build custom monitoring using exported data:

```python
#!/usr/bin/env python3
"""Team forecast monitoring."""
import sqlite3
from datetime import datetime, timedelta

def check_team_health(db_path="team_forecasts.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check: Any analyst without forecasts in last 24 hours?
    cursor.execute("""
        SELECT analyst, MAX(created_at) as last_run
        FROM run_metadata
        GROUP BY analyst
    """)
    
    alerts = []
    for analyst, last_run in cursor.fetchall():
        if datetime.fromisoformat(last_run) < datetime.now() - timedelta(days=1):
            alerts.append(f"⚠️  {analyst} has not run forecasts in 24 hours")
    
    # Check: Any runs with high error rates?
    cursor.execute("""
        SELECT run_id, analyst 
        FROM run_metadata 
        WHERE eval_brier > 0.5
        ORDER BY created_at DESC
        LIMIT 5
    """)
    
    for run_id, analyst in cursor.fetchall():
        alerts.append(f"⚠️  {analyst} has high Brier score in {run_id}")
    
    return alerts

if __name__ == "__main__":
    alerts = check_team_health()
    if alerts:
        print("TEAM FORECAST ALERTS:")
        for alert in alerts:
            print(alert)
        # Send to Slack, email, etc.
```

---

## Best Practices

### 1. Profile Discipline

- Create one profile per analyst
- Use consistent naming: `analyst-<name>`
- Document provider and limit settings
- Review profiles monthly for consistency

### 2. Run Documentation

- Note run IDs in tickets/notes
- Tag significant runs with descriptive exports
- Archive old runs regularly (use `xrtm artifacts cleanup`)

### 3. Export Regularly

- Export important runs to durable storage
- Use JSON export as the released interchange format
- Add CSV or warehouse transforms in your own integration layer when needed

### 4. Review Cadence

- Daily: Individual forecast review
- Weekly: Team performance comparison
- Monthly: Calibration analysis across analysts

### 5. Audit Trail

- Preserve `events.jsonl` for compliance
- Aggregate events into central audit log
- Retain run artifacts per retention policy

---

## Troubleshooting Team Issues

### Problem: Can't identify who ran a forecast

**Cause:** XRTM doesn't track user in run metadata.

**Solution:** Use profile naming convention and maintain external mapping:

```bash
# Create mapping file
echo "20260501T101710Z-d8967e54,analyst-jane" >> run_mapping.csv
```

### Problem: Multiple analysts modifying same run directory

**Cause:** No file locking in XRTM.

**Solution:** Use separate `runs/` directories per analyst:

```bash
xrtm profile create analyst-jane --runs-dir runs/jane
xrtm profile create analyst-bob --runs-dir runs/bob
```

Then aggregate exports into shared database.

### Problem: Team database schema out of sync

**Cause:** XRTM artifact schemas can evolve.

**Solution:** Version your integration scripts:

```python
def import_run_v1(run_dir):
    # Handle xrtm.run-summary.v1 schema
    pass

def import_run_v2(run_dir):
    # Handle xrtm.run-summary.v2 schema
    pass

def import_run(run_dir):
    with open(f"{run_dir}/run_summary.json") as f:
        summary = json.load(f)
    
    version = summary.get("schema_version", "xrtm.run-summary.v1")
    
    if version == "xrtm.run-summary.v1":
        return import_run_v1(run_dir)
    elif version == "xrtm.run-summary.v2":
        return import_run_v2(run_dir)
```

### Problem: Need spreadsheet-friendly rows

**Cause:** Teams often need spreadsheet-friendly rows in addition to the canonical JSON artifact bundle.

**Released path:** use the built-in CSV export for quick spreadsheet follow-up, or keep JSON as the full-fidelity bundle for deeper ETL:

```bash
xrtm runs export runs/20260501T101710Z-d8967e54 --output team-export.csv --format csv
xrtm runs export runs/20260501T101710Z-d8967e54 --output full-data.json
```

---

## Roadmap: Future Team Features

**This section acknowledges features XRTM does not provide today but may in future releases.**

**Under consideration (not committed):**
- Built-in user attribution (`--user` flag)
- Shared database backend option
- Team dashboard in WebUI
- Role-based access control
- Quota management
- Cross-run audit queries
- Cost tracking per user

**Current status:** User attribution and built-in multi-user control-plane features are still not in XRTM v0.3.2. Teams must use the patterns documented above.

---

## Summary

Teams can productively use XRTM today by combining:

1. **Profiles** for consistent analyst workflows
2. **Export** to shared database (custom integration)
3. **Conventions** for attribution and tracking
4. **File system** or scheduled aggregation for sharing

**Effort estimate:** 2-4 weeks for initial institutional deployment with custom database integration.

**Benefits:**
- Local-first architecture (fast, private)
- Comprehensive audit trail per run
- Built-in evaluation metrics
- Reproducible workflows
- Clean export formats

**Limitations to accept:**
- No built-in user management
- No shared database (custom integration required)
- No real-time collaboration features
- Manual tracking of analyst attribution

**When to adopt:**
- You have engineering resources for integration
- Local-first architecture fits your compliance needs
- Team size is 3-10 analysts (manageable with conventions)
- You value evaluation metrics and reproducibility

**When to wait:**
- You need out-of-box team features
- You require real-time collaboration
- Your team is 20+ analysts (harder to manage with conventions)
- You can't invest in custom integration

---

## Additional Resources

- **Operator Runbook:** `docs/operator-runbook.md` - Single-user workflows
- **Python API Reference:** `docs/python-api-reference.md` - Programmatic access
- **Team Study Artifacts:** `audience-studies/prediction-desk/` - Real team study findings
- **Example Integration Script:** `audience-studies/prediction-desk/team-workflow-demo.py`

For questions or to share your team workflow patterns, see XRTM community channels.
