import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

function App() {
  const [token, setToken] = useState(null)
  const [userInfo, setUserInfo] = useState(null)
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loggingIn, setLoggingIn] = useState(false)

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

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoginError('')
    setLoggingIn(true)

    try {
      const response = await fetch('http://127.0.0.1:5000/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword }),
      })

      const data = await response.json()

      if (!response.ok) {
        setLoginError(data.error || 'Login failed')
        return
      }

      setToken(data.token)
      setUserInfo({
        employeeId: data.employee_id,
        fullName: data.full_name,
        role: data.role,
      })
    } catch (err) {
      setLoginError('Could not reach the server')
    } finally {
      setLoggingIn(false)
    }
  }

  const handleLogout = () => {
    setToken(null)
    setUserInfo(null)
    setMessages([])
    setLoginEmail('')
    setLoginPassword('')
  }

  const sendMessage = async () => {
    if (!input.trim()) return

    const userMessage = { role: 'user', text: input }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch('http://127.0.0.1:5000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message: userMessage.text }),
      })

      const data = await response.json()

      if (response.status === 401) {
        // token expired or invalid — force re-login
        handleLogout()
        return
      }

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

  // --- Login screen ---
  if (!token) {
    return (
      <div className="login-screen">
        <div className="login-card">
          <h1>Lex</h1>
          <p className="login-subtitle">Sign in to your HR Assistant</p>

          <form onSubmit={handleLogin}>
            <input
              type="email"
              placeholder="Email"
              value={loginEmail}
              onChange={(e) => setLoginEmail(e.target.value)}
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              required
            />
            {loginError && <div className="login-error">{loginError}</div>}
            <button type="submit" disabled={loggingIn}>
              {loggingIn ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  const hasMessages = messages.length > 0

  // --- Main app (after login) ---
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-title">Lex</div>
        <button className="new-chat-btn" onClick={startNewChat}>
          + New chat
        </button>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-name">{userInfo.fullName}</div>
            <div className="user-role">{userInfo.role === 'hr' ? 'HR Staff' : 'Employee'}</div>
          </div>
          <button className="logout-btn" onClick={handleLogout}>
            Log out
          </button>
        </div>
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