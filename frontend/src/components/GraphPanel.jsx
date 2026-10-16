import React, { useEffect, useRef, useState } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import NodeDetail from './NodeDetail'
import { getOverview } from '../api/client'

const STYLESHEET = [
  {
    selector: 'node',
    style: {
      'background-color': '#64748b',
      'label': 'data(label)',
      'color': '#f1f5f9',
      'font-size': '9px',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'width': 36,
      'height': 36,
      'border-width': 2,
      'border-color': '#475569',
    }
  },
  { selector: 'node[type="Account"][status="active"]',        style: { 'background-color': '#22c55e' } },
  { selector: 'node[type="Account"][status="flagged"]',       style: { 'background-color': '#ef4444' } },
  { selector: 'node[type="Account"][status="frozen"]',        style: { 'background-color': '#f97316' } },
  { selector: 'node[type="Transaction"][status="flagged"]',   style: { 'background-color': '#f97316' } },
  { selector: 'node[type="Transaction"][status="confirmed_fraud"]', style: { 'background-color': '#dc2626' } },
  { selector: 'node[type="Transaction"]',                     style: { 'background-color': '#3b82f6', 'shape': 'diamond', 'width': 28, 'height': 28 } },
  { selector: 'node[type="Customer"]',                        style: { 'background-color': '#8b5cf6', 'shape': 'ellipse' } },
  { selector: 'node[type="Device"]',                          style: { 'background-color': '#a855f7', 'shape': 'rectangle' } },
  { selector: 'node[type="Merchant"]',                        style: { 'background-color': '#eab308', 'shape': 'hexagon' } },
  {
    selector: 'edge',
    style: {
      'width': 1.5,
      'line-color': '#475569',
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'label': 'data(label)',
      'font-size': '8px',
      'color': '#94a3b8',
    }
  },
  { selector: 'edge.traversal-path',  style: { 'line-color': '#f59e0b', 'width': 4, 'target-arrow-color': '#f59e0b' } },
  { selector: 'node.highlighted',     style: { 'border-color': '#fbbf24', 'border-width': 4 } },
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
            <span className="num">{overview.node_counts?.AgentSession || 0}</span>
            <span className="lbl">Sessions</span>
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
        {[
          { color: '#22c55e', label: 'Account (active)' },
          { color: '#ef4444', label: 'Account (flagged)' },
          { color: '#3b82f6', label: 'Transaction' },
          { color: '#f97316', label: 'Transaction (flagged)' },
          { color: '#8b5cf6', label: 'Customer' },
          { color: '#a855f7', label: 'Device' },
          { color: '#eab308', label: 'Merchant' },
        ].map(({ color, label }) => (
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
            if (onInvestigate) onInvestigate(`Investigate account ${id}`)
          }}
        />
      )}
    </div>
  )
}
