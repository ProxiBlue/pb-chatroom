"""Tests for escalation evaluator."""

from __future__ import annotations

from pb_chatroom_relay.escalation import evaluate_escalation


def test_it_triggers_on_multiple_competing_approaches_when_stdout_matches_the_pattern():
    assert 'multiple_competing_approaches' in evaluate_escalation(
        'We see competing approach A and approach B here'
    )
    assert 'multiple_competing_approaches' in evaluate_escalation(
        'There is a clear trade-off between speed and safety'
    )
    assert 'multiple_competing_approaches' in evaluate_escalation(
        'Two competing approaches exist'
    )


def test_it_composes_multiple_reasons_when_multiple_rules_fire():
    # prod_data_access + external_credentials both match
    result = evaluate_escalation('Accessing production database with api_key=abc123')
    assert 'prod_data_access' in result
    assert 'external_credentials' in result
    assert len(result) == 2


def test_it_returns_no_escalation_when_none_of_the_rules_fire():
    result = evaluate_escalation('Everything is fine, all tests pass, no issues found.')
    assert result == []


def test_it_triggers_on_previously_passing_tests_broken_when_stdout_matches_the_failure_pattern():
    assert 'tests_broken' in evaluate_escalation('This broke tests that were passing before')
    assert 'tests_broken' in evaluate_escalation('The change broke a passing test in CI')
    assert 'tests_broken' not in evaluate_escalation('All tests continue to pass normally')


def test_it_triggers_on_external_credentials_when_stdout_mentions_api_key_or_token():
    assert 'external_credentials' in evaluate_escalation('Use api_key=secret123 for auth')
    assert 'external_credentials' in evaluate_escalation('Set access_token in the header')
    assert 'external_credentials' in evaluate_escalation('Store secret_key in env var')
    assert 'external_credentials' not in evaluate_escalation('No sensitive credentials here')


def test_it_triggers_on_confidence_below_threshold_when_stdout_contains_a_low_confidence_sentinel():
    assert 'confidence_below_threshold' in evaluate_escalation('I am not confident this is correct')
    assert 'confidence_below_threshold' in evaluate_escalation(
        'The result is uncertain at this point'
    )
    assert 'confidence_below_threshold' in evaluate_escalation('This approach shows low confidence')
    assert 'confidence_below_threshold' not in evaluate_escalation('Confidence is high, proceeding')


def test_it_triggers_on_cost_trigger_when_stdout_mentions_budget_cap():
    assert 'cost_trigger' in evaluate_escalation('The budget cap has been reached')
    assert 'cost_trigger' in evaluate_escalation('Budget limit exceeded for this month')
    assert 'cost_trigger' in evaluate_escalation('Current spend budget exceeded')
    assert 'cost_trigger' not in evaluate_escalation('Everything is within normal range')


def test_it_triggers_on_prod_data_when_stdout_mentions_production_database_write_or_live_data():
    assert 'prod_data_access' in evaluate_escalation(
        'This touches the production database directly'
    )
    assert 'prod_data_access' in evaluate_escalation('Reading from live data is required')
    assert 'prod_data_access' in evaluate_escalation('Connecting to prod db for migration')
    assert 'prod_data_access' not in evaluate_escalation('No sensitive data access here')


def test_it_triggers_on_architectural_changes_when_3_or_more_module_paths_appear_in_stdout():
    # 3 distinct paths — should trigger
    assert 'architectural_changes' in evaluate_escalation(
        'Changes in src/foo/bar.py and src/baz/qux.py and src/auth/login.py'
    )
    # 2 paths — should NOT trigger
    assert 'architectural_changes' not in evaluate_escalation(
        'Changes in src/foo/bar.py and src/baz/qux.py'
    )
    # same path repeated — should NOT trigger (distinct count < 3)
    assert 'architectural_changes' not in evaluate_escalation(
        'src/foo/bar.py mentioned twice: src/foo/bar.py and src/foo/bar.py'
    )
