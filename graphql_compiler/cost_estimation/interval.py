# Copyright 2020-present Kensho Technologies, LLC.
from dataclasses import dataclass
import datetime
from typing import Generic, Optional, TypeVar


IntervalDomain = TypeVar("IntervalDomain", int, str, datetime.date, datetime.datetime)


@dataclass(eq=False, frozen=True)
class Interval(Generic[IntervalDomain]):
    """Interval of IntervalDomain values. The ends are inclusive."""

    lower_bound: Optional[IntervalDomain]
    upper_bound: Optional[IntervalDomain]

    def is_empty(self) -> bool:
        """Return whether the interval is empty."""
        if self.lower_bound is None or self.upper_bound is None:
            return False
        return self.lower_bound > self.upper_bound

    def __eq__(self, other) -> bool:
        """Compare two intervals. Empty intervals are considered equal to each other."""
        if self.is_empty() and other.is_empty():
            return True
        return self.lower_bound == other.lower_bound and self.upper_bound == other.upper_bound


def measure_int_interval(interval: Interval[int]) -> Optional[int]:
    """Return the size of the integer interval."""
    if interval.lower_bound is None or interval.upper_bound is None:
        return None
    if interval.is_empty():
        return 0
    return interval.upper_bound - interval.lower_bound + 1


def _get_stronger_lower_bound(
    lower_bound_a: Optional[IntervalDomain], lower_bound_b: Optional[IntervalDomain]
) -> Optional[IntervalDomain]:
    """Return the larger bound of the two given lower bounds."""
    stronger_lower_bound = None
    if lower_bound_a is not None and lower_bound_b is not None:
        stronger_lower_bound = max(lower_bound_a, lower_bound_b)
    elif lower_bound_a is not None:
        stronger_lower_bound = lower_bound_a
    elif lower_bound_b is not None:
        stronger_lower_bound = lower_bound_b

    return stronger_lower_bound


def _get_stronger_upper_bound(
    upper_bound_a: Optional[IntervalDomain], upper_bound_b: Optional[IntervalDomain]
) -> Optional[IntervalDomain]:
    """Return the smaller bound of the two given upper bounds."""
    stronger_upper_bound = None
    if upper_bound_a is not None and upper_bound_b is not None:
        stronger_upper_bound = min(upper_bound_a, upper_bound_b)
    elif upper_bound_a is not None:
        stronger_upper_bound = upper_bound_a
    elif upper_bound_b is not None:
        stronger_upper_bound = upper_bound_b

    return stronger_upper_bound


def intersect_int_intervals(interval_a: Interval[int], interval_b: Interval[int]) -> Interval[int]:
    """Return the intersection of two Intervals."""
    strong_lower_bound = _get_stronger_lower_bound(interval_a.lower_bound, interval_b.lower_bound)
    strong_upper_bound = _get_stronger_upper_bound(interval_a.upper_bound, interval_b.upper_bound)
    return Interval(strong_lower_bound, strong_upper_bound)
