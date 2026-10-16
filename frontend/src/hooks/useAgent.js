import { useState, useRef, useCallback } from 'react'

export function useAgent() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [graphData, setGraphData] = useState(null)
  const wsRef = useRef(null)

  const sendQuery = useCallback((query, onGraphUpdate) => {
    setIsLoading(true)
    const userMsg = { role: 'user', content: query, id: Date.now() }
    setMessages(prev => [...prev, userMsg])

    const ws = new WebSocket('ws://localhost:8000/ws/investigate')
    wsRef.current = ws

    const steps = []

    ws.onopen = () => {
      ws.send(JSON.stringify({ query }))
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'step') {
          steps.push(msg.data)
        } else if (msg.type === 'done') {
          setIsLoading(false)
          const result = msg.data
          const agentMsg = {
            role: 'agent',
            content: result.answer,
            steps: result.steps || steps,
            id: Date.now()
          }
          setMessages(prev => [...prev, agentMsg])
          setGraphData(result)
          if (onGraphUpdate) onGraphUpdate(result)
        } else if (msg.type === 'error') {
          setIsLoading(false)
          setMessages(prev => [...prev, {
            role: 'agent',
            content: `Error: ${msg.data?.message || 'Unknown error'}`,
            id: Date.now()
          }])
        }
      } catch (e) {
        console.error('WS parse error', e)
      }
    }

    ws.onerror = (err) => {
      console.error('WebSocket error', err)
      setIsLoading(false)
      setMessages(prev => [...prev, {
        role: 'agent',
        content: 'Connection error. Make sure the backend is running on port 8000.',
        id: Date.now()
      }])
    }

    ws.onclose = () => {
      setIsLoading(false)
    }
  }, [])

  return { sendQuery, messages, isLoading, graphData }
}
