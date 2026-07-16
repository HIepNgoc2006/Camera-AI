"""Report live delivery progress from sanitized GitHub and local Git metadata."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

Command = tuple[str, ...]
Runner = Callable[[Command], str]

ACTIVE_SCOPE = "scope:active-delivery"
DEFERRED_SCOPE = "scope:deferred"
READY = "status:ready"
IN_PROGRESS = "status:in-progress"
BLOCKED = "status:blocked"
NEEDS_DECISION = "status:needs-decision"
ISSUE_LIMIT = 1000
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class ReportError(RuntimeError):
    """A stable error that intentionally excludes captured command output."""


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    state: str
    milestone: str
    labels: tuple[str, ...]
    assignees: tuple[str, ...]
    url: str

    def public(self) -> dict[str, object]:
        return {
            "number": self.number,
            "title": self.title,
            "milestone": self.milestone,
            "assignees": list(self.assignees),
            "url": self.url,
        }


@dataclass(frozen=True)
class Phase:
    title: str
    total: int
    open: int
    closed: int
    completion_percent: float
    due_on: str | None

    def public(self) -> dict[str, object]:
        return {
            "title": self.title,
            "total": self.total,
            "open": self.open,
            "closed": self.closed,
            "completion_percent": self.completion_percent,
            "due_on": self.due_on,
        }


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    draft: bool
    head: str
    url: str

    def public(self) -> dict[str, object]:
        return {
            "number": self.number,
            "title": self.title,
            "draft": self.draft,
            "head": self.head,
            "url": self.url,
        }


@dataclass(frozen=True)
class WorkflowRun:
    workflow: str
    status: str
    conclusion: str
    created_at: str
    url: str

    def public(self) -> dict[str, object]:
        return {
            "workflow": self.workflow,
            "status": self.status,
            "conclusion": self.conclusion,
            "created_at": self.created_at,
            "url": self.url,
        }


@dataclass(frozen=True)
class GitState:
    branch: str
    dirty_paths: int
    ahead_of_main: int
    behind_main: int

    def public(self) -> dict[str, object]:
        return {
            "branch": self.branch,
            "clean": self.dirty_paths == 0,
            "dirty_paths": self.dirty_paths,
            "ahead_of_main": self.ahead_of_main,
            "behind_main": self.behind_main,
        }


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str

    def public(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "message": self.message}


@dataclass(frozen=True)
class ProjectReport:
    generated_at: str
    repository: str
    active_issues: tuple[Issue, ...]
    deferred_issues: tuple[Issue, ...]
    phases: tuple[Phase, ...]
    ready: tuple[Issue, ...]
    in_progress: tuple[Issue, ...]
    blocked: tuple[Issue, ...]
    needs_decision: tuple[Issue, ...]
    open_pull_requests: tuple[PullRequest, ...]
    main_runs: tuple[WorkflowRun, ...]
    git: GitState
    findings: tuple[Finding, ...]

    def public(self) -> dict[str, object]:
        active_open = sum(issue.state == "OPEN" for issue in self.active_issues)
        active_closed = len(self.active_issues) - active_open
        deferred_open = sum(issue.state == "OPEN" for issue in self.deferred_issues)
        deferred_closed = len(self.deferred_issues) - deferred_open
        missing_due_dates = [
            phase.title for phase in self.phases if phase.open and not phase.due_on
        ]
        return {
            "schema_version": 1,
            "generated_at": self.generated_at,
            "repository": self.repository,
            "source": {"github": "live", "snapshot_persisted": False},
            "scope": {
                "active": _count_summary(len(self.active_issues), active_open, active_closed),
                "deferred": _count_summary(
                    len(self.deferred_issues), deferred_open, deferred_closed
                ),
            },
            "phases": [phase.public() for phase in self.phases],
            "schedule": {
                "status": "not_assessable" if missing_due_dates else "assessable",
                "missing_due_dates": missing_due_dates,
            },
            "lanes": {
                "ready": [issue.public() for issue in self.ready],
                "in_progress": [issue.public() for issue in self.in_progress],
                "blocked": [issue.public() for issue in self.blocked],
                "needs_decision": [issue.public() for issue in self.needs_decision],
            },
            "delivery": {
                "open_pull_requests": [item.public() for item in self.open_pull_requests],
                "latest_main_runs": [item.public() for item in self.main_runs],
            },
            "local_git": self.git.public(),
            "findings": [finding.public() for finding in self.findings],
        }


class SubprocessRunner:
    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd

    def __call__(self, command: Command) -> str:
        return run_command(command, self.cwd)


def run_command(command: Command, cwd: Path) -> str:
    """Run a metadata command without surfacing its captured output on failure."""

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise ReportError(f"required command unavailable: {command[0]}") from exc
    if completed.returncode != 0:
        action = " ".join(command[:2])
        raise ReportError(f"metadata command failed: {action}")
    return completed.stdout


def _json(command: Command, runner: Runner) -> object:
    try:
        return cast(object, json.loads(runner(command)))
    except json.JSONDecodeError as exc:
        raise ReportError(
            f"metadata command returned invalid JSON: {' '.join(command[:2])}"
        ) from exc


def _mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ReportError(f"invalid metadata shape: {context}")
    return cast(dict[str, object], value)


def _list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise ReportError(f"invalid metadata shape: {context}")
    return cast(list[object], value)


def _string(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise ReportError(f"invalid metadata field: {context}")
    return value


def _integer(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReportError(f"invalid metadata field: {context}")
    return value


def _boolean(value: object, context: str) -> bool:
    if not isinstance(value, bool):
        raise ReportError(f"invalid metadata field: {context}")
    return value


def _optional_string(value: object, context: str) -> str | None:
    if value is None:
        return None
    return _string(value, context)


def _parse_issue(value: object) -> Issue:
    data = _mapping(value, "issue")
    milestone_value = data.get("milestone")
    milestone = "No milestone"
    if milestone_value is not None:
        milestone = _string(_mapping(milestone_value, "issue milestone").get("title"), "title")

    labels = tuple(
        _string(_mapping(label, "issue label").get("name"), "label name")
        for label in _list(data.get("labels", []), "issue labels")
    )
    assignees = tuple(
        _string(_mapping(assignee, "issue assignee").get("login"), "assignee login")
        for assignee in _list(data.get("assignees", []), "issue assignees")
    )
    return Issue(
        number=_integer(data.get("number"), "issue number"),
        title=_string(data.get("title"), "issue title"),
        state=_string(data.get("state"), "issue state").upper(),
        milestone=milestone,
        labels=labels,
        assignees=assignees,
        url=_string(data.get("url"), "issue url"),
    )


def load_issues(repo: str, scope: str, runner: Runner) -> tuple[Issue, ...]:
    fields = "number,title,state,labels,milestone,assignees,url"
    raw = _json(
        (
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--search",
            f"label:{scope}",
            "--limit",
            str(ISSUE_LIMIT),
            "--json",
            fields,
        ),
        runner,
    )
    return tuple(_parse_issue(item) for item in _list(raw, f"{scope} issues"))


def load_milestone_due_dates(repo: str, runner: Runner) -> dict[str, str | None]:
    raw = _json(("gh", "api", f"repos/{repo}/milestones?state=all&per_page=100"), runner)
    due_dates: dict[str, str | None] = {}
    for value in _list(raw, "milestones"):
        milestone = _mapping(value, "milestone")
        title = _string(milestone.get("title"), "milestone title")
        due_dates[title] = _optional_string(milestone.get("due_on"), "milestone due date")
    return due_dates


def load_pull_requests(repo: str, runner: Runner) -> tuple[PullRequest, ...]:
    raw = _json(
        (
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,title,isDraft,headRefName,url",
        ),
        runner,
    )
    pull_requests: list[PullRequest] = []
    for value in _list(raw, "pull requests"):
        item = _mapping(value, "pull request")
        pull_requests.append(
            PullRequest(
                number=_integer(item.get("number"), "pull request number"),
                title=_string(item.get("title"), "pull request title"),
                draft=_boolean(item.get("isDraft"), "pull request draft"),
                head=_string(item.get("headRefName"), "pull request head"),
                url=_string(item.get("url"), "pull request url"),
            )
        )
    return tuple(pull_requests)


def load_main_runs(repo: str, main_branch: str, runner: Runner) -> tuple[WorkflowRun, ...]:
    raw = _json(
        (
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--branch",
            main_branch,
            "--limit",
            "5",
            "--json",
            "workflowName,status,conclusion,createdAt,url",
        ),
        runner,
    )
    runs: list[WorkflowRun] = []
    for value in _list(raw, "workflow runs"):
        item = _mapping(value, "workflow run")
        runs.append(
            WorkflowRun(
                workflow=_string(item.get("workflowName"), "workflow name"),
                status=_string(item.get("status"), "workflow status"),
                conclusion=_string(item.get("conclusion"), "workflow conclusion"),
                created_at=_string(item.get("createdAt"), "workflow created at"),
                url=_string(item.get("url"), "workflow url"),
            )
        )
    return tuple(runs)


def load_git_state(main_branch: str, runner: Runner) -> GitState:
    branch = runner(("git", "branch", "--show-current")).strip() or "detached"
    status = runner(("git", "status", "--porcelain=v1", "--untracked-files=normal"))
    dirty_paths = len([line for line in status.splitlines() if line.strip()])
    relation = runner(
        ("git", "rev-list", "--left-right", "--count", f"origin/{main_branch}...HEAD")
    ).split()
    if len(relation) != 2:
        raise ReportError("invalid metadata field: git main relation")
    try:
        behind, ahead = (int(value) for value in relation)
    except ValueError as exc:
        raise ReportError("invalid metadata field: git main relation") from exc
    return GitState(branch, dirty_paths, ahead, behind)


def _phase_sort_key(title: str) -> tuple[int, str]:
    match = re.match(r"^M(\d+)\b", title)
    return (int(match.group(1)), title) if match else (sys.maxsize, title)


def build_phases(issues: Sequence[Issue], due_dates: Mapping[str, str | None]) -> tuple[Phase, ...]:
    grouped: defaultdict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        grouped[issue.milestone].append(issue)
    phases: list[Phase] = []
    for title in sorted(grouped, key=_phase_sort_key):
        phase_issues = grouped[title]
        closed = sum(issue.state == "CLOSED" for issue in phase_issues)
        total = len(phase_issues)
        phases.append(
            Phase(
                title=title,
                total=total,
                open=total - closed,
                closed=closed,
                completion_percent=_percent(closed, total),
                due_on=due_dates.get(title),
            )
        )
    return tuple(phases)


def _issues_in_lane(issues: Sequence[Issue], label: str) -> tuple[Issue, ...]:
    return tuple(issue for issue in issues if issue.state == "OPEN" and label in issue.labels)


def evaluate_findings(
    active: Sequence[Issue],
    deferred: Sequence[Issue],
    phases: Sequence[Phase],
    ready: Sequence[Issue],
    in_progress: Sequence[Issue],
    main_runs: Sequence[WorkflowRun],
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    if len(ready) != 1:
        findings.append(
            Finding("READY_COUNT", "error", f"expected exactly 1 Ready issue; found {len(ready)}")
        )
    if len(in_progress) > 1:
        findings.append(
            Finding(
                "IN_PROGRESS_LIMIT",
                "error",
                f"expected at most 1 In Progress issue; found {len(in_progress)}",
            )
        )
    for issue in (*ready, *in_progress):
        if not issue.assignees:
            findings.append(
                Finding(
                    "LANE_UNASSIGNED",
                    "error",
                    f"issue #{issue.number} is in an execution lane without an assignee",
                )
            )
        if READY in issue.labels and IN_PROGRESS in issue.labels:
            findings.append(
                Finding(
                    "LANE_CONFLICT",
                    "error",
                    f"issue #{issue.number} is both Ready and In Progress",
                )
            )

    prohibited_deferred = {
        "priority:critical",
        "priority:high",
        READY,
        IN_PROGRESS,
        BLOCKED,
    }
    for issue in deferred:
        invalid = sorted(prohibited_deferred.intersection(issue.labels))
        if invalid:
            findings.append(
                Finding(
                    "DEFERRED_LANE_POLICY",
                    "error",
                    f"deferred issue #{issue.number} has prohibited labels: {', '.join(invalid)}",
                )
            )

    missing_due_dates = [phase.title for phase in phases if phase.open and not phase.due_on]
    if missing_due_dates:
        findings.append(
            Finding(
                "MILESTONE_DUE_DATES",
                "warning",
                "schedule cannot be assessed; open milestones without due dates: "
                + ", ".join(missing_due_dates),
            )
        )
    if len(active) >= ISSUE_LIMIT or len(deferred) >= ISSUE_LIMIT:
        findings.append(
            Finding(
                "ISSUE_QUERY_LIMIT",
                "warning",
                f"an issue query reached the configured limit of {ISSUE_LIMIT}",
            )
        )
    if not main_runs:
        findings.append(
            Finding("MAIN_CI_MISSING", "warning", "no workflow runs were found for main")
        )
    return tuple(findings)


def build_report(
    repo: str,
    main_branch: str,
    runner: Runner,
    generated_at: str | None = None,
) -> ProjectReport:
    validate_repo(repo)
    active = load_issues(repo, ACTIVE_SCOPE, runner)
    deferred = load_issues(repo, DEFERRED_SCOPE, runner)
    phases = build_phases(active, load_milestone_due_dates(repo, runner))
    ready = _issues_in_lane(active, READY)
    in_progress = _issues_in_lane(active, IN_PROGRESS)
    blocked = _issues_in_lane(active, BLOCKED)
    needs_decision = _issues_in_lane(active, NEEDS_DECISION)
    pull_requests = load_pull_requests(repo, runner)
    main_runs = load_main_runs(repo, main_branch, runner)
    git_state = load_git_state(main_branch, runner)
    findings = evaluate_findings(active, deferred, phases, ready, in_progress, main_runs)
    timestamp = generated_at or datetime.now(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    return ProjectReport(
        timestamp,
        repo,
        active,
        deferred,
        phases,
        ready,
        in_progress,
        blocked,
        needs_decision,
        pull_requests,
        main_runs,
        git_state,
        findings,
    )


def _percent(closed: int, total: int) -> float:
    return round((closed / total) * 100, 1) if total else 0.0


def _count_summary(total: int, open_count: int, closed: int) -> dict[str, object]:
    return {
        "total": total,
        "open": open_count,
        "closed": closed,
        "completion_percent": _percent(closed, total),
    }


def _render_lane(name: str, issues: Sequence[Issue]) -> list[str]:
    lines = [f"{name} ({len(issues)})"]
    if not issues:
        return [*lines, "  none"]
    for issue in issues:
        assignees = ",".join(issue.assignees) if issue.assignees else "UNASSIGNED"
        lines.append(f"  #{issue.number} [{issue.milestone}] {issue.title} (assignee={assignees})")
    return lines


def render_text(report: ProjectReport) -> str:
    active_open = sum(issue.state == "OPEN" for issue in report.active_issues)
    active_closed = len(report.active_issues) - active_open
    deferred_open = sum(issue.state == "OPEN" for issue in report.deferred_issues)
    deferred_closed = len(report.deferred_issues) - deferred_open
    lines = [
        "Project progress (live)",
        f"Repository: {report.repository}",
        f"Generated: {report.generated_at}",
        "Source: live GitHub metadata; no snapshot persisted",
        "",
        "Scope",
        (
            f"  Active: {active_closed}/{len(report.active_issues)} closed "
            f"({_percent(active_closed, len(report.active_issues)):.1f}%), {active_open} open"
        ),
        (
            f"  Deferred: {deferred_closed}/{len(report.deferred_issues)} closed "
            f"({_percent(deferred_closed, len(report.deferred_issues)):.1f}%), {deferred_open} open"
        ),
        "",
        "Phases",
    ]
    for phase in report.phases:
        due = phase.due_on or "unset"
        lines.append(
            f"  {phase.title}: {phase.closed}/{phase.total} closed "
            f"({phase.completion_percent:.1f}%), {phase.open} open, due={due}"
        )
    lines.extend(["", "Execution lanes"])
    for name, issues in (
        ("In Progress", report.in_progress),
        ("Ready", report.ready),
        ("Blocked", report.blocked),
        ("Needs Decision", report.needs_decision),
    ):
        lines.extend(_render_lane(name, issues))

    lines.extend(["", "Delivery", f"  Open PRs: {len(report.open_pull_requests)}"])
    for pull_request in report.open_pull_requests:
        draft = " draft" if pull_request.draft else ""
        lines.append(
            f"  PR #{pull_request.number}{draft}: {pull_request.title} ({pull_request.head})"
        )
    lines.append("  Latest main CI:")
    if not report.main_runs:
        lines.append("    none")
    for run in report.main_runs:
        result = run.conclusion or run.status
        lines.append(f"    {run.workflow}: {result} at {run.created_at}")

    lines.extend(
        [
            "",
            "Local Git",
            (
                f"  branch={report.git.branch} clean={str(report.git.dirty_paths == 0).lower()} "
                f"dirty_paths={report.git.dirty_paths} ahead={report.git.ahead_of_main} "
                f"behind={report.git.behind_main}"
            ),
            "",
            f"Findings ({len(report.findings)})",
        ]
    )
    if not report.findings:
        lines.append("  none")
    for finding in report.findings:
        lines.append(f"  [{finding.severity}] {finding.code}: {finding.message}")
    return "\n".join(lines) + "\n"


def validate_repo(repo: str) -> None:
    if not REPO_PATTERN.fullmatch(repo):
        raise ReportError("repository must use OWNER/NAME format")


def infer_repo(runner: Runner) -> str:
    repo = runner(("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"))
    repo = repo.strip()
    validate_repo(repo)
    return repo


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="GitHub repository in OWNER/NAME format")
    parser.add_argument("--main-branch", default="main")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return exit code 2 when an error-severity tracking policy finding exists",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    runner = SubprocessRunner(repo_root)
    try:
        repo = args.repo or infer_repo(runner)
        report = build_report(repo, args.main_branch, runner)
    except ReportError as exc:
        print(f"project_status=ERROR reason={exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(report.public(), ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(render_text(report), end="")
    if args.strict and any(finding.severity == "error" for finding in report.findings):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
