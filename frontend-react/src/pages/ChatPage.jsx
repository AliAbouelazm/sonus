import { useState, useEffect, useRef, useCallback } from 'react'
import { useWS } from '../contexts/WebSocketContext.jsx'
import { getById, CATEGORY_META, INTEGRATION_TO_DEVICE_PREFIX } from '../data/integrations.js'
import IntegrationIcon from '../components/IntegrationIcon.jsx'

// ── Markdown renderer ────────────────────────────────────────────
function renderMarkdown(text) {
  if (!text) return []
  const lines = text.split('\n')
  const elements = []
  let key = 0

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i]

    if (!raw.trim()) {
      elements.push(<div key={key++} style={{ height: '0.4em' }} />)
      continue
    }

    // H2 / H3 headings
    const h2 = raw.match(/^##\s+(.+)$/)
    if (h2) {
      elements.push(
        <div key={key++} style={{ fontWeight: 700, fontSize: '1.05em', marginTop: 8, marginBottom: 2, color: 'var(--text)' }}>
          {inlineMarkdown(h2[1])}
        </div>
      )
      continue
    }
    const h3 = raw.match(/^###\s+(.+)$/)
    if (h3) {
      elements.push(
        <div key={key++} style={{ fontWeight: 600, fontSize: '0.97em', marginTop: 6, marginBottom: 2, color: 'var(--text-muted)' }}>
          {inlineMarkdown(h3[1])}
        </div>
      )
      continue
    }

    // Bullet list
    const bullet = raw.match(/^(\s*[-*])\s+(.*)$/)
    if (bullet) {
      elements.push(
        <div key={key++} style={{ display: 'flex', gap: 8, marginBottom: 2 }}>
          <span style={{ color: 'var(--text-dim)', flexShrink: 0 }}>·</span>
          <span>{inlineMarkdown(bullet[2])}</span>
        </div>
      )
      continue
    }

    // Numbered list
    const numbered = raw.match(/^(\d+)\.\s+(.*)$/)
    if (numbered) {
      elements.push(
        <div key={key++} style={{ display: 'flex', gap: 8, marginBottom: 2 }}>
          <span style={{ color: 'var(--text-dim)', flexShrink: 0, minWidth: 16 }}>{numbered[1]}.</span>
          <span>{inlineMarkdown(numbered[2])}</span>
        </div>
      )
      continue
    }

    elements.push(<div key={key++} style={{ marginBottom: 2 }}>{inlineMarkdown(raw)}</div>)
  }

  return elements
}

function inlineMarkdown(text) {
  // Split on **bold**, *italic*, `code`, [link](url)
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**'))
      return <strong key={i}>{part.slice(2, -2)}</strong>
    if (part.startsWith('*') && part.endsWith('*'))
      return <em key={i}>{part.slice(1, -1)}</em>
    if (part.startsWith('`') && part.endsWith('`'))
      return (
        <code key={i} style={{
          fontFamily: 'monospace',
          background: 'rgba(255,255,255,0.08)',
          borderRadius: 3,
          padding: '1px 5px',
          fontSize: '0.9em',
        }}>
          {part.slice(1, -1)}
        </code>
      )
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    if (link)
      return (
        <a key={i} href={link[2]} target="_blank" rel="noopener noreferrer" style={{
          color: 'var(--purple)',
          textDecoration: 'underline',
          textUnderlineOffset: 2,
        }}>
          {link[1]}
        </a>
      )
    return part
  })
}

// ── Helpers ──────────────────────────────────────────────────────
function formatToolCall(msg) {
  const name = msg.tool || msg.tool_name
  if (!name) return ''
  const params = msg.params || msg.args
  const paramStr = params ? JSON.stringify(params) : ''
  return `${name}(${paramStr})`
}

const COLOR_TEMP_COLORS = { warm: '#ffb347', neutral: '#fff4e0', cool: '#87ceeb' }

// Integration sidebar card
function IntegrationCard({ config, devices }) {
  const integration = getById(config.integration_id)
  if (!integration) return null

  const meta = CATEGORY_META[integration.category]
  const label = config.display_name || integration.name
  const isHardware = integration.category === 'hardware'

  const prefix = INTEGRATION_TO_DEVICE_PREFIX[config.integration_id]
  const deviceId = prefix ? `${prefix}.${config.instance_id}` : null
  const matchedDevice = deviceId ? devices[deviceId] : null

  return (
    <div className="ic-card" style={{ '--cat-color': meta.color }}>
      <div className="ic-card-header">
        <div className="ic-icon-wrap">
          <IntegrationIcon integration={integration} size={18} />
        </div>
        <span className="ic-name" title={label}>{label}</span>
        <span className="ic-dot" />
      </div>

      {isHardware && matchedDevice && (
        <HardwareState device={matchedDevice} />
      )}

      {!isHardware && (
        <div className="ic-status-row">
          <span className="ic-category-badge" style={{ color: meta.color }}>
            {meta.label.toLowerCase()}
          </span>
        </div>
      )}
    </div>
  )
}

