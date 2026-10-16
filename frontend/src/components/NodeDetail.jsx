import React from 'react'
import RiskBadge from './RiskBadge'

export default function NodeDetail({ node, onClose, onInvestigate }) {
  if (!node) return null

  const props = node.properties || node
  const label = node.label || node.type || 'Node'

  return (
    <div className="node-detail">
      <div style={{display: 'flex', alignItems: 'center', marginBottom: 12}}>
        <h3>{label}: {props.id || node.id}</h3>
        <button className="close-btn" onClick={onClose}>✕</button>
      </div>
      {props.risk_score != null && (
        <div style={{marginBottom: 10}}>
          <RiskBadge score={props.risk_score} />
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
      {(label === 'Account' || props.id?.startsWith?.('ACC')) && (
        <button
          className="investigate-btn"
          onClick={() => onInvestigate && onInvestigate(props.id || node.id)}
        >
          🔍 Investigate this account
        </button>
      )}
    </div>
  )
}
