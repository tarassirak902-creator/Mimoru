from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PeriodComparison:
    current: int
    previous: int

    @property
    def delta(self) -> int:
        return self.current - self.previous

    @property
    def percent(self) -> float | None:
        if self.previous == 0:
            return None if self.current == 0 else 100.0
        return (self.delta / self.previous) * 100.0


def trend_text(current: int, previous: int) -> str:
    comparison = PeriodComparison(current=current, previous=previous)
    if current == previous:
        return "без изменений"
    arrow = "↗️" if current > previous else "↘️"
    if comparison.percent is None:
        return f"{arrow} {comparison.delta:+d}"
    return f"{arrow} {comparison.percent:+.0f}%"


def compact_period_label(days: int) -> str:
    return {1: "сегодня", 7: "7 дней", 30: "30 дней"}.get(days, f"{days} дней")


def report_hour_label(hour: int) -> str:
    return f"{hour:02d}:00"
