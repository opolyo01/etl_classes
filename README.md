# Foothill ETL + MCP

## Run the ETL

### One quarter at a time

Set `FOOTHILL_QUARTER` in `.env`:

```
FOOTHILL_QUARTER=2026W
FOOTHILL_DEPT=every
```

Then run:

```
uv run main.py
```

### Multiple quarters (comma-separated)

Set `FOOTHILL_QUARTERS` in `.env`:

```
FOOTHILL_QUARTERS=2026W,2026S
FOOTHILL_DEPT=every
```

Then run:

```
uv run main.py
```

The ETL upserts by CRN, so re-running updates existing rows.

## Claude Desktop (MCP)

1) Make sure dependencies are installed:

```
uv sync
```

2) Configure Claude Desktop:

Edit:

```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Paste:

```json
{
  "mcpServers": {
    "foothill-schedule": {
      "command": "~/foothill_etl/.venv/bin/python",
      "args": ["~/foothill_etl/mcp_server.py"],
      "cwd": "~/foothill_etl"
    }
  }
}
```

3) Restart Claude Desktop.

### Example prompts

- "Suggest 5 calculus sections for Spring 2026, prefer in-person"
- "Show MATH classes taught by PUGH on TTh mornings"
- "Build a Spring 2026 schedule for CS 2C, CS 3C (C++), and MATH 2B (Linear Algebra)"
- "Find CS classes with `days_time` containing 'MW' and `room` containing 'Online'"
- "List 10 MATH 2B sections and include ratings"
- "Show instructors with the highest ratings for Linear Algebra"
- "Search for 'python' in titles across all departments"
- "Find classes matching `modality=Online` and `query=calculus`"
- "Look up professor ratings for 'LITRUS, MATTHEW'"

### Optional RMP ratings (POC)

Set the school ID for RateMyProfessors (unofficial):

```
RMP_SCHOOL_ID=YOUR_SCHOOL_ID
```

Then call:

- `suggest_classes(..., include_ratings=true)`
- `lookup_professor_ratings(instructor="LAST, FIRST")`
