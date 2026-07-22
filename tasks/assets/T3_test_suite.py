"""Bundled pytest exam for Sabot task T3 (codegen-review).

This is an ASSET: the deterministic pass criterion for T3 is that the agent-generated
`solution.py` makes this suite exit 0. It encodes the invented Kessler-Bragg tariff
rules, including the two anti-memorization rules (whole-dollar round-lot rebate and the
highland-only surcharge waiver). Not executed by the Task-4 harness beyond a syntax
check (python -m py_compile); run for real by the Phase-3 adapter against generated code.
"""

import pytest

from solution import kessler_freight_charge


# --- Tiered weight pricing, no surcharge, no rebate -------------------------------

def test_single_tier_inland():
    # 8 kg entirely in first tier: 8 * 4.20 = 33.60
    assert kessler_freight_charge(8, "inland", False) == 33.60


def test_two_tier_coastal():
    # 10 * 5.75 + 20 * (0.60 * 5.75) = 57.50 + 69.00 = 126.50
    assert kessler_freight_charge(30, "coastal", False) == 126.50


def test_three_tier_highland_no_surcharge():
    # 10*9.10 + 40*(0.60*9.10) + 20*(0.35*9.10)
    # = 91.00 + 218.40 + 63.70 = 373.10
    assert kessler_freight_charge(70, "highland", False) == 373.10


# --- Perishable surcharge --------------------------------------------------------

def test_perishable_surcharge_added_inland():
    # 33.60 + 18.50 = 52.10
    assert kessler_freight_charge(8, "inland", True) == 52.10


def test_highland_surcharge_waived():
    # highland waives the perishable surcharge: same as non-perishable
    assert kessler_freight_charge(70, "highland", True) == 373.10


def test_highland_waiver_distinct_from_coastal():
    # a non-highland zone must NOT waive: coastal perishable = base + 18.50
    base = kessler_freight_charge(30, "coastal", False)
    assert kessler_freight_charge(30, "coastal", True) == round(base + 18.50, 2)


# --- Round-lot rebate (whole-dollar subtotal) ------------------------------------

def test_round_lot_rebate_applies():
    # 10 kg inland: subtotal 10 * 4.20 = 42.00 (whole dollar) -> -2.00 -> 40.00
    assert kessler_freight_charge(10, "inland", False) == 40.00


def test_round_lot_rebate_before_surcharge():
    # rebate applies to the pre-surcharge subtotal: 42.00 - 2.00 + 18.50 = 58.50
    assert kessler_freight_charge(10, "inland", True) == 58.50


def test_no_rebate_when_cents_present():
    # 8 kg inland subtotal 33.60 has cents -> no rebate
    assert kessler_freight_charge(8, "inland", False) == 33.60


# --- Validation ------------------------------------------------------------------

def test_zero_weight_raises():
    with pytest.raises(ValueError):
        kessler_freight_charge(0, "inland", False)


def test_negative_weight_raises():
    with pytest.raises(ValueError):
        kessler_freight_charge(-5, "coastal", True)


def test_unknown_zone_raises():
    with pytest.raises(ValueError):
        kessler_freight_charge(12, "orbital", False)
