#!/usr/bin/env python3
"""Generate the project's reproducible synthetic credit-card portfolio."""

from __future__ import annotations

import argparse
import csv
import random
from calendar import monthrange
from pathlib import Path


START_YEAR, START_MONTH = 2022, 1
MONTH_COUNT = 57
ACCOUNT_COUNT = 2_000
DEFAULT_SEED = 20261030

FIELDS = [
    "account_id", "snapshot_month", "origination_month", "account_status",
    "risk_segment", "acquisition_channel", "customer_age_band",
    "credit_limit_gbp", "opening_balance_gbp", "purchase_amount_gbp",
    "interest_fee_amount_gbp", "payment_due_gbp", "payment_received_gbp",
    "other_adjustment_gbp", "closing_balance_gbp", "days_past_due",
    "delinquency_status",
]

SEGMENT_COUNTS = {"LOWER": 1_000, "MIDDLE": 700, "HIGHER": 300}
CHANNEL_COUNTS = {"DIRECT": 1_400, "PARTNER": 600}
AGE_COUNTS = {"18-24": 240, "25-34": 560, "35-49": 600, "50-64": 440, "65+": 160}
LIMIT_RANGES = {"LOWER": (50_000, 1_000_000), "MIDDLE": (50_000, 750_000), "HIGHER": (50_000, 500_000)}
INTEREST_BPS = {"LOWER": 120, "MIDDLE": 160, "HIGHER": 200}
NEW_DELINQUENCY_BPS = {"LOWER": 80, "MIDDLE": 200, "HIGHER": 500}
CLOSURE_BPS = {"LOWER": 20, "MIDDLE": 40, "HIGHER": 60}
DPD_STATES = ["CURRENT", "1_29", "30_59", "60_89", "90_PLUS"]
DPD_DAYS = {"CURRENT": 0, "1_29": 15, "30_59": 45, "60_89": 75, "90_PLUS": 105}
TRANSITIONS = {
    "CURRENT": [("CURRENT", 9_000)],  # remaining probability is segment-specific delinquency entry
    "1_29": [("CURRENT", 2_500), ("1_29", 6_200), ("30_59", 1_300)],
    "30_59": [("CURRENT", 1_000), ("1_29", 2_000), ("30_59", 5_500), ("60_89", 1_500)],
    "60_89": [("CURRENT", 600), ("1_29", 1_000), ("30_59", 2_400), ("60_89", 4_800), ("90_PLUS", 1_200)],
    "90_PLUS": [("CURRENT", 200), ("1_29", 300), ("30_59", 1_000), ("60_89", 1_500), ("90_PLUS", 7_000)],
}
PAYMENT_FRACTION_BPS = {
    "CURRENT": (8_500, 10_000),
    "1_29": (7_000, 9_500),
    "30_59": (5_500, 8_500),
    "60_89": (3_000, 7_000),
    "90_PLUS": (1_000, 5_000),
}


def month_end(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}"


def month_at(index: int) -> tuple[int, int]:
    absolute = START_YEAR * 12 + START_MONTH - 1 + index
    return absolute // 12, absolute % 12 + 1


