import React, { useEffect, useRef, useState, useCallback } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import NodeDetail from './NodeDetail'
import { getOverview } from '../api/client'

const EDGE_LABEL_MAP = {
  SENT: 'sent', TO: 'to', OWNS: 'owns', USED_DEVICE: 'device',
  LOGGED_IN_FROM: 'IP', LIVES_AT: 'address', HAS_PHONE: 'phone',
  AT: 'at', TRIGGERED_BY: 'alert', CONTAINS: 'has',
  HAS_EVIDENCE: 'evidence', ABOUT: 'about', EVIDENCED_BY: 'evidence',
  LED_TO: 'led to', TARGETS: 'targets', SHARED: 'shared',
}

// Node color by label
const NODE_COLORS = {
  Customer:    '#4ade80',
  Account:     '#3b82f6',
  Transaction: '#a78bfa',
  Device:      '#06b6d4',
  Address:     '#84cc16',
  IP:          '#e879f9',
  Phone:       '#f472b6',
  Alert:       '#ef4444',
  Case:        '#fbbf24',
  Decision:    '#34d399',
  Action:      '#fb923c',
  Evidence:    '#c084fc',
  Merchant:    '#fcd34d',
}

const STYLESHEET = [
  {
    selector: 'node',
    style: {
      'background-color': '#64748b',
      'label': 'data(displayLabel)',
      'color': '#ffffff',
      'font-size': '11px',
      'font-weight': 'bold',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': '4px',
      'text-outline-width': 2,
      'text-outline-color': '#0f172a',
      'width': 44,
      'height': 44,
      'border-width': 2,
      'border-color': '#334155',
      'shape': 'ellipse',
    }
  },
  // Customer — green circle
  { selector: 'node[nodeLabel="Customer"]', style: { 'background-color': '#4ade80', 'shape': 'ellipse', 'color': '#052e16' } },
  // Account — blue square
  { selector: 'node[nodeLabel="Account"]', style: { 'background-color': '#3b82f6', 'shape': 'rectangle', 'color': '#fff' } },
  { selector: 'node[nodeLabel="Account"][status="frozen"]', style: { 'background-color': '#ef4444' } },
  // Transaction — purple triangle
  { selector: 'node[nodeLabel="Transaction"]', style: { 'background-color': '#a78bfa', 'shape': 'triangle', 'width': 40, 'height': 40, 'color': '#fff' } },
  { selector: 'node[nodeLabel="Transaction"][status="flagged"]', style: { 'background-color': '#f59e0b' } },
  // Device — cyan diamond
  { selector: 'node[nodeLabel="Device"]', style: { 'background-color': '#06b6d4', 'shape': 'diamond', 'width': 48, 'height': 48 } },
  // Address — lime hexagon
  { selector: 'node[nodeLabel="Address"]', style: { 'background-color': '#84cc16', 'shape': 'hexagon', 'width': 48, 'height': 48 } },
  // IP — fuchsia star
  { selector: 'node[nodeLabel="IP"]', style: { 'background-color': '#e879f9', 'shape': 'star', 'width': 36, 'height': 36 } },
  // Alert — red octagon, large
  { selector: 'node[nodeLabel="Alert"]', style: { 'background-color': '#ef4444', 'shape': 'octagon', 'width': 52, 'height': 52 } },
  // Case — yellow round-rectangle
  { selector: 'node[nodeLabel="Case"]', style: { 'background-color': '#fbbf24', 'shape': 'round-rectangle', 'color': '#1c1917' } },
  // Decision — emerald barrel
  { selector: 'node[nodeLabel="Decision"]', style: { 'background-color': '#34d399', 'shape': 'barrel', 'color': '#052e16' } },
  // Action — orange tag
  { selector: 'node[nodeLabel="Action"]', style: { 'background-color': '#fb923c', 'shape': 'tag', 'color': '#fff' } },
  // Merchant — yellow pentagon
  { selector: 'node[nodeLabel="Merchant"]', style: { 'background-color': '#fcd34d', 'shape': 'pentagon', 'color': '#1c1917' } },

  // Edges
  {
    selector: 'edge',
    style: {
      'width': 2,
      'line-color': '#475569',
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'label': 'data(shortLabel)',
      'font-size': '10px',
      'color': '#94a3b8',
      'text-outline-width': 2,
      'text-outline-color': '#0f172a',
      'text-rotation': 'autorotate',
    }
  },

  // Highlighted (agent traversal path)
  { selector: 'node.highlighted', style: { 'border-color': '#fbbf24', 'border-width': 5, 'border-opacity': 1 } },
  { selector: 'edge.highlighted-edge', style: { 'line-color': '#fbbf24', 'width': 4, 'target-arrow-color': '#fbbf24' } },

  // Selected
  { selector: 'node:selected', style: { 'border-color': '#38bdf8', 'border-width': 4 } },
]

