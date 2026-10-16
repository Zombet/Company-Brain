import { useState, useCallback } from 'react'

export function useGraph() {
  const [elements, setElements] = useState([])

  const addNodes = useCallback((nodes) => {
    setElements(prev => {
      const existingIds = new Set(prev.map(e => e.data?.id))
      const newEls = nodes
        .filter(n => !existingIds.has(n.data?.id))
        .map(n => ({ data: n.data }))
      return [...prev, ...newEls]
    })
  }, [])

  const addPath = useCallback((pathData) => {
    if (!pathData || !pathData.path_nodes) return
    const newNodes = pathData.path_nodes.map(n => ({
      data: {
        id: n.id,
        label: n.id,
        type: (n.labels && n.labels[0]) || 'Node',
        risk_score: n.risk_score,
        classes: 'highlighted'
      }
    }))
    const newEdges = []
    for (let i = 0; i < pathData.path_nodes.length - 1; i++) {
      const src = pathData.path_nodes[i].id
      const tgt = pathData.path_nodes[i + 1].id
      const rel = pathData.path_rels?.[i]
      newEdges.push({
        data: {
          id: `path-${src}-${tgt}`,
          source: src,
          target: tgt,
          label: rel?.type || '',
          classes: 'traversal-path'
        }
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

  const clearGraph = useCallback(() => setElements([]), [])

  return { elements, addNodes, addPath, clearGraph }
}
