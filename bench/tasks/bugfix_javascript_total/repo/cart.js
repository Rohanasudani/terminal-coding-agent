function totalWithTax(subtotal, taxRate) {
  return subtotal * (1 - taxRate);
}

module.exports = { totalWithTax };
