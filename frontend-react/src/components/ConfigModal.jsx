import IntegrationIcon from './IntegrationIcon.jsx'
import { useState } from 'react'
import { CATEGORY_META } from '../data/integrations.js'

export default function ConfigModal({ integration, existingConfig, onSave, onDisconnect, onClose }) {
  const meta = CATEGORY_META[integration.category]
  const isOAuth = integration.auth_type === 'oauth'
  const isNone = integration.auth_type === 'none'

  const buildDefaults = () => {
    const vals = {}
    for (const field of integration.fields || []) {
      vals[field.name] = existingConfig?.config?.[field.name] ?? (field.default ?? '')
    }
    return vals
  }

  const [formValues, setFormValues] = useState(buildDefaults)
  const [saving, setSaving] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [error, setError] = useState(null)
  const [displayName, setDisplayName] = useState(
    existingConfig?.display_name || integration.name
  )

  const isEditing = !!existingConfig

  function shouldShow(field) {
    if (!field.show_if) return true
    const [key, val] = Object.entries(field.show_if)[0]
    return formValues[key] === val
  }

  function canConnect() {
    return (integration.fields || [])
      .filter(shouldShow)
      .filter((f) => f.required)
      .every((f) => formValues[f.name]?.toString().trim() !== '')
  }

  function handleField(name, value) {
    setFormValues((prev) => ({ ...prev, [name]: value }))
    if (error) setError(null)
  }

  function buildPayload() {
    const instanceId = integration.allow_multiple
      ? `${integration.id}_${Date.now()}`
      : integration.id
    return {
      integration_id: integration.id,
      instance_id: existingConfig?.instance_id || instanceId,
      display_name: displayName,
      config: formValues,
    }
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      await onSave(buildPayload())
      // Parent closes modal on success
    } catch (err) {
      setError(err.message || 'Connection failed. Please check your credentials and try again.')
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveAndOAuth() {
    // Open popup before any async work — browsers block popups after await
    const win = window.open('about:blank', '_blank', 'width=600,height=700')
    setSaving(true)
    setError(null)
    try {
      await onSave(buildPayload())
      if (win) win.location.href = integration.oauth_url
    } catch (err) {
      if (win) win.close()
      setError(err.message || 'Failed to save credentials. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function handleDisconnectClick() {
    setDisconnecting(true)
    try {
      await onDisconnect()
    } catch (err) {
      setError(err.message || 'Disconnect failed.')
      setDisconnecting(false)
    }
  }

  function handleReauthorize() {
    window.open(integration.oauth_url, '_blank', 'width=600,height=700')
  }

  const catStyle = { '--cat-color': meta.color }
  const connectDisabled = saving || !canConnect()

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={catStyle} onMouseDown={(e) => e.stopPropagation()}>

        <div className="modal-header">
          <div className="modal-emoji"><IntegrationIcon integration={integration} size={28} /></div>
          <div className="modal-title-group">
            <div className="modal-title">{integration.name}</div>
            <div className="modal-subtitle">{integration.description}</div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="modal-body">
          {integration.setup_instructions?.length > 0 && (
            <div className="modal-instructions">
              <div className="modal-instructions-title">Setup</div>
              <ol>
                {integration.setup_instructions.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          )}

          <div className="modal-form">
            <div className="form-group">
              <label className="form-label">Display Name</label>
              <input
                className="form-input"
                type="text"
                value={displayName}
                onChange={(e) => { setDisplayName(e.target.value); if (error) setError(null) }}
                placeholder={integration.name}
              />
            </div>

            {(integration.fields || []).filter(shouldShow).map((field) => (
              <div key={field.name} className="form-group">
                <label className="form-label">
                  {field.label}
                  {field.required && <span style={{ color: 'var(--cat-color)', marginLeft: 4 }}>*</span>}
                </label>
                {field.type === 'select' ? (
                  <select
                    className="form-select"
                    value={formValues[field.name] || ''}
                    onChange={(e) => handleField(field.name, e.target.value)}
                  >
                    <option value="">Select…</option>
                    {field.options.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="form-input"
                    type={field.type}
                    value={formValues[field.name] || ''}
                    onChange={(e) => handleField(field.name, e.target.value)}
                    placeholder={field.placeholder || ''}
                    autoComplete={field.type === 'password' ? 'new-password' : undefined}
                  />
                )}
              </div>
            ))}

            {isNone && (
              <div style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', padding: '8px 0' }}>
                No additional setup required.
              </div>
            )}
          </div>

          {error && (
            <div className="modal-error">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" style={{ flexShrink: 0 }}>
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><circle cx="12" cy="16" r="0.5" fill="currentColor"/>
              </svg>
              {error}
            </div>
          )}
        </div>

        <div className="modal-footer">
          {isEditing && (
            <button
              className="btn btn-danger"
              onClick={handleDisconnectClick}
              disabled={disconnecting}
            >
              {disconnecting ? 'Removing…' : 'Disconnect'}
            </button>
          )}
          <button className="btn btn-secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>

          {!isOAuth && !isNone && (
            <button
              className="btn btn-primary"
              style={catStyle}
              onClick={handleSave}
              disabled={connectDisabled}
              title={connectDisabled && !saving ? 'Fill in all required fields first' : undefined}
            >
              {saving ? 'Connecting…' : isEditing ? 'Save Changes' : 'Connect'}
            </button>
          )}

          {isOAuth && !isEditing && (
            <button
              className="btn btn-primary"
              style={catStyle}
              onClick={handleSaveAndOAuth}
              disabled={connectDisabled}
              title={connectDisabled && !saving ? 'Fill in all required fields first' : undefined}
            >
              {saving ? 'Opening…' : `Connect with ${getOAuthLabel(integration)}`}
            </button>
          )}

          {isOAuth && isEditing && (
            <>
              <button
                className="btn btn-secondary"
                style={{ borderColor: meta.color, color: meta.color }}
                onClick={handleReauthorize}
                disabled={saving}
              >
                Re-authorize
              </button>
              <button
                className="btn btn-primary"
                style={catStyle}
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? 'Saving…' : 'Save Changes'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function getOAuthLabel(integration) {
  if (integration.oauth_url?.includes('spotify')) return 'Spotify'
  if (integration.oauth_url?.includes('gcal')) return 'Google'
  if (integration.oauth_url?.includes('fatsecret')) return 'FatSecret'
  return 'OAuth'
}
