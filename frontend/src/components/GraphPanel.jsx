import React, { useEffect, useRef, useState } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import NodeDetail from './NodeDetail'
import { getOverview } from '../api/client'

const EDGE_LABEL_MAP = {
  SENT: 'SND',
  TO: '→',
  OWNS: 'OWN',
  USED_DEVICE: 'USED',
  LOGGED_IN_FROM: 'IP',
  LIVES_AT: 'AT',
  HAS_PHONE: 'PH',
  HAS_EMAIL: '@',
  TRIGGERED_BY: 'TRIG',
  CONTAINS: 'HAS',
  HAS_EVIDENCE: 'EV',
  ABOUT: 'RE',
  EVIDENCED_BY: 'EV',
  LED_TO: '→',
  TARGETS: '→',
}

const STYLESHEET = [
  {
    selector: 'node',
    style: {
      'background-color': '#64748b',
      'label': 'data(id_short)',
      'color': '#f1f5f9',
      'font-size': '9px',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'width': 36,
      'height': 36,
      'border-width': 2,
      'border-color': '#475569',
      'shape': 'ellipse',
    }
  },
  { selector: 'node[nodeLabel="Customer"]', style: { 'background-color': '#4ade80', 'shape': 'ellipse' } },
  { selector: 'node[nodeLabel="Account"]', style: { 'background-color': '#3b82f6', 'shape': 'rectangle' } },
  { selector: 'node[nodeLabel="Account"][status="frozen"]', style: { 'background-color': '#ef4444' } },
  { selector: 'node[nodeLabel="Transaction"]', style: { 'background-color': '#a78bfa', 'shape': 'triangle', 'width': 32, 'height': 32 } },
  { selector: 'node[nodeLabel="Transaction"][status="flagged"]', style: { 'background-color': '#f59e0b' } },
  { selector: 'node[nodeLabel="Device"]', style: { 'background-color': '#06b6d4', 'shape': 'diamond' } },
  { selector: 'node[nodeLabel="Address"]', style: { 'background-color': '#84cc16', 'shape': 'hexagon' } },
  { selector: 'node[nodeLabel="IP"]', style: { 'background-color': '#e879f9', 'shape': 'star' } },
  { selector: 'node[nodeLabel="Alert"]', style: { 'background-color': '#ef4444', 'shape': 'octagon', 'width': 44, 'height': 44 } },
  { selector: 'node[nodeLabel="Case"]', style: { 'background-color': '#fbbf24', 'shape': 'round-rectangle' } },
  { selector: 'node[nodeLabel="Decision"]', style: { 'background-color': '#34d399', 'shape': 'barrel' } },
  { selector: 'node[nodeLabel="Action"]', style: { 'background-color': '#fb923c', 'shape': 'tag' } },
  { selector: 'node[nodeLabel="Evidence"]', style: { 'background-color': '#a78bfa', 'shape': 'vee' } },
  {
    selector: 'edge',
    style: {
      'width': 1.5,
      'line-color': '#475569',
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'label': 'data(shortLabel)',
      'font-size': '8px',
      'color': '#94a3b8',
    }
  },
  { selector: 'node.highlighted', style: { 'border-color': '#fbbf24', 'border-width': 4 } },
  { selector: 'edge.highlighted-edge', style: { 'line-color': '#fbbf24', 'width': 3, 'target-arrow-color': '#fbbf24' } },
  { selector: 'edge.traversal-path', style: { 'line-color': '#f59e0b', 'width': 4, 'target-arrow-color': '#f59e0b' } },
]

const LEGEND_ITEMS = [
  { color: '#4ade80', label: 'Customer' },
  { color: '#3b82f6', label: 'Account' },
  { color: '#a78bfa', label: 'Transaction' },
  { color: '#06b6d4', label: 'Device' },
  { color: '#84cc16', label: 'Address' },
  { color: '#e879f9', label: 'IP' },
  { color: '#ef4444', label: 'Alert' },
  { color: '#fbbf24', label: 'Case' },
  { color: '#34d399', label: 'Decision' },
  { color: '#fb923c', label: 'Action' },
  { color: '#a78bfa', label: 'Evidence' },
]

export default function GraphPanel({ elements, onNodeSelect, onInvestigate }) {
  const cyRef = useRef(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [overview, setOverview] = useState(null)

  useEffect(() => {
    getOverview().then(r => setOverview(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (cyRef.current && elements.length > 0) {
      const cy = cyRef.current
      cy.layout({ name: 'cose', animate: true, randomize: false }).run()
    }
  }, [elements])

  const handleNodeClick = (evt) => {
    const node = evt.target
    const data = node.data()
    setSelectedNode(data)
    if (onNodeSelect) onNodeSelect(data)
  }

  return (
    <div className="graph-panel">
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
          <div className="overview-stat">
            <span className="num">{overview.flagged_accounts || 0}</span>
            <span className="lbl" style={{color: '#ef4444'}}>Flagged</span>
          </div>
          <div className="overview-stat">
            <span className="num">{overview.node_counts?.Alert || 0}</span>
            <span className="lbl">Alerts</span>
          </div>
        </div>
      )}

      {elements.length === 0 ? (
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', flexDirection: 'column', gap: 8}}>
          <div style={{fontSize: '3rem'}}>🕸️</div>
          <div>Run an investigation to see the graph</div>
        </div>
      ) : (
        <CytoscapeComponent
          elements={elements}
          stylesheet={STYLESHEET}
          layout={{name: 'cose'}}
          style={{width: '100%', height: '100%'}}
          cy={(cy) => {
            cyRef.current = cy
            cy.on('tap', 'node', handleNodeClick)
          }}
        />
      )}

      <div className="graph-legend">
        {LEGEND_ITEMS.map(({ color, label }) => (
          <div key={label} className="legend-item">
            <div className="legend-dot" style={{background: color}} />
            <span style={{color: '#94a3b8'}}>{label}</span>
          </div>
        ))}
      </div>

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
  )
}
