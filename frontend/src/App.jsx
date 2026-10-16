import React, { useState, useEffect } from 'react'
import ChatPanel from './components/ChatPanel'
import GraphPanel from './components/GraphPanel'
import { useAgent } from './hooks/useAgent'
import { useGraph } from './hooks/useGraph'
import { getOverview, getNeighbors } from './api/client'

export default function App() {
  const [status, setStatus] = useState('checking')
  const [history, setHistory] = useState([])
  const { sendQuery, messages, isLoading } = useAgent()
  const { elements, addNodes, addPath, clearGraph } = useGraph()

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then(r => r.json())
      .then(d => setStatus(d.falkordb === 'connected' ? 'connected' : 'error'))
      .catch(() => setStatus('error'))
  }, [])

  const handleSend = (query) => {
    sendQuery(query, (result) => {
      // When agent finishes, try to load neighbor graph for any account mentioned
      if (result?.steps) {
        result.steps.forEach(step => {
          if (step.tool === 'get_risk_neighbors' || step.tool === 'trace_fraud_ring') {
            try {
              const accountId = step.tool_input?.account_id
              if (accountId) {
                getNeighbors(accountId).then(r => {
                  const neighbors = r.data?.neighbors || []
                  const newNodes = [
                    { data: { id: accountId, label: accountId, type: 'Account' } },
                    ...neighbors.map(n => ({
                      data: {
                        id: n.neighbor_id,
                        label: n.neighbor_id,
                        type: (n.neighbor_labels && n.neighbor_labels[0]) || 'Node',
                        risk_score: n.risk_score,
                        status: n.status,
                      }
                    })),
                  ]
                  const newEdges = neighbors.map(n => ({
                    data: {
                      id: `${accountId}-${n.neighbor_id}-${n.relationship_type}`,
                      source: accountId,
                      target: n.neighbor_id,
                      label: n.relationship_type,
                    }
                  }))
                  addNodes([...newNodes, ...newEdges])
                }).catch(() => {})
              }
            } catch (e) {}
          }
          if (step.tool === 'get_transaction_path') {
            try {
              const obs = typeof step.observation === 'string' ? JSON.parse(step.observation) : step.observation
              if (obs?.path_nodes) addPath(obs)
            } catch (e) {}
          }
        })
      }
    })
  }

  return (
    <div id="app" style={{display: 'flex', flexDirection: 'column', height: '100vh'}}>
      <header className="header">
        <div
          className={`status-dot ${status === 'connected' ? 'connected' : ''}`}
          title={`FalkorDB: ${status}`}
        />
        <h1>🔍 Fraud Investigation Agent</h1>
        <span style={{marginLeft: 'auto', color: '#64748b', fontSize: '0.8rem'}}>
          FalkorDB · Groq · LangChain
        </span>
      </header>
      <div className="layout">
        <ChatPanel
          messages={messages}
          isLoading={isLoading}
          onSend={handleSend}
          history={history}
        />
        <GraphPanel
          elements={elements}
          onNodeSelect={() => {}}
          onInvestigate={(query) => handleSend(query)}
        />
      </div>
    </div>
  )
}
