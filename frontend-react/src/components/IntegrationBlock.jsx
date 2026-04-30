import { useDraggable } from '@dnd-kit/core'
import { CATEGORY_META } from '../data/integrations.js'
import IntegrationIcon from './IntegrationIcon.jsx'

export default function IntegrationBlock({ integration, isConnected, displayName }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: integration.id,
    data: { integration },
    disabled: isConnected,
  })

  const meta = CATEGORY_META[integration.category]
  const label = displayName || integration.name

  return (
    <div
      ref={setNodeRef}
      style={{ '--cat-color': meta.color }}
      {...listeners}
      {...attributes}
      className={[
        'integration-block',
        isDragging ? 'dragging' : '',
        isConnected ? 'connected-outside' : '',
      ].filter(Boolean).join(' ')}
      title={isConnected ? `${label} — already connected` : `Drag to connect ${label}`}
    >
      <div style={{ width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <IntegrationIcon integration={integration} size={20} />
      </div>
      <div className="integration-info">
        <div className="integration-name">{label}</div>
        {isConnected ? (
          <div
            className="integration-connected-badge"
            style={{
              color: meta.color,
              borderColor: `${meta.color}40`,
              background: `${meta.color}12`,
            }}
          >
            connected
          </div>
        ) : (
          <div className="integration-desc">{integration.description}</div>
        )}
      </div>
    </div>
  )
}

export function IntegrationBlockOverlay({ integration }) {
  const meta = CATEGORY_META[integration.category]
  return (
    <div
      className="drag-overlay-block"
      style={{ '--cat-color': meta.color, '--cat-color-shadow': `${meta.color}33` }}
    >
      <div style={{ width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <IntegrationIcon integration={integration} size={20} />
      </div>
      <div className="integration-info">
        <div className="integration-name">{integration.name}</div>
        <div className="integration-desc" style={{ color: meta.color, opacity: 0.7 }}>Drop on brain to connect</div>
      </div>
    </div>
  )
}
