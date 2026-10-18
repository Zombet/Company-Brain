import { useState, useRef, useCallback } from 'react'

export function useAgent() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const wsRef = useRef(null)
  const doneRef = useRef(false)  // tracks whether we got a 'done' message

  const sendQuery = useCallback((query, onGraphUpdate) => {
    setIsLoading(true)
    doneRef.current = false
    setMessages(prev => [...prev, { role: 'user', content: query, id: Date.now() }])

    const ws = new WebSocket('ws://localhost:8000/ws/investigate')
    wsRef.current = ws
    const streamedSteps = []

    ws.onopen = () => ws.send(JSON.stringify({ query }))

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        if (msg.type === 'step') {
          streamedSteps.push(msg.data)
          if (onGraphUpdate) onGraphUpdate({ steps: [msg.data], partial: true })

        } else if (msg.type === 'done') {
          doneRef.current = true
          setIsLoading(false)
          const result = msg.data
          const finalSteps = streamedSteps.length > 0 ? streamedSteps : (result.steps || [])
          // Ensure content is always a string
          const content = typeof result.answer === 'string'
            ? result.answer
            : (result.answer ? JSON.stringify(result.answer) : 'Investigation complete.')

          setMessages(prev => [...prev, {
            role: 'agent',
            content,
            steps: finalSteps,
            session_id: result.session_id,
            id: Date.now(),
          }])
          if (onGraphUpdate) onGraphUpdate({ ...result, steps: finalSteps, partial: false })

        } else if (msg.type === 'error') {
          doneRef.current = true
          setIsLoading(false)
          setMessages(prev => [...prev, {
            role: 'agent',
            content: `Investigation error: ${msg.data?.message || 'Unknown error'}. Check that FalkorDB is running.`,
            steps: streamedSteps,
            id: Date.now(),
          }])
        }
      } catch (e) {
        console.error('WS parse error', e)
      }
    }

    ws.onerror = (err) => {
      console.error('WebSocket error', err)
      setIsLoading(false)
      if (!doneRef.current) {
        setMessages(prev => [...prev, {
          role: 'agent',
          content: 'Connection error. Make sure the backend is running on port 8000.',
          steps: streamedSteps,
          id: Date.now(),
        }])
      }
    }

    ws.onclose = () => {
      setIsLoading(false)
      // If closed before done, show what we have so far
      if (!doneRef.current && streamedSteps.length > 0) {
        setMessages(prev => {
          const last = prev[prev.length - 1]
          if (last?.role === 'user') {
            return [...prev, {
              role: 'agent',
              content: `Investigation was cut short (connection closed). ${streamedSteps.length} tool call(s) completed. Try again — the backend may still be warming up.`,
              steps: streamedSteps,
              id: Date.now(),
            }]
          }
          return prev
        })
      } else if (!doneRef.current) {
        setMessages(prev => {
          const last = prev[prev.length - 1]
          if (last?.role === 'user') {
            return [...prev, {
              role: 'agent',
              content: 'Connection closed before investigation completed. Please try again.',
              steps: [],
              id: Date.now(),
            }]
          }
          return prev
        })
      }
    }
  }, [])

  return { sendQuery, messages, isLoading }
}