def money(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def apply_bps(amount: int, basis_points: int) -> int:
    return (amount * basis_points + 5_000) // 10_000


def weighted_choice(rng: random.Random, choices: list[tuple[str, int]]) -> str:
    draw = rng.randrange(10_000)
    running = 0
    for value, weight in choices:
        running += weight
        if draw < running:
            return value
    raise ValueError(f"Transition weights sum to {running}, expected 10000")


def make_assignments(rng: random.Random) -> list[dict[str, str]]:
    """Create exact whole-portfolio attribute quotas, shuffled before cohort assignment."""
    def quota_values(quotas: dict[str, int]) -> list[str]:
        values = [value for value, count in quotas.items() for _ in range(count)]
        rng.shuffle(values)
        return values

    segments = quota_values(SEGMENT_COUNTS)
    channels = quota_values(CHANNEL_COUNTS)
    ages = quota_values(AGE_COUNTS)
    accounts = []
    for i in range(ACCOUNT_COUNT):
        segment = segments[i]
        low, high = LIMIT_RANGES[segment]
        accounts.append({
            "account_id": f"SYN{i + 1:06d}",
            "risk_segment": segment,
            "acquisition_channel": channels[i],
            "customer_age_band": ages[i],
            "credit_limit_cents": rng.randrange(low, high + 1, 5_000),
        })
    return accounts


def next_dpd_state(rng: random.Random, prior_state: str, segment: str) -> str:
    if prior_state == "CURRENT":
        delinquency_bps = NEW_DELINQUENCY_BPS[segment]
        draw = rng.randrange(10_000)
        return "1_29" if draw < delinquency_bps else "CURRENT"
    return weighted_choice(rng, TRANSITIONS[prior_state])


def generate_rows(seed: int = DEFAULT_SEED) -> list[dict[str, str]]:
    rng = random.Random(seed)
    accounts = make_assignments(rng)
    rows: list[dict[str, str]] = []

    # First 5 cohorts contain 36 accounts and the remaining 52 contain 35: 2,000 total.
    cohort_sizes = [36 if i < 5 else 35 for i in range(MONTH_COUNT)]
    cohort_start = 0
    for month_index, cohort_size in enumerate(cohort_sizes):
        year, month = month_at(month_index)
        snapshot_month = month_end(year, month)
        cohort_accounts = accounts[cohort_start:cohort_start + cohort_size]
        cohort_start += cohort_size
        for account in cohort_accounts:
            account_id = account["account_id"]
            segment = account["risk_segment"]
            limit = account["credit_limit_cents"]
            prior_balance = 0
            prior_state = "CURRENT"
            closed = False

            for obs_index in range(month_index, MONTH_COUNT):
                obs_year, obs_month = month_at(obs_index)
                obs_date = month_end(obs_year, obs_month)
                mob = obs_index - month_index
                opening = prior_balance
                state = "CURRENT" if mob == 0 else next_dpd_state(rng, prior_state, segment)

                # Closure is an explicit absorbing final row; closure payments clear the full balance.
                closure_bps = CLOSURE_BPS[segment]
                close_now = mob >= 2 and rng.randrange(10_000) < closure_bps
                if close_now:
                    purchases = 0
                    charges = 0
                    due = opening
                    received = opening
                    adjustment = 0
                    closing = 0
                    status = "CLOSED"
                    state = "CLOSED"
                    dpd_days = 0
                    closed = True
                else:
                    # Purchases are 0%-4% of limit per month, to the nearest cent.
                    purchases = rng.randrange(limit // 25 + 1)
                    charges = apply_bps(opening, INTEREST_BPS[segment])
                    prepayment = opening + purchases + charges
                    due = min(prepayment, max(2_500, apply_bps(prepayment, 500))) if prepayment else 0
                    fraction_low, fraction_high = PAYMENT_FRACTION_BPS[state]
                    payment_fraction = rng.randrange(fraction_low, fraction_high + 1)
                    received = apply_bps(due, payment_fraction)
                    received = min(received, due, prepayment)
                    adjustment = 0
                    closing = prepayment - received
                    status = "ACTIVE"
                    dpd_days = DPD_DAYS[state]

                row = {
                    "account_id": account_id,
                    "snapshot_month": obs_date,
                    "origination_month": snapshot_month,
                    "account_status": status,
                    "risk_segment": segment,
                    "acquisition_channel": account["acquisition_channel"],
                    "customer_age_band": account["customer_age_band"],
                    "credit_limit_gbp": money(limit),
                    "opening_balance_gbp": money(opening),
                    "purchase_amount_gbp": money(purchases),
                    "interest_fee_amount_gbp": money(charges),
                    "payment_due_gbp": money(due),
                    "payment_received_gbp": money(received),
                    "other_adjustment_gbp": money(adjustment),
                    "closing_balance_gbp": money(closing),
                    "days_past_due": str(dpd_days),
                    "delinquency_status": state,
                }
                rows.append(row)
                if closed:
                    break
                prior_balance = closing
                prior_state = state

    if cohort_start != ACCOUNT_COUNT:
        raise AssertionError(f"Assigned {cohort_start} accounts, expected {ACCOUNT_COUNT}")
    return rows


def write_csv(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=Path("data/synthetic_portfolio.csv"))
    args = parser.parse_args()
    rows = generate_rows(args.seed)
    write_csv(rows, args.output)
    print(f"Wrote {len(rows):,} account-month rows to {args.output} (seed={args.seed})")


if __name__ == "__main__":
    main()
