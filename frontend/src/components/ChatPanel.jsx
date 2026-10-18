import React, { useState, useRef, useEffect } from 'react'
import ToolCallLog from './ToolCallLog'
import SessionHistory from './SessionHistory'

const EXAMPLE_QUERIES = [
  'Investigate C_kunal',
  'Find fraud ring from AL_ring_alert',
  'Trace mule chain from C_john',
  'Find path between C_kunal and C_kingpin',
]

const SCENARIO_CHIPS = [
  { name: 'Fraud Ring', query: 'Investigate the fraud ring starting from C_kunal' },
  { name: 'Mule Chain', query: 'Trace the mule chain starting from A_john1' },
  { name: 'Circular Flow', query: 'Find circular money flow involving C_omar' },
  { name: 'Decoy Family', query: 'Investigate C_raj - should this family be flagged?' },
  { name: 'Kingpin', query: 'Find path between C_kunal and C_john to identify the kingpin bridge account connecting the fraud ring and mule chain' },
]

function renderMarkdown(text) {
  // Guard against non-string input
  if (!text) return ''
  if (typeof text !== 'string') {
    try { text = JSON.stringify(text, null, 2) } catch { text = String(text) }
  }
  const lines = text.split('\n')
  const result = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (line.trim().startsWith('|')) {
      const tableLines = []
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        tableLines.push(lines[i])
        i++
      }
      const nonSep = tableLines.filter(l => !/^\s*\|[-| :]+\|\s*$/.test(l))
      if (nonSep.length > 0) {
        const parseRow = (l) => l.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1).map(c => c.trim())
        const [headerRow, ...bodyRows] = nonSep
        const headers = parseRow(headerRow)
        const rows = bodyRows.map(parseRow)
        result.push('<table class="md-table"><thead><tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr></thead><tbody>' + rows.map(r => '<tr>' + r.map(c => `<td>${c}</td>`).join('') + '</tr>').join('') + '</tbody></table>')
      }
    } else {
      result.push(line)
      i++
    }
  }
  let html = result.join('\n')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/&lt;br&gt;/g, '<br/>')
  html = html.replace(/<br>/gi, '<br/>')
  html = html.replace(/\n/g, '<br/>')
  return html
}

export default function ChatPanel({ messages, isLoading, onSend, history, prefilledQuery }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (prefilledQuery) setInput(prefilledQuery)
  }, [prefilledQuery])

  const handleSend = () => {
    const q = input.trim()
    if (!q || isLoading) return
    onSend(q)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-panel">
      <div className="message-list">
        {messages.length === 0 && (
          <div style={{color: '#64748b', textAlign: 'center', marginTop: 40, fontSize: '0.9rem'}}>
            <div style={{fontSize: '2rem', marginBottom: 8}}>🔍</div>
            Start an investigation by typing a query or selecting an example below.
          </div>
        )}
        {messages.map(msg => (
          <div key={msg.id}>
            {msg.role === 'user' ? (
              <div className="user-message">{msg.content}</div>
            ) : (
              <div className="agent-message">
                {(() => {
                  try {
                    return <div dangerouslySetInnerHTML={{__html: renderMarkdown(msg.content)}} />
                  } catch (e) {
                    return <div style={{color:'#ef4444'}}>Render error: {String(msg.content).slice(0,200)}</div>
                  }
                })()}
                {msg.steps && msg.steps.length > 0 && (
                  <ToolCallLog steps={msg.steps} />
                )}
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            Investigating...
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <SessionHistory history={history} />
      <div className="query-chips">
        {EXAMPLE_QUERIES.map(q => (
          <button key={q} className="chip" onClick={() => onSend(q)}>{q}</button>
        ))}
      </div>
      <div className="scenario-chips">
        <span style={{fontSize: '0.72rem', color: '#f59e0b', marginRight: 6, alignSelf: 'center'}}>Demo Scenarios:</span>
        {SCENARIO_CHIPS.map(s => (
          <button key={s.name} className="scenario-chip" onClick={() => onSend(s.query)}>{s.name}</button>
        ))}
      </div>
      <div className="query-input-area">
        <textarea
          className="query-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about a transaction, account, or fraud pattern..."
          rows={1}
        />
        <button className="send-btn" onClick={handleSend} disabled={isLoading || !input.trim()}>Send</button>
      </div>
    </div>
  )
}
