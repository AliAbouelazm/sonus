import { useState } from 'react'
import { useDroppable } from '@dnd-kit/core'
import { CATEGORY_META, INTEGRATION_TO_DEVICE_PREFIX } from '../data/integrations.js'
import IntegrationIcon from './IntegrationIcon.jsx'

const BRAIN_R = 90
const R_NEAR  = 200
const R_FAR   = 278
const SIZE    = R_FAR * 2 + 100
const CX      = SIZE / 2
const CY      = SIZE / 2

const CATEGORY_ORDER = ['software', 'wearables', 'hardware', 'communication']

const nodeRadius = (i) => i % 2 === 0 ? R_NEAR : R_FAR

function getLabel(item) {
  return item.display_name && item.display_name !== item.name
    ? item.display_name
    : item.name
}

function getDeviceStatus(item, devices) {
  const prefix = INTEGRATION_TO_DEVICE_PREFIX[item.integration_id]
  if (!prefix) return null

  const deviceId = `${prefix}.${item.instance_id}`
  const device = devices[deviceId]
  if (!device?.state) return null

  const { state, device_type } = device

  if (device_type === 'lock') return state.locked ? 'Locked' : 'Unlocked'
  if (state.on === false) return 'Off'
  if (state.on === true) {
    const parts = []
    if (state.brightness !== undefined) parts.push(`${state.brightness}%`)
    if (state.speed) parts.push(state.speed)
    if (state.target_temp) parts.push(`${state.target_temp}°F`)
    return parts.length ? parts.join(' · ') : 'On'
  }
  return null
}

export default function Brain({ connected, devices = {}, isOver, onClickConnected }) {
  const { setNodeRef } = useDroppable({ id: 'brain' })
  const [hovered, setHovered] = useState(null)

  const sorted = [...connected].sort((a, b) =>
    CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category)
  )

  const total = sorted.length

  return (
    <div className="brain-container" style={{ width: SIZE, height: SIZE }}>

      {/* SVG: dashed connection lines + brain-edge dots */}
      <svg
        style={{ position: 'absolute', inset: 0, width: SIZE, height: SIZE, overflow: 'visible', pointerEvents: 'none', zIndex: 2 }}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
      >
        {sorted.map((item, i) => {
          const meta  = CATEGORY_META[item.category]
          const angle = (i * 360 / total - 90) * Math.PI / 180
          const r     = nodeRadius(i)
          const nx    = CX + Math.cos(angle) * r
          const ny    = CY + Math.sin(angle) * r
          const bx    = CX + Math.cos(angle) * (BRAIN_R + 4)
          const by    = CY + Math.sin(angle) * (BRAIN_R + 4)
          const id    = item.instance_id || item.id
          const isHov = hovered === id

          return (
            <g key={`line-${id}`}>
              {/* Glow line (wider, low opacity) */}
              {isHov && (
                <line
                  x1={bx} y1={by} x2={nx} y2={ny}
                  stroke={meta.color}
                  strokeWidth={6}
                  strokeOpacity={0.08}
                  strokeLinecap="round"
                />
              )}
              {/* Main dashed line */}
              <line
                x1={bx} y1={by} x2={nx} y2={ny}
                stroke={meta.color}
                strokeWidth={isHov ? 1.4 : 0.8}
                strokeOpacity={isHov ? 0.7 : 0.2}
                strokeDasharray="4 5"
                strokeLinecap="round"
                style={{ transition: 'stroke-opacity 0.2s, stroke-width 0.2s' }}
              />
              {/* Dot at brain edge */}
              <circle
                cx={bx} cy={by} r={isHov ? 3 : 2}
                fill={meta.color}
                fillOpacity={isHov ? 1 : 0.45}
                style={{ transition: 'fill-opacity 0.2s, r 0.2s' }}
              />
            </g>
          )
        })}
      </svg>

      {/* Brain drop target */}
      <div
        ref={setNodeRef}
        className={`brain ${isOver ? 'drop-over' : ''}`}
        style={{ left: CX - BRAIN_R, top: CY - BRAIN_R }}
      >
        <div className="brain-inner">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#e8b4f8" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" style={{ filter: 'drop-shadow(0 0 10px rgba(191,90,242,0.9))' }}>
            <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="3" />
          </svg>
          <span className="brain-label">SONUS</span>
          {total > 0
            ? <span className="brain-count">{total} connected</span>
            : <span className="brain-hint">drop here</span>
          }
        </div>
      </div>

      {/* Connection node chips */}
      {sorted.map((item, i) => {
        const meta  = CATEGORY_META[item.category]
        const angle = (i * 360 / total - 90) * Math.PI / 180
        const r     = nodeRadius(i)
        const nx    = CX + Math.cos(angle) * r
        const ny    = CY + Math.sin(angle) * r
        const label = getLabel(item)
        const id    = item.instance_id || item.id
        const isHov = hovered === id

        const status = getDeviceStatus(item, devices)
        // locked = secure = green, unlocked/off = dim
        const statusIsOn = status != null && status !== 'Off' && status !== 'Unlocked'

        return (
          <div
            key={`node-${id}`}
            className="conn-node"
            style={{
              left: nx,
              top: ny,
              '--node-color': meta.color,
              background: isHov ? `${meta.color}1e` : `${meta.color}0d`,
              borderColor: isHov ? meta.color : `${meta.color}50`,
              boxShadow: isHov ? `0 0 12px ${meta.color}28, inset 0 0 8px ${meta.color}0a` : 'none',
            }}
            onClick={() => onClickConnected(item)}
            onMouseEnter={() => setHovered(id)}
            onMouseLeave={() => setHovered(null)}
          >
            <IntegrationIcon integration={item} size={13} />
            <span className="conn-node-name" style={{ color: isHov ? meta.color : `${meta.color}bb` }}>
              {label}
            </span>
            {status && (
              <span
                className="conn-node-status"
                style={{
                  fontSize: 9,
                  marginLeft: 6,
                  padding: '1px 5px',
                  borderRadius: 3,
                  background: statusIsOn ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.08)',
                  color: statusIsOn ? '#4ade80' : 'rgba(255,255,255,0.5)',
                  fontWeight: 500,
                  letterSpacing: '0.3px',
                }}
              >
                {status}
              </span>
            )}
            {isHov && (
              <svg className="conn-node-gear" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke={meta.color} strokeWidth="2.5" strokeLinecap="round">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            )}
          </div>
        )
      })}

    </div>
  )
}