function HardwareState({ device }) {
  const { device_type, state } = device
  if (!state) return null

  const getLabel = () => {
    if (device_type === 'lock') return state.locked ? 'Locked' : 'Unlocked'
    if (state.on === false) return 'Off'
    if (state.on === true) {
      const parts = []
      if (state.brightness !== undefined) parts.push(`${state.brightness}%`)
      if (state.speed) parts.push(state.speed)
      if (state.target_temp) parts.push(`${state.target_temp}°F`)
      if (state.mode) parts.push(state.mode)
      return parts.length ? parts.join(' · ') : 'On'
    }
    return '—'
  }

  // For locks: locked = secure = green. For other devices: on = green.
  const isOn = device_type === 'lock'
    ? (state.locked ?? false)
    : (state.on ?? false)

  const lampColor = device_type === 'bulb' && state.on
    ? (state.color || COLOR_TEMP_COLORS[state.color_temp] || '#ffffff')
    : null

  return (
    <div className="ic-hw-state">
      {lampColor && (
        <span style={{
          display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
          background: lampColor, boxShadow: `0 0 5px ${lampColor}`, flexShrink: 0,
        }} />
      )}
      <span className={`ic-hw-badge ${isOn ? 'hw-on' : 'hw-off'}`}>{getLabel()}</span>
    </div>
  )
}

// ── Avatars ──────────────────────────────────────────────────────
function UserAvatar() {
  return (
    <div className="message-avatar user-avatar">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <circle cx="12" cy="8" r="4"/>
        <path d="M4 20c0-4.4 3.6-8 8-8s8 3.6 8 8"/>
      </svg>
    </div>
  )
}

function AssistantAvatar() {
  return (
    <div className="message-avatar assistant-avatar">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c4b5fd" strokeWidth="2">
        <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>
      </svg>
    </div>
  )
}

function ToolAvatar() {
  return (
    <div className="message-avatar tool-avatar">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.07 4.93l-1.42 1.42M4.93 4.93l1.42 1.42M20 12h-2M6 12H4M16.95 16.95l-1.42-1.42M7.05 16.95l1.42-1.42M12 18v2M12 4V2"/>
      </svg>
    </div>
  )
}

// ── Message Component ────────────────────────────────────────────
function Message({ msg }) {
  if (msg.type === 'user') {
    return (
      <div className="message user">
        <UserAvatar />
        <div className="message-bubble">{msg.content}</div>
      </div>
    )
  }
  if (msg.type === 'assistant') {
    return (
      <div className="message assistant">
        <AssistantAvatar />
        <div className="message-bubble">{renderMarkdown(msg.content)}</div>
      </div>
    )
  }
  if (msg.type === 'tool') {
    return (
      <div className="message tool">
        <ToolAvatar />
        <div className="message-bubble">{msg.content}</div>
      </div>
    )
  }
  if (msg.type === 'system') {
    return (
      <div className="system-message">
        {msg.content}
      </div>
    )
  }
  if (msg.type === 'thinking') {
    return (
      <div className="message assistant">
        <AssistantAvatar />
        <div className="thinking">
          <span /><span /><span />
        </div>
      </div>
    )
  }
  return null
}

