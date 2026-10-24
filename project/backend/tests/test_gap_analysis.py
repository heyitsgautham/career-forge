"""Skill gap maths and the role benchmark catalogue."""

from app.services.gap_analysis import (
    compute_gaps,
    compute_overall_fit,
    get_all_roles,
    get_role_benchmark,
)


def test_role_catalogue_lists_domains_for_every_role():
    roles = get_all_roles()
    assert roles
    for role in roles:
        assert {"roleId", "role", "icon", "description", "skillDomains"} <= role.keys()
        assert role["skillDomains"]
        assert get_role_benchmark(role["roleId"])["role"] == role["role"]


def test_unknown_role_has_no_benchmark():
    assert get_role_benchmark("astronaut") is None


def test_gaps_are_sorted_and_prioritised():
    gaps = compute_gaps(
        {"APIs": 50, "SQL": 80, "Testing": 10},
        {"APIs": 70, "SQL": 70, "Testing": 60, "Cloud": 20},
    )
    assert [g["domain"] for g in gaps] == ["Testing", "APIs", "Cloud", "SQL"]
    by_domain = {g["domain"]: g for g in gaps}
    assert by_domain["Testing"]["priority"] == "high"  # gap 50
    assert by_domain["APIs"]["priority"] == "medium"  # gap 20
    assert by_domain["Cloud"]["userScore"] == 0
    assert by_domain["SQL"]["gap"] == 0
    assert by_domain["SQL"]["priority"] == "low"


def test_overall_fit_caps_each_domain_at_the_benchmark():
    benchmark = {"APIs": 80, "SQL": 20}
    assert compute_overall_fit({"APIs": 100, "SQL": 100}, benchmark) == 100
    assert compute_overall_fit({"APIs": 40}, benchmark) == 40
    assert compute_overall_fit({}, benchmark) == 0


def test_overall_fit_handles_empty_benchmarks():
    assert compute_overall_fit({"APIs": 50}, {}) == 0
    assert compute_overall_fit({"APIs": 50}, {"APIs": 0}) == 0
