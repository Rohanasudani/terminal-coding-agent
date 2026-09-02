from pricing import apply_discount
from tax import add_tax


def final_total(subtotal, discount_rate, tax_rate):
    discounted = apply_discount(subtotal, discount_rate)
    return add_tax(discounted, tax_rate)
