const assert = require("assert");
const { totalWithTax } = require("./cart");

assert.equal(totalWithTax(100, 0.08), 108);
assert.equal(totalWithTax(50, 0.2), 60);
