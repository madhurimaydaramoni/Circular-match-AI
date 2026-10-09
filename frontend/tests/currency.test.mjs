import assert from 'node:assert/strict'
import test from 'node:test'
import { defaultLocale, formatINR, formatINRPerTonne, formatIndianNumber } from '../src/currency.js'

test('formats rupees and large numbers with the Indian locale', () => {
  assert.equal(defaultLocale, 'en-IN')
  assert.equal(formatINR(43810), '₹43,810')
  assert.equal(formatINR(125000), '₹1,25,000')
  assert.equal(formatINR(125000.5), '₹1,25,000.5')
  assert.equal(formatINRPerTonne(43810), '₹43,810/tonne')
  assert.equal(formatIndianNumber(125000), '1,25,000')
})
