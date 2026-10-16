import React, { useState } from 'react'

const TOOL_COLORS = {
  get_connected_accounts: '#3b82f6',
  trace_fraud_ring: '#ef4444',
  get_transaction_path: '#f97316',
  get_investigation_history: '#8b5cf6',
  flag_account: '#dc2626',
  get_risk_neighbors: '#22c55e',
}

export default function ToolCallLog({ steps }) {
  const [expanded, setExpanded] = useState({})
  if (!steps || steps.length === 0) return null

  return (
    <div style={{marginTop: 8}}>
      {steps.map((step, i) => {
        const color = TOOL_COLORS[step.tool] || '#64748b'
        const isOpen = expanded[i]
        return (
          <div key={i} className="tool-call-log">
            <div
              className="tool-call-header"
              onClick={() => setExpanded(prev => ({ ...prev, [i]: !prev[i] }))}
            >
              <span
                className="tool-badge"
                style={{ background: color + '22', color, border: `1px solid ${color}55` }}
              >
                {step.tool}
              </span>
              <span style={{color: '#94a3b8', fontSize: '0.75rem'}}>
                {isOpen ? '▲' : '▼'}
              </span>
            </div>
            {isOpen && (
              <div className="tool-call-body">
                <div style={{marginBottom: 6, color: '#94a3b8', fontSize: '0.75rem'}}>Input:</div>
                <pre style={{fontSize: '0.75rem', color: '#e2e8f0'}}>
                  {JSON.stringify(step.tool_input, null, 2)}
                </pre>
                <div style={{marginTop: 8, marginBottom: 4, color: '#94a3b8', fontSize: '0.75rem'}}>Output:</div>
                <pre style={{fontSize: '0.75rem', color: '#e2e8f0', maxHeight: 200, overflow: 'auto'}}>
                  {typeof step.observation === 'string' ? step.observation : JSON.stringify(step.observation, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
