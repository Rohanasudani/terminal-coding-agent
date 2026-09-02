from checkout import final_total
from pricing import apply_discount
from tax import add_tax


def test_discount_reduces_total():
    assert apply_discount(100, 0.20) == 80


def test_tax_increases_total():
    assert add_tax(80, 0.10) == 88


def test_final_total_applies_discount_then_tax():
    assert final_total(100, 0.20, 0.10) == 88
