import React, { useState, useEffect } from 'react'
import ChatPanel from './components/ChatPanel'
import GraphPanel from './components/GraphPanel'
import { useAgent } from './hooks/useAgent'
import { useGraph } from './hooks/useGraph'

const EDGE_LABEL_MAP = {
  SENT: 'SND', TO: '→', OWNS: 'OWN', USED_DEVICE: 'USED', LOGGED_IN_FROM: 'IP',
  LIVES_AT: 'AT', HAS_PHONE: 'PH', HAS_EMAIL: '@', AT: '@', TRIGGERED_BY: 'TRIG',
  CONTAINS: 'HAS', HAS_EVIDENCE: 'EV', ABOUT: 'RE', EVIDENCED_BY: 'EV',
  LED_TO: '→', TARGETS: '→',
}

function _labelFromId(id) {
  if (!id) return 'Node'
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
  return 'Node'
}

function makeNode(id, label, props = {}, highlighted = false) {
  if (!id) return null
  const nodeLabel = label || _labelFromId(id)
  let displayLabel
  if (props.name) {
    displayLabel = props.name.split(' ')[0]
  } else {
    displayLabel = String(id)
      .replace(/^C_/, '').replace(/^A_/, '').replace(/^T_/, '')
      .replace(/^AL_/, '\u26a0 ').replace(/^CASE_/, '\ud83d\udcc1 ')
      .replace(/^ACT_/, '\u26a1 ').replace(/^DEC_/, '\u2713 ')
      .substring(0, 12)
  }
  return {
    data: {
      id: String(id), label: nodeLabel, nodeLabel, displayLabel,
      id_short: String(id).substring(0, 12),
      risk_score: props.risk_score ?? null,
      status: props.status ?? null,
      name: props.name || null,
      ...props,
    },
    classes: highlighted ? 'highlighted' : undefined,
  }
}

function makeEdge(source, target, type, highlighted = false) {
  if (!source || !target) return null
  const t = type || 'REL'
  return {
    data: {
      id: `${source}-${target}-${t}`,
      source: String(source),
      target: String(target),
      label: t,
      shortLabel: EDGE_LABEL_MAP[t] || t,
    },
    classes: highlighted ? 'highlighted-edge' : undefined,
  }
}

function safeParseObs(raw) {
  if (!raw) return null
  if (typeof raw === 'object' && !Array.isArray(raw)) return raw

  // Handle OpenRouter content-block format: '[{"type":"text","text":"{...}"}]'
  // or plain JSON string
  let str = raw
  if (Array.isArray(raw)) {
    // Already parsed array of content blocks
    const textBlock = raw.find(b => b.type === 'text')
    str = textBlock ? textBlock.text : null
  } else if (typeof raw === 'string') {
    // Try to detect content-block wrapper
    const trimmed = raw.trim()
    if (trimmed.startsWith('[{') && trimmed.includes('"type"') && trimmed.includes('"text"')) {
      try {
        const blocks = JSON.parse(trimmed)
        const textBlock = Array.isArray(blocks) && blocks.find(b => b.type === 'text')
        str = textBlock ? textBlock.text : trimmed
      } catch { str = trimmed }
    }
  }
  if (!str) return null
  try { return JSON.parse(str) } catch { return null }
}

