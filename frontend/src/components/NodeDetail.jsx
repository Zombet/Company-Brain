import React from 'react'
import RiskBadge from './RiskBadge'

const LABEL_COLORS = {
  Customer: '#4ade80',
  Account: '#3b82f6',
  Transaction: '#a78bfa',
  Device: '#06b6d4',
  Address: '#84cc16',
  IP: '#e879f9',
  Alert: '#ef4444',
  Case: '#fbbf24',
  Decision: '#34d399',
  Action: '#fb923c',
  Evidence: '#a78bfa',
}

export default function NodeDetail({ node, onClose, onInvestigate }) {
  if (!node) return null

  const props = node.properties || node
  const label = node.nodeLabel || node.label || node.type || 'Node'
  const nodeId = props.id || node.id
  const badgeColor = LABEL_COLORS[label] || '#64748b'
  const riskScore = props.risk_score != null ? parseFloat(props.risk_score) : null

  return (
    <div className="node-detail">
      <div style={{display: 'flex', alignItems: 'center', marginBottom: 12}}>
        <div>
          <span className="node-type-badge" style={{background: badgeColor + '33', color: badgeColor, border: `1px solid ${badgeColor}55`}}>{label}</span>
          <h3 style={{marginTop: 4}}>{nodeId}</h3>
        </div>
        <button className="close-btn" onClick={onClose}>✕</button>
      </div>
      {riskScore != null && (
        <div style={{marginBottom: 10}}>
          <RiskBadge score={riskScore} />
          <div className="risk-bar-container">
            <div
              className="risk-bar-fill"
              style={{width: (riskScore * 100) + '%',
                background: riskScore < 0.4 ? '#4ade80' : riskScore < 0.7 ? '#f59e0b' : '#ef4444'}}
            />
          </div>
        </div>
      )}
      <table className="props-table">
        <tbody>
          {Object.entries(props).map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td style={{wordBreak: 'break-all'}}>
                {v === null || v === undefined ? <em style={{color: '#64748b'}}>null</em>
                  : typeof v === 'boolean' ? v.toString()
                  : String(v)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        className="investigate-btn"
        onClick={() => onInvestigate && onInvestigate(nodeId)}
      >
        🔍 Investigate {label.toLowerCase()}
      </button>
    </div>
  )
}
