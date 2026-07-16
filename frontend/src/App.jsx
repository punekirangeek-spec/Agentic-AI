import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  const sendMessage = async () => {
    if (!input.trim()) return

    const userMessage = { role: 'user', text: input }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch('http://127.0.0.1:5000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage.text }),
      })

      const data = await response.json()

      const assistantMessage = {
        role: 'assistant',
        text: data.reply || data.error || 'No response received.',
        downloadUrl: data.download_url || null,
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: 'Error: could not reach the server.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const startNewChat = () => {
    setMessages([])
    setInput('')
  }

  const hasMessages = messages.length > 0

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-title">Lex</div>
        <button className="new-chat-btn" onClick={startNewChat}>
          + New chat
        </button>
      </aside>

      <div className="app">
        {!hasMessages && (
          <div className="centered-view">
            <h1>What's on the agenda today?</h1>
            <div className="input-bar">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything"
                rows={1}
                autoFocus
              />
              <button className="send-btn" onClick={sendMessage} disabled={loading || !input.trim()}>
                ↑
              </button>
            </div>
          </div>
        )}

        {hasMessages && (
          <>
            <div className="chat-area">
              <div className="messages">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`message-row ${msg.role}`}>
                    {msg.role === 'assistant' && (
                      <div className="sender-label">Lex</div>
                    )}
                    <div className="message-bubble">
                      {msg.role === 'assistant' ? (
                        <ReactMarkdown>{msg.text}</ReactMarkdown>
                      ) : (
                        msg.text
                      )}
                     {msg.downloadUrl && (
                        <a href={msg.downloadUrl} className="download-link" download>
                            <div className="file-info">
                              <span className="file-name">
                                  {decodeURIComponent(msg.downloadUrl.split('/').pop())}
                              </span>
                            <span className="file-action">Click to download</span>
                           </div>
                        </a>
                     )}
                    </div>
                  </div>
                ))}

                {loading && (
                  <div className="message-row assistant">
                    <div className="sender-label">Lex</div>
                    <div className="message-bubble typing">
                      <span className="dot"></span>
                      <span className="dot"></span>
                      <span className="dot"></span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="input-bar-wrapper">
              <div className="input-bar">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything"
                  rows={1}
                />
                <button className="send-btn" onClick={sendMessage} disabled={loading || !input.trim()}>
                  ↑
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default App