#!/usr/bin/env python3
"""DORA metrics from GitHub Deployments of the `production` environment.

Every merge to main is released by the `Release to production` job, and GitHub records
that job as a Deployment with a final status (success / failure). From these records:

* Deployment Frequency  — successful production deployments per week;
* Lead Time for Changes — per change: first commit of the pull request -> its deployment finished;
* Change Failure Rate   — failed deployments / all finished deployments;
* Time to Restore       — failed deployment -> next successful deployment.

Nothing is entered by hand: if there is no data yet, the metric is reported as N/A.

    GITHUB_TOKEN=... python scripts/dora_dashboard.py --output dist/dora_dashboard.png
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ENVIRONMENT = "production"
FINAL_STATES = {"success", "failure", "error"}


@dataclass
class Release:
    sha: str
    created_at: datetime
    finished_at: datetime
    state: str  # success | failure | error
    change: str  # "#12 Title" or the commit subject
    first_commit_at: datetime  # first commit of the change


# ---------------------------------------------------------------- GitHub API

def github_get(path: str):
    repository = os.environ.get("GITHUB_REPOSITORY", "Sterben403/pelargonium-shop1")
    token = os.environ.get("GITHUB_TOKEN", "")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "pelargonium-shop-dora",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def github_get_all(path: str) -> list:
    items, page = [], 1
    separator = "&" if "?" in path else "?"
    while True:
        batch = github_get(f"{path}{separator}per_page=100&page={page}")
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def describe_change(sha: str) -> tuple[str, datetime]:
    """The pull request that brought `sha` to main and the time of its first commit."""
    pulls = github_get(f"/commits/{sha}/pulls")
    if pulls:
        pr = pulls[0]
        commits = github_get_all(f"/pulls/{pr['number']}/commits")
        first = min(parse_time(c["commit"]["author"]["date"]) for c in commits)
        return f"#{pr['number']} {pr['title']}", first
    commit = github_get(f"/commits/{sha}")["commit"]  # pushed to main without a PR
    return commit["message"].splitlines()[0], parse_time(commit["author"]["date"])


def collect_releases() -> list[Release]:
    releases = []
    for deployment in github_get_all(f"/deployments?environment={ENVIRONMENT}"):
        statuses = github_get(f"/deployments/{deployment['id']}/statuses")  # newest first
        final = next((s for s in statuses if s["state"] in FINAL_STATES), None)
        if not final:
            continue  # still running
        change, first_commit_at = describe_change(deployment["sha"])
        releases.append(Release(
            sha=deployment["sha"],
            created_at=parse_time(deployment["created_at"]),
            finished_at=parse_time(final["created_at"]),
            state=final["state"],
            change=change,
            first_commit_at=first_commit_at,
        ))
    return sorted(releases, key=lambda r: r.finished_at)


# ---------------------------------------------------------------- metrics

def level(metric: str, value: float | None) -> str:
    """Rough DORA performance level (thresholds of the 2023 State of DevOps report)."""
    if value is None:
        return "N/A"
    bands = {
        # metric: (elite, high, medium) upper bounds; above medium -> Low
        "lead_time_hours": (24, 24 * 7, 24 * 30),
        "change_failure_rate_percent": (5, 10, 15),
        "time_to_restore_hours": (1, 24, 24 * 7),
    }
    if metric == "deployments_per_week":  # higher is better
        return "Elite" if value >= 7 else "High" if value >= 1 else "Medium" if value >= 0.25 else "Low"
    elite, high, medium = bands[metric]
    return "Elite" if value <= elite else "High" if value <= high else "Medium" if value <= medium else "Low"


def calculate(releases: list[Release], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    successes = [r for r in releases if r.state == "success"]
    failures = [r for r in releases if r.state != "success"]

    if releases:
        days = max(1.0, (now - releases[0].created_at).total_seconds() / 86400)
        per_week = round(len(successes) / days * 7, 2)
    else:
        days, per_week = 0.0, None

    lead_times = [(r.finished_at - r.first_commit_at).total_seconds() / 3600 for r in successes]

    restore_times = []
    for failed in failures:
        recovered = next((r for r in successes if r.finished_at > failed.finished_at), None)
        if recovered:
            restore_times.append((recovered.finished_at - failed.finished_at).total_seconds() / 3600)

    metrics = {
        "deployments_per_week": per_week,
        "lead_time_hours": round(statistics.median(lead_times), 2) if lead_times else None,
        "change_failure_rate_percent": round(len(failures) / len(releases) * 100, 1) if releases else None,
        "time_to_restore_hours": round(statistics.mean(restore_times), 2) if restore_times else None,
    }
    return {
        "generated_at": now.isoformat(),
        "environment": ENVIRONMENT,
        "observation_days": round(days, 1),
        "deployments": len(releases),
        "successful": len(successes),
        "failed": len(failures),
        "restored": len(restore_times),
        **metrics,
        "levels": {name: level(name, value) for name, value in metrics.items()},
        "releases": [
            {
                "sha": r.sha[:7],
                "change": r.change,
                "state": r.state,
                "finished_at": r.finished_at.isoformat(),
                "lead_time_hours": round((r.finished_at - r.first_commit_at).total_seconds() / 3600, 2),
            }
            for r in releases
        ],
    }


# ---------------------------------------------------------------- output

def fmt_hours(hours: float | None) -> str:
    if hours is None:
        return "N/A"
    if hours < 1:
        return f"{hours * 60:.0f} min"
    if hours < 48:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} days"


def cards(m: dict) -> list[tuple[str, str, str]]:
    lv = m["levels"]
    per_week = "N/A" if m["deployments_per_week"] is None else f"{m['deployments_per_week']} / week"
    cfr = "N/A" if m["change_failure_rate_percent"] is None else f"{m['change_failure_rate_percent']}%"
    return [
        ("Deployment Frequency", per_week,
         f"{m['successful']} successful deployments\nin {m['observation_days']} days · {lv['deployments_per_week']}"),
        ("Lead Time for Changes", fmt_hours(m["lead_time_hours"]),
         f"median, first commit -> production\n{lv['lead_time_hours']}"),
        ("Change Failure Rate", cfr,
         f"{m['failed']} failed of {m['deployments']} deployments\n{lv['change_failure_rate_percent']}"),
        ("Time to Restore", fmt_hours(m["time_to_restore_hours"]),
         f"{m['restored']} recoveries after failure\n{lv['time_to_restore_hours']}"),
    ]


def render_dashboard(metrics: dict, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig = plt.figure(figsize=(12, 7.2), dpi=180)
    fig.patch.set_facecolor("white")
    top = fig.add_axes([0, 0.42, 1, 0.58])
    top.set_xlim(0, 12)
    top.set_ylim(0, 4.2)
    top.axis("off")
    top.text(0.3, 3.95, "Pelargonium Shop — DORA metrics", fontsize=15, fontweight="bold", color="#231A27")
    top.text(11.7, 3.95, "source: GitHub Deployments · environment production",
             fontsize=9, color="#666666", ha="right")
    for i, (title, value, note) in enumerate(cards(metrics)):
        x = 0.3 + i * 2.88
        top.add_patch(FancyBboxPatch((x, 0.3), 2.7, 3.2, boxstyle="round,pad=0.04,rounding_size=0.12",
                                     linewidth=1.2, edgecolor="#345E4A", facecolor="#EEF4F0"))
        top.text(x + 0.18, 3.05, title, fontsize=10.5, fontweight="bold", color="#345E4A")
        top.text(x + 0.18, 2.05, value, fontsize=20, fontweight="bold", color="#231A27")
        top.text(x + 0.18, 0.85, note, fontsize=8.5, color="#4A4A4A")

    ax = fig.add_axes([0.07, 0.08, 0.9, 0.3])
    rows = metrics["releases"]
    if rows:
        colors = ["#345E4A" if r["state"] == "success" else "#B3261E" for r in rows]
        ax.bar(range(len(rows)), [r["lead_time_hours"] for r in rows], color=colors)
        ax.set_xticks(range(len(rows)), [r["sha"] for r in rows], fontsize=7, rotation=45)
        ax.set_ylabel("lead time, h", fontsize=9)
        ax.set_title("Lead time of each deployment (red = failed)", fontsize=10, loc="left")
        ax.grid(axis="y", alpha=0.25)
    else:
        ax.axis("off")
        ax.text(0.5, 0.5, "No production deployments yet", ha="center", va="center", fontsize=11, color="#666666")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, facecolor="white")
    plt.close(fig)


def summary_markdown(metrics: dict) -> str:
    lines = ["## DORA metrics (production)", "", "| Metric | Value | Level |", "| --- | --- | --- |"]
    keys = ["deployments_per_week", "lead_time_hours", "change_failure_rate_percent", "time_to_restore_hours"]
    for (title, value, _), key in zip(cards(metrics), keys, strict=True):
        lines.append(f"| {title} | {value} | {metrics['levels'][key]} |")
    lines += ["", "| Deployment | Change | Result | Lead time |", "| --- | --- | --- | --- |"]
    for r in metrics["releases"]:
        lines.append(f"| `{r['sha']}` | {r['change']} | {r['state']} | {fmt_hours(r['lead_time_hours'])} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/dora_dashboard.png")
    parser.add_argument("--json", default="dist/dora_metrics.json")
    parser.add_argument("--summary", help="append a Markdown table here (e.g. $GITHUB_STEP_SUMMARY)")
    args = parser.parse_args()

    metrics = calculate(collect_releases())
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    render_dashboard(metrics, Path(args.output))
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(summary_markdown(metrics))
    print(json.dumps({k: v for k, v in metrics.items() if k != "releases"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
