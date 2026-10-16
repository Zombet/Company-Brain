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

// Mirrors the ID-prefix convention from queries.py so we can guess node labels
// when the backend doesn't return them explicitly.
function _labelFromId(id) {
  if (!id) return null
  if (id.startsWith('C_')) return 'Customer'
  if (id.startsWith('A_')) return 'Account'
  if (id.startsWith('T_')) return 'Transaction'
  if (id.startsWith('D_')) return 'Device'
  if (id.startsWith('ADDR_')) return 'Address'
  if (id.startsWith('IP_')) return 'IP'
  if (id.startsWith('PH_')) return 'Phone'
  if (id.startsWith('M_')) return 'Merchant'
  if (id.startsWith('AL_')) return 'Alert'
  if (id.startsWith('CASE_')) return 'Case'
  if (id.startsWith('EV_')) return 'Evidence'
  if (id.startsWith('DEC_')) return 'Decision'
  if (id.startsWith('ACT_')) return 'Action'
  return null
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

            // Normalize tool name: strip trailing _tool suffix so comparisons work
            // regardless of whether the MCP server appends it.
            const toolName = (step.tool || '').replace(/_tool$/, '')

            if (toolName === 'get_entity_profile' && obs?.node) {
              const n = obs.node
              const nodeLabel = n.label || _labelFromId(n.id) || 'Node'
              allEls.push(makeNode(n.id, nodeLabel, { risk_score: n.risk_score, status: n.status }))
              // Also render neighbours as nodes
              ;(obs.neighbors || []).forEach(nb => {
                if (nb.id) {
                  const nbLabel = nb.label || _labelFromId(nb.id) || 'Node'
                  allEls.push(makeNode(nb.id, nbLabel, {}))
                  allEls.push(makeEdge(n.id, nb.id, nb.rel || 'REL'))
                }
              })
            }

            if (toolName === 'expand_neighborhood') {
              // Each item is {data: {id, label, properties}} / {data: {source, target, type}}
              const nodes = obs?.nodes || []
              const edges = obs?.edges || []
              nodes.forEach(n => {
                const nd = n.data || n
                const nodeLabel = nd.label || _labelFromId(nd.id) || 'Node'
                const props = nd.properties || {}
                allEls.push(makeNode(nd.id, nodeLabel, { risk_score: props.risk_score, status: props.status }))
              })
              edges.forEach(e => {
                const ed = e.data || e
                allEls.push(makeEdge(ed.source, ed.target, ed.type || ed.label || 'REL'))
              })
            }

            if (toolName === 'find_paths') {
              // find_paths returns [{ids, rels, hops}]
              const pathList = Array.isArray(obs) ? obs : obs?.paths || []
              const firstPath = pathList[0]
              if (firstPath?.ids) {
                const ids = firstPath.ids
                const rels = firstPath.rels || []
                ids.forEach(id => {
                  const nodeLabel = _labelFromId(id) || 'Node'
                  allEls.push({ ...makeNode(id, nodeLabel, {}), classes: 'highlighted' })
                })
                for (let i = 0; i < ids.length - 1; i++) {
                  allEls.push({ ...makeEdge(ids[i], ids[i + 1], rels[i] || 'REL'), classes: 'highlighted-edge' })
                }
              } else if (obs?.path_nodes) {
                addPath(obs)
              }
            }

            if (toolName === 'detect_communities' && obs?.members) {
              obs.members.forEach(n => {
                const nodeLabel = (n.labels && n.labels[0]) || n.label || _labelFromId(n.id) || 'Node'
                allEls.push({ ...makeNode(n.id, nodeLabel, { risk_score: n.risk_score }), classes: 'highlighted' })
              })
            }

            if (toolName === 'rank_central_nodes') {
              // rank_central_nodes returns a list directly
              const rankList = Array.isArray(obs) ? obs : obs?.nodes || []
              rankList.forEach(n => {
                const nodeLabel = n.label || _labelFromId(n.id) || 'Node'
                const el = makeNode(n.id, nodeLabel, { risk_score: n.risk_score, degree: n.degree })
                if ((n.degree || 0) > 3) el.classes = 'highlighted'
                allEls.push(el)
              })
            }

            if (toolName === 'trace_money_flow' && obs) {
              const accts = [...(obs.inbound || []), ...(obs.outbound || [])]
              accts.forEach(n => allEls.push(makeNode(n.id || n.account_id, 'Account', { status: n.status })))
            }

            if (toolName === 'score_cluster' && obs?.members) {
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
