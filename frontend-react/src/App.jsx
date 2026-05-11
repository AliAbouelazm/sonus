import { useState, useEffect, useCallback } from 'react'
import { WebSocketProvider, useWS } from './contexts/WebSocketContext.jsx'
import IntegrationsPage from './pages/IntegrationsPage.jsx'
import ChatPage from './pages/ChatPage.jsx'

function ModeConfirmModal({ direction, onConfirm, onCancel }) {
  const toActive = direction === 'to_active'
  const accentColor = toActive ? 'var(--green)' : '#fbbf24'

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div
        className="modal"
        style={{ '--cat-color': accentColor, maxWidth: 440 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-title">
              {toActive ? 'Switch to Active Mode' : 'Switch to Demo Mode'}
            </div>
            <div className="modal-subtitle">
              {toActive ? 'Autonomous learning will activate' : 'Learning will be paused'}
            </div>
          </div>
          <button className="modal-close" onClick={onCancel}>✕</button>
        </div>

        <div className="modal-body">
          <p style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.65, margin: 0 }}>
            {toActive
              ? 'Sonus will start monitoring your biometrics, discovering usage patterns, and acting autonomously when confidence is high enough. All interactions will be logged for learning.'
              : 'All background loops will pause. You can still chat and control devices normally, but nothing will be logged and confidence scores will not change.'}
          </p>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onCancel} style={{ flex: 1 }}>Cancel</button>
          <button
            className="btn btn-primary"
            style={{
              flex: 1,
              background: accentColor,
              boxShadow: toActive ? '0 4px 16px rgba(16,185,129,0.3)' : '0 4px 16px rgba(251,191,36,0.2)',
            }}
            onClick={onConfirm}
          >
            {toActive ? 'Start Learning' : 'Pause Learning'}
          </button>
        </div>
      </div>
    </div>
  )
}

function AppContent() {
  const [page, setPage] = useState('integrations')
  const [mode, setMode] = useState('demo')
  const [pendingMode, setPendingMode] = useState(null)
  const { status } = useWS()

  useEffect(() => {
    fetch('/api/mode')
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data?.mode) setMode(data.mode) })
      .catch(() => {})
  }, [])

  const handleModeClick = useCallback(() => {
    setPendingMode(mode === 'active' ? 'demo' : 'active')
  }, [mode])

  const confirmModeSwitch = useCallback(async () => {
    const next = pendingMode
    setPendingMode(null)
    setMode(next)
    try {
      await fetch('/api/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: next }),
      })
    } catch (_) {}
  }, [pendingMode])

  const cancelModeSwitch = useCallback(() => {
    setPendingMode(null)
  }, [])

  const isDemo = mode === 'demo'

  const statusLabel = status === 'connected' ? 'Connected'
    : status === 'connecting' ? 'Connecting…'
    : 'Offline'

  return (
    <div className="app">
      <header className="header">
        <div className="header-logo">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-light)" strokeWidth="1.75" strokeLinecap="round">
            <circle cx="12" cy="12" r="10"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
          <span className="header-logo-text">Sonus</span>
        </div>

        <nav className="header-nav">
          <button
            className={`nav-btn ${page === 'integrations' ? 'active' : ''}`}
            onClick={() => setPage('integrations')}
          >
            Integrations
          </button>
          <button
            className={`nav-btn ${page === 'chat' ? 'active' : ''}`}
            onClick={() => setPage('chat')}
          >
            Chat
          </button>
        </nav>

        <div className="header-right">
          <button
            className={`mode-toggle ${mode}`}
            onClick={handleModeClick}
            title={isDemo
              ? 'Demo Mode: learning is paused. Click to start Active mode.'
              : 'Active Mode: Sonus is actively learning. Click to pause.'}
          >
            {isDemo ? 'DEMO' : 'ACTIVE'}
          </button>
          <div className="header-status">
            <div className={`status-dot ${status}`} />
            <span className="status-text">{statusLabel}</span>
          </div>
        </div>
      </header>

      {isDemo && (
        <div className="demo-banner">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><circle cx="12" cy="16" r="0.5" fill="currentColor"/>
          </svg>
          Demo Mode — Learning Disabled. Background loops are off. Switch to Active mode when ready for Sonus to start learning.
          <button className="demo-banner-btn" onClick={handleModeClick}>Switch to Active</button>
        </div>
      )}

      <main className="page">
        <div style={{ display: page === 'integrations' ? 'contents' : 'none' }}>
          <IntegrationsPage />
        </div>
        <div style={{ display: page === 'chat' ? 'contents' : 'none' }}>
          <ChatPage mode={mode} />
        </div>
      </main>

      {pendingMode && (
        <ModeConfirmModal
          direction={pendingMode === 'active' ? 'to_active' : 'to_demo'}
          onConfirm={confirmModeSwitch}
          onCancel={cancelModeSwitch}
        />
      )}
    </div>
  )
}

export default function App() {
  return (
    <WebSocketProvider>
      <AppContent />
    </WebSocketProvider>
  )
}
