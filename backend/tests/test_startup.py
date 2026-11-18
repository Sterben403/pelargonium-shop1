import pytest
from sqlalchemy.exc import OperationalError

from app import main


class FlakyEngine:
    """Refuses connections a few times, like a database container that is still starting."""

    def __init__(self, failures):
        self.failures = failures
        self.calls = 0
        self.real = main.engine

    def connect(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        return self.real.connect()


def test_startup_waits_for_database(monkeypatch):
    flaky = FlakyEngine(failures=3)
    monkeypatch.setattr(main, "engine", flaky, raising=True)
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    main.wait_for_database(attempts=5)
    assert flaky.calls == 4


def test_startup_gives_up_when_database_never_comes(monkeypatch):
    monkeypatch.setattr(main, "engine", FlakyEngine(failures=99))
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    with pytest.raises(OperationalError):
        main.wait_for_database(attempts=3)
