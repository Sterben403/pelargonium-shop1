import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "dora_dashboard", Path(__file__).resolve().parents[1] / "scripts" / "dora_dashboard.py")
dora = importlib.util.module_from_spec(spec)
sys.modules["dora_dashboard"] = dora  # dataclasses look the module up while the class is created
spec.loader.exec_module(dora)

T0 = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)


def release(hours_after_start, state="success", lead_hours=2.0, name="#1 change"):
    finished = T0 + timedelta(hours=hours_after_start)
    return dora.Release(sha=f"{int(hours_after_start * 10):07d}abc", created_at=finished - timedelta(minutes=5),
                        finished_at=finished, state=state, change=name,
                        first_commit_at=finished - timedelta(hours=lead_hours))


def test_no_deployments_means_no_numbers():
    m = dora.calculate([], now=T0)
    assert m["deployments_per_week"] is None and m["lead_time_hours"] is None
    assert m["change_failure_rate_percent"] is None and m["time_to_restore_hours"] is None
    assert set(m["levels"].values()) == {"not enough data"}


def test_metrics_from_deployments():
    releases = [
        release(0, lead_hours=1),
        release(24, lead_hours=3),
        release(48, state="failure", lead_hours=5),
        release(50, lead_hours=0.5),  # fix of the failed release, 2 hours later
        release(100, lead_hours=2),
    ]
    m = dora.calculate(releases, now=T0 + timedelta(days=14))
    assert m["deployments"] == 5 and m["successful"] == 4 and m["failed"] == 1
    assert m["deployments_per_week"] == 2.0  # 4 successful in 14 days
    assert m["lead_time_hours"] == 1.5  # median of successful changes: 0.5, 1, 2, 3
    assert m["change_failure_rate_percent"] == 20.0
    assert m["time_to_restore_hours"] == 2.0
    assert m["levels"] == {"deployments_per_week": "High", "lead_time_hours": "Elite",
                           "change_failure_rate_percent": "Low", "time_to_restore_hours": "High"}


def test_one_release_is_not_stretched_into_a_weekly_rate():
    m = dora.calculate([release(0, lead_hours=0.75)], now=T0 + timedelta(hours=3))
    assert m["deployments_per_week"] == 1.0  # one release, divided by a full week, not by 3 hours
    assert m["lead_time_hours"] == 0.75  # a measured value is still reported
    assert set(m["levels"].values()) == {"not enough data"}


def test_failure_without_recovery_has_no_restore_time():
    m = dora.calculate([release(0), release(5, state="failure")], now=T0 + timedelta(days=1))
    assert m["time_to_restore_hours"] is None and m["restored"] == 0


def test_summary_lists_every_deployment():
    m = dora.calculate([release(0, name="#7 Phone mask"), release(3, state="failure", name="#8 Broken")],
                       now=T0 + timedelta(days=1))
    text = dora.summary_markdown(m)
    assert "#7 Phone mask" in text and "#8 Broken" in text and "| failure |" in text
