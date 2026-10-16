import React from 'react'

export default function SessionHistory({ history }) {
  if (!history || history.length === 0) return null

  return (
    <div className="session-history">
      <h4>Past Sessions</h4>
      {history.slice(0, 5).map((s, i) => (
        <div key={i} className="session-item">
          <div style={{fontSize: '0.82rem', marginBottom: 2}}>
            {s.query?.slice(0, 60)}{s.query?.length > 60 ? '...' : ''}
          </div>
          <div className="session-date">
            {s.started_at ? new Date(s.started_at * 1000).toLocaleString() : 'Unknown date'}
          </div>
        </div>
      ))}
    </div>
  )
}
