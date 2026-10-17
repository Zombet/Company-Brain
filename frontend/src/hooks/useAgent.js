import { useState, useRef, useCallback } from 'react'

export function useAgent() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const wsRef = useRef(null)

  const sendQuery = useCallback((query, onGraphUpdate) => {
    setIsLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: query, id: Date.now() }])

    const ws = new WebSocket('ws://localhost:8000/ws/investigate')
    wsRef.current = ws

    // Accumulate streaming steps so we can pass them to onGraphUpdate
    const streamedSteps = []

    ws.onopen = () => ws.send(JSON.stringify({ query }))

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        if (msg.type === 'step') {
          // Each step arrives as {tool, tool_input, observation}
          streamedSteps.push(msg.data)

          // Stream partial graph update as each tool result arrives
          if (onGraphUpdate) {
            onGraphUpdate({ steps: [msg.data], partial: true })
          }

        } else if (msg.type === 'done') {
          setIsLoading(false)
          const result = msg.data
          // Prefer the streamed steps (they have real observations);
          // fall back to whatever the backend packaged in result.steps
          const finalSteps = streamedSteps.length > 0 ? streamedSteps : (result.steps || [])

          setMessages(prev => [...prev, {
            role: 'agent',
            content: result.answer,
            steps: finalSteps,
            session_id: result.session_id,
            id: Date.now(),
          }])

          if (onGraphUpdate) {
            onGraphUpdate({ ...result, steps: finalSteps, partial: false })
          }

        } else if (msg.type === 'error') {
          setIsLoading(false)
          setMessages(prev => [...prev, {
            role: 'agent',
            content: `Error: ${msg.data?.message || 'Unknown error'}`,
            id: Date.now(),
          }])
        }
      } catch (e) {
        console.error('WS parse error', e)
      }
    }

    ws.onerror = () => {
      setIsLoading(false)
      setMessages(prev => [...prev, {
        role: 'agent',
        content: 'Connection error. Make sure the backend is running on port 8000.',
        id: Date.now(),
      }])
    }

    ws.onclose = () => setIsLoading(false)
  }, [])

  return { sendQuery, messages, isLoading }
}
