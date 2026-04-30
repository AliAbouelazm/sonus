import { CATEGORY_META, getByCategory } from '../data/integrations.js'
import IntegrationBlock from './IntegrationBlock.jsx'

export default function CategoryPanel({ categories, connectedIds, connectedMap, side }) {
  return (
    <div className={`panel-column ${side}`}>
      {categories.map((cat) => {
        const meta = CATEGORY_META[cat]
        const items = getByCategory(cat)
        return (
          <div key={cat} className="panel-category">
            <div className="panel-category-header">
              <div className="panel-category-dot" style={{ background: meta.color }} />
              <span className="panel-category-label">{meta.label}</span>
            </div>
            <div className="panel-category-divider" />
            <div className="panel-category-items">
              {items.map((integration) => {
                const connectedEntry = connectedMap?.[integration.id]
                return (
                  <IntegrationBlock
                    key={integration.id}
                    integration={integration}
                    isConnected={connectedIds.has(integration.id)}
                    displayName={integration.allow_multiple ? undefined : connectedEntry?.display_name}
                  />
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
