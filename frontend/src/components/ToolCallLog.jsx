import React, { useState } from 'react'

const TOOL_COLORS = {
  // Read tools - blue palette
  get_entity_profile: '#3b82f6',
  expand_neighborhood: '#60a5fa',
  find_paths: '#93c5fd',
  shared_attributes: '#38bdf8',
  detect_communities: '#22d3ee',
  rank_central_nodes: '#67e8f9',
  trace_money_flow: '#a5f3fc',
  score_cluster: '#7dd3fc',
  // Action tools - red/orange palette
  freeze_account: '#ef4444',
  open_case: '#f97316',
  flag_cluster: '#dc2626',
  escalate_to_human: '#b45309',
}

function renderInputTable(input) {
  if (!input || typeof input !== 'object') {
    return <p style={{fontSize: '0.75rem', color: '#e2e8f0'}}>{String(input)}</p>
  }
  return (
    <table className="kv-table">
      <tbody>
        {Object.entries(input).map(([k, v]) => (
          <tr key={k}>
            <td>{k}</td>
            <td>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function renderObsSummary(observation) {
  let text = typeof observation === 'string' ? observation : JSON.stringify(observation)
  text = text.replace(/^[\[{]/, '').replace(/[\]}]$/, '').trim()
  const first200 = text.slice(0, 200)
  return <p className="obs-summary">{first200}{text.length > 200 ? '...' : ''}</p>
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
              <span style={{color: '#94a3b8', fontSize: '0.75rem'}}>{isOpen ? '▲' : '▼'}</span>
            </div>
            {isOpen && (
              <div className="tool-call-body">
                <div style={{marginBottom: 6, color: '#94a3b8', fontSize: '0.75rem'}}>Input:</div>
                {renderInputTable(step.tool_input)}
                <div style={{marginTop: 8, marginBottom: 4, color: '#94a3b8', fontSize: '0.75rem'}}>Output:</div>
                {renderObsSummary(step.observation)}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
