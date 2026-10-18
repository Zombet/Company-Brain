import { useState, useCallback } from 'react'

const EDGE_LABEL_MAP = {
  SENT: 'sent', TO: 'to', OWNS: 'owns', USED_DEVICE: 'device',
  LOGGED_IN_FROM: 'IP', LIVES_AT: 'address', HAS_PHONE: 'phone',
  AT: 'at', TRIGGERED_BY: 'alert', CONTAINS: 'has',
  HAS_EVIDENCE: 'ev', ABOUT: 'about', EVIDENCED_BY: 'ev',
  LED_TO: 'led to', TARGETS: 'targets', SHARED: 'shared',
}

function makeDisplayLabel(id) {
  if (!id) return ''
  return String(id)
    .replace(/^C_/, '').replace(/^A_/, '').replace(/^T_/, '')
    .replace(/^AL_/, '⚠ ').replace(/^CASE_/, '📁 ')
    .replace(/^ACT_/, '⚡ ').replace(/^DEC_/, '✓ ')
    .substring(0, 14)
}

export function useGraph() {
  const [elements, setElements] = useState([])

  const addNodes = useCallback((nodes) => {
    setElements(prev => {
      const existingIds = new Set(prev.map(e => e.data?.id))
      const newEls = []
      nodes.forEach(n => {
        const id = n.data?.id
        if (!id || existingIds.has(id)) return
        existingIds.add(id)
        newEls.push({
          data: {
            ...n.data,
            displayLabel: n.data?.displayLabel || makeDisplayLabel(id),
            nodeLabel: n.data?.nodeLabel || n.data?.label || n.data?.type || '',
            shortLabel: n.data?.label ? (EDGE_LABEL_MAP[n.data.label] || n.data.label) : '',
          },
          classes: n.classes || undefined,
        })
      })
      return newEls.length > 0 ? [...prev, ...newEls] : prev
    })
  }, [])

  const addPath = useCallback((pathData) => {
    if (!pathData?.path_nodes) return
    const newNodes = pathData.path_nodes.map(n => ({
      data: {
        id: n.id,
        label: (n.labels && n.labels[0]) || 'Node',
        nodeLabel: (n.labels && n.labels[0]) || 'Node',
        displayLabel: makeDisplayLabel(n.id),
        risk_score: n.risk_score,
      },
      classes: 'highlighted'
    }))
    const newEdges = []
    for (let i = 0; i < pathData.path_nodes.length - 1; i++) {
      const src = pathData.path_nodes[i].id
      const tgt = pathData.path_nodes[i + 1].id
      const relType = pathData.path_rels?.[i]?.type || ''
      newEdges.push({
        data: {
          id: `path-${src}-${tgt}`,
          source: src, target: tgt,
          label: relType,
          shortLabel: EDGE_LABEL_MAP[relType] || relType,
        },
        classes: 'highlighted-edge'
      })
    }
    setElements(prev => {
      const existingIds = new Set(prev.map(e => e.data?.id))
      const combined = [...prev]
      ;[...newNodes, ...newEdges].forEach(el => {
        if (!existingIds.has(el.data.id)) {
          existingIds.add(el.data.id)
          combined.push(el)
        }
      })
      return combined
    })
  }, [])

  const addSubgraph = useCallback((subgraphData) => {
    if (!subgraphData) return
    const { nodes = [], edges = [] } = subgraphData
    setElements(prev => {
      const existingIds = new Set(prev.map(e => e.data?.id))
      const newEls = []
      nodes.forEach(n => {
        const id = n.id
        if (!id || existingIds.has(id)) return
        existingIds.add(id)
        newEls.push({
          data: {
            id, label: n.label || id,
            nodeLabel: n.label || 'Node',
            displayLabel: makeDisplayLabel(id),
            ...(n.properties || {}),
          },
          classes: 'highlighted'
        })
      })
      edges.forEach(e => {
        const edgeId = `${e.source}-${e.target}-${e.type}`
        if (existingIds.has(edgeId)) return
        existingIds.add(edgeId)
        newEls.push({
          data: {
            id: edgeId, source: e.source, target: e.target,
            label: e.type,
            shortLabel: EDGE_LABEL_MAP[e.type] || e.type,
          },
          classes: 'highlighted-edge'
        })
      })
      return newEls.length > 0 ? [...prev, ...newEls] : prev
    })
  }, [])

  const clearGraph = useCallback(() => setElements([]), [])

  return { elements, addNodes, addPath, addSubgraph, clearGraph }
}