// Extract Cytoscape elements from a single tool step
function elementsFromStep(step) {
  const els = []
  const obs = safeParseObs(step.observation)
  if (!obs) {
    console.log('[graph] no obs for tool:', step.tool, 'raw:', typeof step.observation, String(step.observation).substring(0, 100))
    return els
  }

  // Normalise tool name — strip _tool suffix added by MCP server naming
  const tool = (step.tool || '').replace(/_tool$/, '')

  if (tool === 'get_entity_profile') {
    // obs = {node: {id, name, risk_score, ...}, neighbors: [{rel, label, id, rel_props}]}
    // Only show meaningful node types — skip IP, Phone (too noisy)
    const SHOW_LABELS = ['Customer', 'Account', 'Transaction', 'Device', 'Address', 'Alert', 'Case', 'Action', 'Merchant', 'Evidence', 'Decision']
    const nodeProps = obs.node || {}
    const entityId = nodeProps.id || step.tool_input?.entity_id
    if (entityId) {
      const n = makeNode(entityId, _labelFromId(entityId), { ...nodeProps, name: nodeProps.name }, true)
      if (n) els.push(n)
      ;(obs.neighbors || []).forEach(nb => {
        if (!nb.id) return
        const nbLabel = nb.label || _labelFromId(nb.id)
        if (!SHOW_LABELS.includes(nbLabel)) return  // skip IP, Phone
        const nbNode = makeNode(nb.id, nbLabel, { name: nb.name })
        if (nbNode) els.push(nbNode)
        // Edge — both nodes now exist so it's safe
        const rel = nb.rel || 'REL'
        const e = makeEdge(entityId, nb.id, rel)
        if (e) els.push(e)
      })
    }
  }

  if (tool === 'expand_neighborhood') {
    // obs = {nodes: [{data:{id,label,properties}}], edges: [{data:{source,target,type}}]}
    const SHOW_LABELS = ['Customer', 'Account', 'Transaction', 'Device', 'Address', 'Alert', 'Case', 'Action', 'Merchant']
    const nodes = obs.nodes || []
    const edges = obs.edges || []
    nodes.forEach(n => {
      const nd = n.data || n
      const nodeLabel = nd.label || nd.nodeLabel || _labelFromId(nd.id)
      if (!SHOW_LABELS.includes(nodeLabel)) return
      const props = nd.properties || {}
      const node = makeNode(nd.id, nodeLabel, { risk_score: props.risk_score, status: props.status })
      if (node) els.push(node)
    })
    edges.forEach(e => {
      const ed = e.data || e
      // Only add edges where both nodes were added (i.e. not filtered out)
      const addedIds = new Set(els.map(x => x.data?.id))
      if (!addedIds.has(String(ed.source)) || !addedIds.has(String(ed.target))) return
      const edge = makeEdge(ed.source, ed.target, ed.type || ed.label)
      if (edge) els.push(edge)
    })
  }

  if (tool === 'find_paths') {
    // obs = [{ids:[...], rels:[...], hops:N}]
    const pathList = Array.isArray(obs) ? obs : (obs.paths || [])
    const firstPath = pathList[0]
    if (firstPath?.ids) {
      const ids = firstPath.ids
      const rels = firstPath.rels || []
      ids.forEach(id => {
        const n = makeNode(id, _labelFromId(id), {}, true)
        if (n) els.push(n)
      })
      for (let i = 0; i < ids.length - 1; i++) {
        const e = makeEdge(ids[i], ids[i + 1], rels[i], true)
        if (e) els.push(e)
      }
    }
  }

  if (tool === 'shared_attributes') {
    // obs = [{bridge_id, bridge_labels, bridge_name, bridge_risk}]
    const bridges = Array.isArray(obs) ? obs : []
    const seedA = step.tool_input?.a
    const seedB = step.tool_input?.b
    if (seedA) { const n = makeNode(seedA, _labelFromId(seedA), {}, true); if (n) els.push(n) }
    if (seedB) { const n = makeNode(seedB, _labelFromId(seedB), {}, true); if (n) els.push(n) }
    bridges.forEach(b => {
      const bid = b.bridge_id
      const blabels = b.bridge_labels || []
      const blabel = blabels[0] || _labelFromId(bid)
      const bn = makeNode(bid, blabel, { risk_score: b.bridge_risk }, true)
      if (bn) els.push(bn)
      if (seedA) { const e = makeEdge(seedA, bid, 'SHARED'); if (e) els.push(e) }
      if (seedB) { const e = makeEdge(seedB, bid, 'SHARED'); if (e) els.push(e) }
    })
  }

  if (tool === 'detect_communities') {
    // obs = {community_id, members:[{id, labels:[...], risk_score}], size}
    // Only show meaningful node types — skip IP, Phone (too noisy)
    const SHOW_LABELS = ['Customer', 'Device', 'Address']
    const members = obs.members || []
    members.forEach(m => {
      const mlabels = m.labels || []
      const mlabel = mlabels[0] || _labelFromId(m.id)
      if (!SHOW_LABELS.includes(mlabel)) return  // skip IP, Phone etc
      const n = makeNode(m.id, mlabel, { risk_score: m.risk_score, name: m.name }, true)
      if (n) els.push(n)
    })
  }

  if (tool === 'rank_central_nodes') {
    // obs = [{id, label, degree, risk_score}]
    const rankList = Array.isArray(obs) ? obs : []
    rankList.forEach(n => {
      const node = makeNode(n.id, n.label || _labelFromId(n.id), { risk_score: n.risk_score }, (n.degree || 0) > 3)
      if (node) els.push(node)
    })
  }

  if (tool === 'trace_money_flow') {
    // obs = {account_id, inbound:[{txn_id,amount,ts,src}], outbound:[{txn_id,amount,ts,dest}]}
    const srcId = obs.account_id || step.tool_input?.account_id
    if (srcId) { const n = makeNode(srcId, 'Account', {}, true); if (n) els.push(n) }
    ;(obs.outbound || []).forEach(txn => {
      if (txn.txn_id) {
        const tn = makeNode(txn.txn_id, 'Transaction', { risk_score: txn.risk_score })
        if (tn) els.push(tn)
        if (srcId) { const e = makeEdge(srcId, txn.txn_id, 'SENT'); if (e) els.push(e) }
      }
      if (txn.dest) {
        const dn = makeNode(txn.dest, 'Account', {})
        if (dn) els.push(dn)
        if (txn.txn_id) { const e = makeEdge(txn.txn_id, txn.dest, 'TO'); if (e) els.push(e) }
      }
    })
    ;(obs.inbound || []).forEach(txn => {
      if (txn.src) {
        const sn = makeNode(txn.src, 'Account', {})
        if (sn) els.push(sn)
        if (txn.txn_id) { const e = makeEdge(txn.src, txn.txn_id, 'SENT'); if (e) els.push(e) }
        if (srcId && txn.txn_id) { const e = makeEdge(txn.txn_id, srcId, 'TO'); if (e) els.push(e) }
      }
    })
  }

  if (tool === 'detect_circular_flow') {
    // obs = {cycle_found, path:[A_omar1, A_diana1, A_felix1, A_omar1], amounts, timestamps}
    if (obs.cycle_found && obs.path) {
      const path = obs.path
      const uniqueIds = [...new Set(path)]
      uniqueIds.forEach(id => {
        const n = makeNode(id, _labelFromId(id), {}, true)
        if (n) els.push(n)
      })
      // Add cycle edges
      for (let i = 0; i < path.length - 1; i++) {
        const e = makeEdge(path[i], path[i + 1], 'SENT', true)
        if (e) els.push(e)
      }
    }
  }

  return els.filter(Boolean)
}

