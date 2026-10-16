import React from 'react'

export default function RiskBadge({ score }) {
  if (score == null) return null
  const cls = score < 0.3 ? 'risk-low' : score < 0.7 ? 'risk-medium' : 'risk-high'
  const label = score < 0.3 ? 'Low' : score < 0.7 ? 'Medium' : 'High'
  return (
    <span className={`risk-badge ${cls}`}>
      Risk: {label} ({(score * 100).toFixed(0)}%)
    </span>
  )
}
