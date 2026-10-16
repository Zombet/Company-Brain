import React, { useState, useEffect } from 'react'
import ChatPanel from './components/ChatPanel'
import GraphPanel from './components/GraphPanel'
import { useAgent } from './hooks/useAgent'
import { useGraph } from './hooks/useGraph'
import { getOverview } from './api/client'

const EDGE_LABEL_MAP = {
  SENT: 'SND', TO: '→', OWNS: 'OWN', USED_DEVICE: 'USED', LOGGED_IN_FROM: 'IP',
  LIVES_AT: 'AT', HAS_PHONE: 'PH', HAS_EMAIL: '@', TRIGGERED_BY: 'TRIG',
  CONTAINS: 'HAS', HAS_EVIDENCE: 'EV', ABOUT: 'RE', EVIDENCED_BY: 'EV',
  LED_TO: '→', TARGETS: '→',
}

function makeNode(id, label, props = {}) {
  return {
    data: {
      id,
      label,
      nodeLabel: label,
      id_short: String(id).substring(0, 12),
      ...props,
    }
  }
}

function makeEdge(source, target, type, extraProps = {}) {
  return {
    data: {
      id: `${source}-${target}-${type}`,
      source,
      target,
      label: type,
      shortLabel: EDGE_LABEL_MAP[type] || type,
      ...extraProps,
    }
  }
}

export default function App() {
  const [status, setStatus] = useState('checking')
  const [prefilledQuery, setPrefilledQuery] = useState('')
  const { sendQuery, messages, isLoading } = useAgent()
  const { elements, addNodes, addPath, addSubgraph, clearGraph } = useGraph()

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then(r => r.json())
      .then(d => setStatus(d.falkordb === 'connected' ? 'connected' : 'error'))
      .catch(() => setStatus('error'))
  }, [])

  const handleNodeInvestigate = (id) => {
    setPrefilledQuery(`Investigate ${id}`)
  }

  const handleSend = (query) => {
    setPrefilledQuery('')
    sendQuery(query, (result) => {
      if (result?.steps) {
        const allEls = []
        result.steps.forEach(step => {
          try {
            const obs = typeof step.observation === 'string'
              ? JSON.parse(step.observation)
              : step.observation

            if (step.tool === 'get_entity_profile' && obs?.node) {
              const n = obs.node
              allEls.push(makeNode(n.id, n.label || 'Node', { risk_score: n.risk_score, status: n.status }))
            }

            if (step.tool === 'expand_neighborhood') {
              const nodes = obs?.nodes || []
              const edges = obs?.edges || []
              nodes.forEach(n => allEls.push(makeNode(n.id, n.label || 'Node', { risk_score: n.risk_score, status: n.status })))
              edges.forEach(e => allEls.push(makeEdge(e.source, e.target, e.type)))
            }

            if (step.tool === 'find_paths' && obs?.paths) {
              const firstPath = obs.paths[0]
              if (firstPath?.nodes) {
                const pathNodes = firstPath.nodes.map(n => ({
                  ...makeNode(n.id, n.label || 'Node', { risk_score: n.risk_score, status: n.status }),
                  classes: 'highlighted'
                }))
                const pathEdges = []
                for (let i = 0; i < firstPath.nodes.length - 1; i++) {
                  pathEdges.push({ ...makeEdge(firstPath.nodes[i].id, firstPath.nodes[i+1].id, firstPath.rels?.[i]?.type || 'REL'), classes: 'highlighted-edge' })
                }
                allEls.push(...pathNodes, ...pathEdges)
              } else if (obs?.path_nodes) {
                addPath(obs)
              }
            }

            if (step.tool === 'detect_communities' && obs?.members) {
              obs.members.forEach(n => {
                allEls.push({ ...makeNode(n.id, n.label || 'Node', { risk_score: n.risk_score }), classes: 'highlighted' })
              })
            }

            if (step.tool === 'rank_central_nodes' && obs?.nodes) {
              obs.nodes.forEach(n => {
                const el = makeNode(n.id, n.label || 'Node', { risk_score: n.risk_score, degree: n.degree })
                if ((n.degree || 0) > 3) el.classes = 'highlighted'
                allEls.push(el)
              })
            }

            if (step.tool === 'trace_money_flow' && obs) {
              const accts = [...(obs.inbound || []), ...(obs.outbound || [])]
              accts.forEach(n => allEls.push(makeNode(n.id || n.account_id, 'Account', { status: n.status })))
            }

            if (step.tool === 'score_cluster' && obs?.members) {
              obs.members.forEach(n => allEls.push(makeNode(n.id, n.label || 'Node', { risk_score: n.risk_score })))
            }

            if (obs?.subgraph) {
              addSubgraph(obs.subgraph)
            }
          } catch (e) {
            // JSON parse might fail for non-JSON observations
          }
        })

        if (result?.subgraph) {
          addSubgraph(result.subgraph)
        } else if (allEls.length > 0) {
          addNodes(allEls)
        }
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
          prefilledQuery={prefilledQuery}
        />
        <GraphPanel
          elements={elements}
          onNodeSelect={() => {}}
          onInvestigate={(query) => handleSend(query)}
          onNodeInvestigate={handleNodeInvestigate}
        />
      </div>
    </div>
  )
}
