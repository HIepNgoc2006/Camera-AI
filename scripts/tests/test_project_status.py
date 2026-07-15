from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.project_status import (
    ACTIVE_SCOPE,
    DEFERRED_SCOPE,
    Command,
    ReportError,
    build_report,
    render_text,
    run_command,
    validate_repo,
)

REPO = "example/camera-ai"
GENERATED_AT = "2026-07-16T01:00:00Z"
REPO_ROOT = Path(__file__).resolve().parents[2]


def issue(
    number: int,
    *,
    state: str = "OPEN",
    milestone: str = "M3 - Backend Core",
    labels: Sequence[str] = (),
    assignees: Sequence[str] = (),
) -> dict[str, object]:
    return {
        "number": number,
        "title": f"Synthetic issue {number}",
        "state": state,
        "milestone": {"title": milestone},
        "labels": [{"name": label} for label in labels],
        "assignees": [{"login": assignee} for assignee in assignees],
        "url": f"https://example.invalid/issues/{number}",
    }


class FakeRunner:
    def __init__(
        self,
        active: Sequence[dict[str, object]],
        deferred: Sequence[dict[str, object]] | None = None,
    ) -> None:
        self.active = list(active)
        self.deferred = list(deferred or [])
        self.commands: list[Command] = []

    def __call__(self, command: Command) -> str:
        self.commands.append(command)
        if command[:3] == ("gh", "issue", "list"):
            search = command[command.index("--search") + 1]
            values = self.active if search == f"label:{ACTIVE_SCOPE}" else self.deferred
            return json.dumps(values)
        if command[:2] == ("gh", "api"):
            return json.dumps(
                [
                    {"title": "M2 - Codebase Foundation", "due_on": "2026-07-15T00:00:00Z"},
                    {"title": "M3 - Backend Core", "due_on": "2026-08-15T00:00:00Z"},
                ]
            )
        if command[:3] == ("gh", "pr", "list"):
            return json.dumps([])
        if command[:3] == ("gh", "run", "list"):
            return json.dumps(
                [
                    {
                        "workflowName": "Baseline quality",
                        "status": "completed",
                        "conclusion": "success",
                        "createdAt": "2026-07-16T00:00:00Z",
                        "url": "https://example.invalid/actions/1",
                    }
                ]
            )
        if command == ("git", "branch", "--show-current"):
            return "ops/live-progress\n"
        if command == ("git", "status", "--porcelain=v1", "--untracked-files=normal"):
            return ""
        if command[:4] == ("git", "rev-list", "--left-right", "--count"):
            return "0\t1\n"
        raise AssertionError(f"unexpected command: {command}")


def healthy_active_issues() -> list[dict[str, object]]:
    return [
        issue(
            1,
            state="CLOSED",
            milestone="M2 - Codebase Foundation",
            labels=(ACTIVE_SCOPE,),
        ),
        issue(2, labels=(ACTIVE_SCOPE, "status:ready"), assignees=("developer",)),
        issue(3, labels=(ACTIVE_SCOPE, "status:in-progress"), assignees=("developer",)),
        issue(4, labels=(ACTIVE_SCOPE, "status:blocked")),
        issue(5, labels=(ACTIVE_SCOPE, "status:needs-decision")),
    ]


def test_build_report_summarizes_live_metadata() -> None:
    runner = FakeRunner(
        healthy_active_issues(),
        deferred=[
            issue(
                6,
                milestone="M6 - Mobile App",
                labels=(DEFERRED_SCOPE, "priority:low"),
            )
        ],
    )

    report = build_report(REPO, "main", runner, GENERATED_AT)
    output = report.public()

    assert output["scope"] == {
        "active": {"total": 5, "open": 4, "closed": 1, "completion_percent": 20.0},
        "deferred": {"total": 1, "open": 1, "closed": 0, "completion_percent": 0.0},
    }
    assert [phase.title for phase in report.phases] == [
        "M2 - Codebase Foundation",
        "M3 - Backend Core",
    ]
    assert [item.number for item in report.ready] == [2]
    assert [item.number for item in report.in_progress] == [3]
    assert [item.number for item in report.blocked] == [4]
    assert [item.number for item in report.needs_decision] == [5]
    assert report.git.branch == "ops/live-progress"
    assert report.git.ahead_of_main == 1
    assert report.findings == ()


