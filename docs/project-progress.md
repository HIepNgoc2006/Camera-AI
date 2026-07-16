# Live project progress reporting

The progress report reads current GitHub and local Git metadata instead of trusting a committed
snapshot. It never reads issue bodies, comments, workflow logs, artifacts, `.env` files, or business
data, and it does not persist a local report by default.

## Local commands

Run from the repository root with an authenticated GitHub CLI session:

```powershell
rtk .\.venv\Scripts\python.exe scripts/project_status.py
rtk .\.venv\Scripts\python.exe scripts/project_status.py --format json
rtk .\.venv\Scripts\python.exe scripts/project_status.py --strict
```

Use `--repo OWNER/NAME` when the repository cannot be inferred by `gh repo view`. The command needs
read-only network access to issue, milestone, pull request, and Actions metadata. It does not install
or download tools.

The text report includes:

- active and deferred issue totals;
- completion by active milestone;
- the Ready, In Progress, Blocked, and Needs Decision lanes;
- open pull requests and the latest five workflow runs on `main`;
- the current branch, dirty path count, and relation to `origin/main`;
- tracking-policy findings and missing milestone due dates.

JSON output has `schema_version: 1` and is intended for later dashboard integration. Treat field
additions as backward compatible; increment the schema version before removing or changing existing
field meanings.

## Policy behavior

The reporter enforces the repository's one-developer execution policy:

- exactly one open issue must be Ready;
- no more than one open issue may be In Progress;
- Ready and In Progress issues require an assignee;
- an issue cannot be both Ready and In Progress;
- deferred issues cannot carry Critical, High, Ready, In Progress, or Blocked labels.

Normal mode reports findings but still produces the summary. `--strict` returns exit code `2` when an
error-severity policy finding exists. Missing milestone due dates are warnings because the reporter
must not invent a schedule; progress can be measured, but on-time/late status remains unavailable.

Command or schema failures return exit code `1`. Captured command output is intentionally omitted
from errors so a failing external command cannot expose metadata or credentials through this tool.

## Automated history

`.github/workflows/project-progress.yml` runs every Monday at 01:17 UTC (08:17 Asia/Bangkok) and on
manual dispatch. Each run writes the live text report to the GitHub Actions job summary, so workflow
history provides dated progress records without committing generated snapshots to the repository.

The workflow has read-only access to Actions, repository contents, issues, and pull requests. Report
titles and links remain repository metadata and must never contain personal, biometric, evidence,
camera credential, raw payload, or secret values.