const LEGEND = [
  { color: '#4ade80', shape: '●', label: 'Customer' },
  { color: '#3b82f6', shape: '■', label: 'Account' },
  { color: '#a78bfa', shape: '▲', label: 'Transaction' },
  { color: '#06b6d4', shape: '◆', label: 'Device' },
  { color: '#84cc16', shape: '⬡', label: 'Address' },
  { color: '#e879f9', shape: '★', label: 'IP' },
  { color: '#ef4444', shape: '⬟', label: 'Alert' },
  { color: '#fbbf24', shape: '▣', label: 'Case' },
  { color: '#34d399', shape: '⬭', label: 'Decision' },
  { color: '#fb923c', shape: '⬦', label: 'Action' },
]

export default function GraphPanel({ elements, onNodeSelect, onInvestigate, onNodeInvestigate }) {
  const cyRef = useRef(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [overview, setOverview] = useState(null)
  const layoutRunning = useRef(false)

  useEffect(() => {
    getOverview().then(r => setOverview(r.data)).catch(() => {})
  }, [])

  // Run layout whenever elements change, debounced so rapid additions batch together
  useEffect(() => {
    if (!cyRef.current || elements.length === 0) return
    if (layoutRunning.current) return
    layoutRunning.current = true

    const timer = setTimeout(() => {
      const cy = cyRef.current
      if (!cy) { layoutRunning.current = false; return }
      cy.layout({
        name: 'cose',
        animate: true,
        animationDuration: 600,
        nodeRepulsion: 8000,
        idealEdgeLength: 120,
        nodeOverlap: 20,
        randomize: false,
        fit: true,
        padding: 40,
      }).run()
      layoutRunning.current = false
    }, 300)

    return () => { clearTimeout(timer); layoutRunning.current = false }
  }, [elements])

  const handleNodeClick = useCallback((evt) => {
    const data = evt.target.data()
    setSelectedNode(data)
    if (onNodeSelect) onNodeSelect(data)
  }, [onNodeSelect])

  const handleBgClick = useCallback((evt) => {
    if (evt.target === evt.cy) setSelectedNode(null)
  }, [])

  const nodeCount = elements.filter(e => !e.data?.source).length
  const edgeCount = elements.filter(e => e.data?.source).length

  return (
    <div className="graph-panel" style={{ position: 'relative', display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* Overview bar */}
      {overview && (
        <div className="overview-bar">
          <div className="overview-stat">
            <span className="num">{overview.node_counts?.Account || 0}</span>
            <span className="lbl">Accounts</span>
          </div>
          <div className="overview-stat">
            <span className="num">{overview.node_counts?.Transaction || 0}</span>
            <span className="lbl">Transactions</span>
          </div>
          <div className="overview-stat" style={{ color: '#ef4444' }}>
            <span className="num" style={{ color: '#ef4444' }}>{overview.flagged_accounts || 0}</span>
            <span className="lbl">Flagged</span>
          </div>
          <div className="overview-stat">
            <span className="num">{overview.node_counts?.Alert || 0}</span>
            <span className="lbl">Alerts</span>
          </div>
          {elements.length > 0 && (
            <div className="overview-stat" style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#64748b' }}>
              {nodeCount} nodes · {edgeCount} edges
            </div>
          )}
        </div>
      )}

      {/* Graph canvas */}
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        {elements.length === 0 ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', color: '#64748b', flexDirection: 'column', gap: 12
          }}>
            <div style={{ fontSize: '3rem' }}>🕸️</div>
            <div style={{ fontSize: '0.95rem' }}>Run an investigation to see the graph</div>
            <div style={{ fontSize: '0.8rem', color: '#475569', maxWidth: 260, textAlign: 'center' }}>
              Try "Fraud Ring" or "Mule Chain" from the scenario buttons below
            </div>
          </div>
        ) : (
          <CytoscapeComponent
            elements={elements}
            stylesheet={STYLESHEET}
            layout={{ name: 'preset' }}
            style={{ width: '100%', height: '100%' }}
            cy={(cy) => {
              cyRef.current = cy
              cy.removeAllListeners()
              cy.on('tap', 'node', handleNodeClick)
              cy.on('tap', handleBgClick)
            }}
          />
        )}

        {/* Node detail panel */}
        {selectedNode && (
          <NodeDetail
            node={selectedNode}
            onClose={() => setSelectedNode(null)}
            onInvestigate={(id) => {
              setSelectedNode(null)
              if (onInvestigate) onInvestigate(`Investigate ${id}`)
            }}
          />
        )}
      </div>

      {/* Legend */}
      <div className="graph-legend" style={{
        display: 'flex', flexWrap: 'wrap', gap: '6px 14px',
        padding: '8px 12px', borderTop: '1px solid #1e293b',
        background: '#0f172a'
      }}>
        {LEGEND.map(({ color, shape, label }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.75rem' }}>
            <span style={{ color, fontSize: '1rem', lineHeight: 1 }}>{shape}</span>
            <span style={{ color: '#94a3b8' }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
