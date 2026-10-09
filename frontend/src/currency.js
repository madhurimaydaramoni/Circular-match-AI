const indianNumberFormat = new Intl.NumberFormat('en-IN')
const indianCurrencyFormat = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

export function formatINR(value) {
  return indianCurrencyFormat.format(value)
}

export function formatINRPerTonne(value) {
  return `${formatINR(value)}/tonne`
}

export function formatIndianNumber(value) {
  return indianNumberFormat.format(value)
}

export const defaultLocale = 'en-IN'