export default function App() {
  const [status, setStatus] = useState('checking')
  const [prefilledQuery, setPrefilledQuery] = useState('')
  const { sendQuery, messages, isLoading } = useAgent()
  const { elements, addNodes, clearGraph } = useGraph()

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then(r => r.json())
      .then(d => setStatus(d.falkordb === 'connected' ? 'connected' : 'error'))
      .catch(() => setStatus('error'))
  }, [])

  const handleNodeInvestigate = (id) => setPrefilledQuery(`Investigate ${id}`)

  const handleSend = (query) => {
    setPrefilledQuery('')
    clearGraph()

    sendQuery(query, (update) => {
      if (!update?.steps) return
      const newEls = []
      update.steps.forEach(step => {
        try {
          const els = elementsFromStep(step)
          els.forEach(el => newEls.push(el))
        } catch (e) {
          console.warn('elementsFromStep error:', e, step)
        }
      })
      if (newEls.length > 0) {
        console.log('[graph] adding', newEls.length, 'elements from', update.steps.map(s => s.tool))
        addNodes(newEls)
      } else {
        console.log('[graph] no elements from steps:', update.steps.map(s => s.tool))
      }

      // After final result, fetch neighborhood for the seed entity to get edges
      if (!update.partial && update.steps?.length > 0) {
        // Find any entity ID from the first tool call
        const firstStep = update.steps[0]
        const seedId = firstStep?.tool_input?.entity_id ||
                       firstStep?.tool_input?.seed_id ||
                       firstStep?.tool_input?.account_id ||
                       firstStep?.tool_input?.a
        if (seedId) {
          fetch(`http://localhost:8000/api/entity/${seedId}/neighborhood?depth=1`)
            .then(r => r.json())
            .then(data => {
              const SHOW_LABELS = ['Customer', 'Account', 'Transaction', 'Device', 'Address', 'Alert', 'Case', 'Action']
              const extraEls = []
              const addedIds = new Set()
              // First pass: nodes only (filtered)
              ;(data.nodes || []).forEach(n => {
                const nd = n.data || n
                const lbl = nd.label || nd.nodeLabel || ''
                if (!SHOW_LABELS.includes(lbl)) return
                const props = nd.properties || {}
                const node = makeNode(nd.id, lbl, { risk_score: props.risk_score, status: props.status })
                if (node) { extraEls.push(node); addedIds.add(String(nd.id)) }
              })
              // Second pass: edges only if BOTH endpoints exist
              ;(data.edges || []).forEach(e => {
                const ed = e.data || e
                const src = String(ed.source || '')
                const tgt = String(ed.target || '')
                if (!src || !tgt || !addedIds.has(src) || !addedIds.has(tgt)) return
                const edge = makeEdge(src, tgt, ed.type || ed.label)
                if (edge) extraEls.push(edge)
              })
              if (extraEls.length > 0) addNodes(extraEls)
            })
            .catch(() => {})
        }
      }
    })
  }

  return (
    <div id="app" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <header className="header">
        <div
          className={`status-dot ${status === 'connected' ? 'connected' : ''}`}
          title={`FalkorDB: ${status}`}
        />
        <h1>🔍 Fraud Investigation Agent</h1>
        <span style={{ marginLeft: 'auto', color: '#64748b', fontSize: '0.8rem' }}>
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
