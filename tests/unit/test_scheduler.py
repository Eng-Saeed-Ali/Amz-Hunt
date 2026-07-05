"""Unit tests for ActiveHoursScheduler — time-of-day gating logic."""

from datetime import datetime, timezone
from unittest import mock

import pytest

from src.core.models.target_endpoint import TargetEndpoint
from src.core.scheduler import ActiveHoursScheduler


def _make_endpoint(
    endpoint_id: str = "test-ep",
    url: str = "https://example.com/deals",
    parser_type: str = "html_dom",
    active_hours: tuple[int | None, int | None] = (6, 18),
) -> TargetEndpoint:
    """Thin factory that creates a minimal, valid TargetEndpoint.

    Only active_hours and the required identity fields are set; the
    scheduler never touches mutable fields (last_polled_utc, etc.)
    so defaults are fine.
    """
    return TargetEndpoint(
        endpoint_id=endpoint_id,
        url=url,
        parser_type=parser_type,
        active_hours=active_hours,
        impersonate_profile="chrome110",
        priority=1,
    )


class TestTwentyFourSevenMode:
    """Scheduler must always return True for endpoints configured to run 24/7."""

    def test_none_start_and_end_means_always_active(self) -> None:
        endpoint = _make_endpoint(active_hours=(None, None))
        assert ActiveHoursScheduler.is_active_now(endpoint) is True

    def test_equal_start_and_end_means_always_active(self) -> None:
        endpoint = _make_endpoint(active_hours=(12, 12))
        assert ActiveHoursScheduler.is_active_now(endpoint) is True

    def test_none_start_with_valid_end_means_always_active(self) -> None:
        endpoint = _make_endpoint(active_hours=(None, 18))
        assert ActiveHoursScheduler.is_active_now(endpoint) is True

    def test_valid_start_with_none_end_means_always_active(self) -> None:
        endpoint = _make_endpoint(active_hours=(6, None))
        assert ActiveHoursScheduler.is_active_now(endpoint) is True


class TestNormalRange:
    """Active hours with start <= end must gate correctly."""

    def test_current_hour_within_window_returns_true(self) -> None:
        """10:00 UTC is inside the 06:00–18:00 window."""
        endpoint = _make_endpoint(active_hours=(6, 18))
        with mock.patch.object(
            ActiveHoursScheduler,
            "_get_utc_now",
            return_value=datetime(2026, 7, 5, 10, 0, 0, tzinfo=timezone.utc),
        ):
            assert ActiveHoursScheduler.is_active_now(endpoint) is True

    def test_current_hour_before_window_returns_false(self) -> None:
        """03:00 UTC is before the 06:00–18:00 window."""
        endpoint = _make_endpoint(active_hours=(6, 18))
        with mock.patch.object(
            ActiveHoursScheduler,
            "_get_utc_now",
            return_value=datetime(2026, 7, 5, 3, 0, 0, tzinfo=timezone.utc),
        ):
            assert ActiveHoursScheduler.is_active_now(endpoint) is False

    def test_current_hour_after_window_returns_false(self) -> None:
        """20:00 UTC is after the 06:00–18:00 window."""
        endpoint = _make_endpoint(active_hours=(6, 18))
        with mock.patch.object(
            ActiveHoursScheduler,
            "_get_utc_now",
            return_value=datetime(2026, 7, 5, 20, 0, 0, tzinfo=timezone.utc),
        ):
            assert ActiveHoursScheduler.is_active_now(endpoint) is False

    def test_current_hour_on_lower_boundary_returns_true(self) -> None:
        """06:00 UTC exactly — boundary must be inclusive."""
        endpoint = _make_endpoint(active_hours=(6, 18))
        with mock.patch.object(
            ActiveHoursScheduler,
            "_get_utc_now",
            return_value=datetime(2026, 7, 5, 6, 0, 0, tzinfo=timezone.utc),
        ):
            assert ActiveHoursScheduler.is_active_now(endpoint) is True

    def test_current_hour_on_upper_boundary_returns_true(self) -> None:
        """18:00 UTC exactly — boundary must be inclusive."""
        endpoint = _make_endpoint(active_hours=(6, 18))
        with mock.patch.object(
            ActiveHoursScheduler,
            "_get_utc_now",
            return_value=datetime(2026, 7, 5, 18, 0, 0, tzinfo=timezone.utc),
        ):
            assert ActiveHoursScheduler.is_active_now(endpoint) is True


class TestMidnightWrappingRange:
    """Active hours spanning midnight (start > end) must gate correctly."""

    def test_late_night_inside_wrapping_window_returns_true(self) -> None:
        """23:00 UTC is inside 22:00–06:00 (post-midnight window)."""
        endpoint = _make_endpoint(active_hours=(22, 6))
        with mock.patch.object(
            ActiveHoursScheduler,
            "_get_utc_now",
            return_value=datetime(2026, 7, 5, 23, 0, 0, tzinfo=timezone.utc),
        ):
            assert ActiveHoursScheduler.is_active_now(endpoint) is True

    def test_early_morning_inside_wrapping_window_returns_true(self) -> None:
        """02:00 UTC is inside 22:00–06:00 (pre-dawn)."""
        endpoint = _make_endpoint(active_hours=(22, 6))
        with mock.patch.object(
            ActiveHoursScheduler,
            "_get_utc_now",
            return_value=datetime(2026, 7, 5, 2, 0, 0, tzinfo=timezone.utc),
        ):
            assert ActiveHoursScheduler.is_active_now(endpoint) is True

    def test_midday_outside_wrapping_window_returns_false(self) -> None:
        """12:00 UTC is outside 22:00–06:00 (daytime gap)."""
        endpoint = _make_endpoint(active_hours=(22, 6))
        with mock.patch.object(
            ActiveHoursScheduler,
            "_get_utc_now",
            return_value=datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc),
        ):
            assert ActiveHoursScheduler.is_active_now(endpoint) is False