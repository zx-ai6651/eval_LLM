export function formatTime(value?: string): string {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

export function formatMoney(value?: number): string {
  return (value || 0).toFixed(6)
}