def test_report_requests_metadata_without_issue_body_or_comments() -> None:
    runner = FakeRunner(healthy_active_issues())

    build_report(REPO, "main", runner, GENERATED_AT)

    issue_commands = [
        command for command in runner.commands if command[:3] == ("gh", "issue", "list")
    ]
    assert issue_commands
    for command in issue_commands:
        fields = command[command.index("--json") + 1].split(",")
        assert "body" not in fields
        assert "comments" not in fields


def test_lane_policy_flags_multiple_in_progress_and_unassigned_issue() -> None:
    active = healthy_active_issues()
    active.append(issue(7, labels=(ACTIVE_SCOPE, "status:in-progress")))
    runner = FakeRunner(active)

    report = build_report(REPO, "main", runner, GENERATED_AT)

    codes = [finding.code for finding in report.findings]
    assert "IN_PROGRESS_LIMIT" in codes
    assert "LANE_UNASSIGNED" in codes


def test_deferred_policy_rejects_execution_labels() -> None:
    runner = FakeRunner(
        healthy_active_issues(),
        deferred=[
            issue(
                8,
                milestone="M7 - Integration & QA",
                labels=(DEFERRED_SCOPE, "priority:high", "status:blocked"),
            )
        ],
    )

    report = build_report(REPO, "main", runner, GENERATED_AT)

    assert any(finding.code == "DEFERRED_LANE_POLICY" for finding in report.findings)


def test_text_report_is_a_compact_operational_summary() -> None:
    report = build_report(REPO, "main", FakeRunner(healthy_active_issues()), GENERATED_AT)

    rendered = render_text(report)

    assert "Project progress (live)" in rendered
    assert "Active: 1/5 closed (20.0%), 4 open" in rendered
    assert "In Progress (1)" in rendered
    assert "Ready (1)" in rendered
    assert "Baseline quality: success" in rendered
    assert "body" not in rendered.lower()


def test_missing_due_date_is_reported_without_making_schedule_up() -> None:
    runner = FakeRunner(healthy_active_issues())

    def no_due_date(command: Command) -> str:
        if command[:2] == ("gh", "api"):
            return json.dumps(
                [
                    {"title": "M2 - Codebase Foundation", "due_on": None},
                    {"title": "M3 - Backend Core", "due_on": None},
                ]
            )
        return runner(command)

    report = build_report(REPO, "main", no_due_date, GENERATED_AT)

    assert report.public()["schedule"] == {
        "status": "not_assessable",
        "missing_due_dates": ["M3 - Backend Core"],
    }
    assert any(finding.code == "MILESTONE_DUE_DATES" for finding in report.findings)


def test_failed_command_does_not_expose_captured_output() -> None:
    failed = subprocess.CompletedProcess(
        args=("gh", "issue"),
        returncode=1,
        stdout="synthetic-sensitive-output",
        stderr="synthetic-sensitive-error",
    )
    with (
        patch("scripts.project_status.subprocess.run", return_value=failed),
        pytest.raises(ReportError) as exc_info,
    ):
        run_command(("gh", "issue", "list"), Path.cwd())

    message = str(exc_info.value)
    assert message == "metadata command failed: gh issue"
    assert "synthetic-sensitive" not in message


@pytest.mark.parametrize(
    "repo",
    ("missing-owner", "owner/name/extra", "owner name/repo", "https://example.invalid/repo"),
)
def test_repository_name_validation_fails_closed(repo: str) -> None:
    with pytest.raises(ReportError, match="OWNER/NAME"):
        validate_repo(repo)


def test_progress_workflow_is_read_only_and_enforces_lane_policy() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "project-progress.yml").read_text(
        encoding="utf-8"
    )

    assert "actions: read" in workflow
    assert "contents: read" in workflow
    assert "issues: read" in workflow
    assert "pull-requests: read" in workflow
    assert "permissions: write" not in workflow
    assert "--strict" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