// ── Main ChatPage ────────────────────────────────────────────────
export default function ChatPage({ mode = 'demo' }) {
  const { status, lastMessage, send } = useWS()
  const [messages, setMessages]                   = useState([])
  const [inputText, setInputText]                 = useState('')
  const [isThinking, setIsThinking]               = useState(false)
  const [devices, setDevices]                     = useState({})
  const [connectedIntegrations, setConnectedIntegrations] = useState([])
  const [tokenStats, setTokenStats]               = useState(null)
  const [reminders, setReminders]                 = useState([])
  const [isRecording, setIsRecording]             = useState(false)
  const messagesEndRef = useRef(null)
  const textareaRef    = useRef(null)
  const recognitionRef = useRef(null)

  const fetchIntegrations = useCallback(async () => {
    try {
      const res = await fetch('/api/integrations')
      if (!res.ok) return
      const data = await res.json()
      setConnectedIntegrations(data.integrations || [])
    } catch (_) {}
  }, [])

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return
    const msg = lastMessage

    if (msg.type === 'pong') return

    if (msg.type === 'device_update') {
      setDevices((prev) => ({
        ...prev,
        [msg.device_id]: { device_id: msg.device_id, device_type: msg.device_type, state: msg.state },
      }))
      return
    }

    if (msg.type === 'chat_start') { setIsThinking(true); return }

    if (msg.type === 'tool_call') {
      const text = formatToolCall(msg)
      if (text) setMessages((prev) => [...prev, { type: 'tool', content: text, id: Date.now() + Math.random() }])
      return
    }

    if (msg.type === 'chat_complete') {
      setIsThinking(false)
      const reply = msg.content || msg.response
      if (reply) setMessages((prev) => [...prev, { type: 'assistant', content: reply, id: Date.now() + Math.random() }])
      return
    }

    if (msg.type === 'integration_update') {
      fetchIntegrations()
      const verb = msg.action === 'connected' ? 'Connected' : 'Disconnected'
      const name = msg.display_name || msg.integration_id
      setMessages((prev) => [...prev, {
        type: 'system',
        content: `${verb}: ${name}`,
        id: Date.now() + Math.random(),
      }])
      return
    }

    if (msg.type === 'reset') {
      setMessages([])
      setConnectedIntegrations([])
      return
    }

    if (msg.type === 'reminder') {
      setReminders((prev) => [...prev, { id: Date.now(), title: msg.title, body: msg.description }])
      return
    }

    if (msg.type === 'error') {
      setIsThinking(false)
      setMessages((prev) => [...prev, {
        type: 'assistant',
        content: `Something went wrong: ${msg.message}`,
        id: Date.now() + Math.random(),
      }])
    }
  }, [lastMessage, fetchIntegrations])

  // Initial data load
  useEffect(() => {
    fetchIntegrations()

    fetch('/api/devices')
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data && typeof data === 'object') setDevices(data) })
      .catch(() => {})

    fetch('/api/token-usage')
      .then((r) => r.ok ? r.json() : null)
      .then((data) => data && setTokenStats(data))
      .catch(() => {})
  }, [fetchIntegrations])

  // Scroll to bottom on new messages / thinking state
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
    }
  }, [inputText])

  const sendMessage = useCallback(() => {
    const text = inputText.trim()
    if (!text || status !== 'connected') return
    setMessages((prev) => [...prev, { type: 'user', content: text, id: Date.now() }])
    setInputText('')
    setIsThinking(true)
    send({ type: 'chat', content: text })
    // Keep focus in textarea after send
    setTimeout(() => textareaRef.current?.focus(), 0)
  }, [inputText, status, send])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  const toggleVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      alert('Voice input is not supported in this browser.')
      return
    }

    if (isRecording) {
      recognitionRef.current?.stop()
      setIsRecording(false)
      return
    }

    const r = new SR()
    r.lang = 'en-US'
    r.interimResults = false
    r.continuous = false
    recognitionRef.current = r
    r.onresult = (e) => {
      setInputText(e.results[0][0].transcript)
      setIsRecording(false)
      setTimeout(() => textareaRef.current?.focus(), 0)
    }
    r.onend = () => setIsRecording(false)
    r.onerror = (e) => {
      setIsRecording(false)
      if (e.error === 'not-allowed') {
        alert('Microphone access denied. Please allow mic access in your browser settings.')
      }
    }
    r.start()
    setIsRecording(true)
  }

  const dismissReminder = (id) => setReminders((prev) => prev.filter((r) => r.id !== id))

  const handleReset = async () => {
    if (!confirm(
      'This will permanently erase all of Sonus\'s memory, integrations, and conversation history.\n\nAre you sure you want to reset everything?'
    )) return
    try {
      await fetch('/api/admin/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: true }),
      })
    } catch (_) {}
    setMessages([])
    setConnectedIntegrations([])
  }

  // Token bar — only show percentage if a budget is configured
  const hasBudget = tokenStats?.budget && tokenStats.budget > 0
  const tokenPct = hasBudget
    ? Math.min(100, Math.round((tokenStats.total_tokens / tokenStats.budget) * 100))
    : null

  return (
    <div className="chat-page">
      {/* Integrations sidebar */}
      <aside className="device-sidebar">
        <div className="device-sidebar-header">
          Integrations
          <span className={`mode-badge ${mode}`}>
            {mode === 'active' ? 'ACTIVE' : 'DEMO'}
          </span>
        </div>
        <div className="device-cards">
          {connectedIntegrations.length === 0 ? (
            <div className="sidebar-empty">
              No integrations connected.<br/>
              <span>Go to the Integrations tab to connect.</span>
            </div>
          ) : (() => {
            const grouped = {}
            for (const cfg of connectedIntegrations) {
              const integration = getById(cfg.integration_id)
              if (!integration) continue
              const cat = integration.category
              if (!grouped[cat]) grouped[cat] = []
              grouped[cat].push(cfg)
            }
            const categoryOrder = ['software', 'hardware', 'wearables', 'communication']
            return categoryOrder.map((cat) => {
              const items = grouped[cat]
              if (!items?.length) return null
              const meta = CATEGORY_META[cat]
              return (
                <div key={cat} className="sidebar-group">
                  <div className="sidebar-group-header" style={{ color: meta.color }}>
                    <span className="sidebar-group-dot" style={{ background: meta.color }} />
                    {meta.label}
                  </div>
                  {items.map((cfg) => (
                    <IntegrationCard key={cfg.instance_id} config={cfg} devices={devices} />
                  ))}
                </div>
              )
            })
          })()}
        </div>
      </aside>

      {/* Chat main */}
      <div className="chat-main">
        <div className="chat-messages">
          {messages.length === 0 && !isThinking && (
            <div className="chat-welcome">
              <div className="welcome-mark">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.6" strokeLinecap="round">
                  <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>
                </svg>
              </div>
              <div className="chat-welcome-title">Sonus</div>
              <div className="chat-welcome-sub">
                {status === 'connected'
                  ? 'Smart home, simplified.'
                  : status === 'connecting'
                    ? 'Connecting...'
                    : 'Reconnecting...'}
              </div>
              {status === 'connected' && (
                <div className="welcome-suggestions">
                  {[
                    "What's on my calendar today?",
                    "Turn on the living room lights",
                    "Play some focus music",
                    "What's the weather like?",
                  ].map((s) => (
                    <button
                      key={s}
                      className="welcome-suggestion"
                      onClick={() => { setInputText(s); setTimeout(() => textareaRef.current?.focus(), 0) }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {messages.map((msg) => <Message key={msg.id} msg={msg} />)}
          {isThinking && <Message msg={{ type: 'thinking' }} />}
          <div ref={messagesEndRef} />
        </div>

        {/* Offline banner */}
        {status !== 'connected' && (
          <div className="offline-banner">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><circle cx="12" cy="16" r="0.5" fill="currentColor"/>
            </svg>
            {status === 'connecting' ? 'Connecting to Sonus…' : 'Reconnecting…'}
          </div>
        )}

        {/* Input area */}
        <div className="chat-input-area">
          <div className={`chat-input-row ${status !== 'connected' ? 'input-offline' : ''}`}>
            <textarea
              ref={textareaRef}
              className="chat-textarea"
              placeholder={status === 'connected' ? 'Message Sonus…' : 'Waiting for connection…'}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={status !== 'connected'}
            />
            <div className="chat-actions">
              <button
                className={`icon-btn ${isRecording ? 'recording' : ''}`}
                onClick={toggleVoice}
                title={isRecording ? 'Stop recording' : 'Voice input'}
                aria-label={isRecording ? 'Stop recording' : 'Voice input'}
                disabled={status !== 'connected'}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  <line x1="12" y1="19" x2="12" y2="22"/>
                  <line x1="8" y1="22" x2="16" y2="22"/>
                </svg>
              </button>
              <button
                className="send-btn"
                onClick={sendMessage}
                disabled={!inputText.trim() || status !== 'connected'}
                title="Send message"
                aria-label="Send"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="19" x2="12" y2="5"/>
                  <polyline points="5 12 12 5 19 12"/>
                </svg>
              </button>
            </div>
          </div>

          {/* Bottom bar: reset + token usage */}
          <div className="chat-bottom-bar">
            <button className="reset-btn" onClick={handleReset} title="Reset Sonus memory and conversation">
              Reset
            </button>
            {tokenStats && (
              <>
                {tokenPct !== null && (
                  <div className="token-bar-track" style={{ flex: 1 }}>
                    <div className="token-bar-fill" style={{
                      width: `${tokenPct}%`,
                      background: tokenPct > 90 ? '#ef4444' : tokenPct > 70 ? '#FBBF24' : 'var(--purple)',
                    }} />
                  </div>
                )}
                <span className="token-bar-text">
                  {tokenStats.total_tokens?.toLocaleString()} tokens · ${tokenStats.cost?.toFixed(3) ?? '0.000'}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Reminder toasts */}
      {reminders.map((r) => (
        <div key={r.id} className="reminder-toast">
          <button className="reminder-dismiss" onClick={() => dismissReminder(r.id)}>×</button>
          <div className="reminder-toast-title">Reminder: {r.title}</div>
          {r.body && <div className="reminder-toast-body">{r.body}</div>}
        </div>
      ))}
    </div>
  )
}
