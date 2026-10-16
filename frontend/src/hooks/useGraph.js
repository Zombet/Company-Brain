import { useState, useCallback } from 'react'

const EDGE_LABEL_MAP = {
  SENT: 'SND', TO: '→', OWNS: 'OWN', USED_DEVICE: 'USED', LOGGED_IN_FROM: 'IP',
  LIVES_AT: 'AT', HAS_PHONE: 'PH', HAS_EMAIL: '@', TRIGGERED_BY: 'TRIG',
  CONTAINS: 'HAS', HAS_EVIDENCE: 'EV', ABOUT: 'RE', EVIDENCED_BY: 'EV',
  LED_TO: '→', TARGETS: '→',
}

export function useGraph() {
  const [elements, setElements] = useState([])

  const addNodes = useCallback((nodes) => {
    setElements(prev => {
      const existingIds = new Set(prev.map(e => e.data?.id))
      const newEls = nodes
        .filter(n => !existingIds.has(n.data?.id))
        .map(n => {
          const id = n.data?.id
          return {
            data: {
              ...n.data,
              id_short: id ? String(id).substring(0, 12) : id,
              nodeLabel: n.data?.nodeLabel || n.data?.type || n.data?.label,
              shortLabel: n.data?.label ? (EDGE_LABEL_MAP[n.data.label] || n.data.label) : n.data?.label,
            },
            classes: n.classes || undefined,
          }
        })
      return [...prev, ...newEls]
    })
  }, [])

  const addPath = useCallback((pathData) => {
    if (!pathData || !pathData.path_nodes) return
    const newNodes = pathData.path_nodes.map(n => ({
      data: {
        id: n.id,
        label: n.id,
        nodeLabel: (n.labels && n.labels[0]) || 'Node',
        id_short: String(n.id).substring(0, 12),
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
          source: src,
          target: tgt,
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
        if (!existingIds.has(el.data.id)) combined.push(el)
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
        if (!existingIds.has(id)) {
          newEls.push({
            data: {
              id,
              label: n.label || id,
              nodeLabel: n.label || 'Node',
              id_short: String(id).substring(0, 12),
              ...(n.properties || {}),
            },
            classes: 'highlighted'
          })
        }
      })
      edges.forEach(e => {
        const edgeId = `${e.source}-${e.target}-${e.type}`
        if (!existingIds.has(edgeId)) {
          newEls.push({
            data: {
              id: edgeId,
              source: e.source,
              target: e.target,
              label: e.type,
              shortLabel: EDGE_LABEL_MAP[e.type] || e.type,
            },
            classes: 'highlighted-edge'
          })
        }
      })
      return [...prev, ...newEls]
    })
  }, [])

  const clearGraph = useCallback(() => setElements([]), [])

  return { elements, addNodes, addPath, addSubgraph, clearGraph }
}
