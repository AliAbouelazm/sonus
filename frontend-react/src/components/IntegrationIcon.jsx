import { useState } from 'react'

// ── Custom SVG icons for integrations without real logos ──────
const CUSTOM_SVGS = {
  smart_lock: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2"/>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
      <circle cx="12" cy="16" r="1" fill={color}/>
    </svg>
  ),
  smart_bulb: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21h6M10 17h4"/>
      <path d="M12 3a6 6 0 0 1 4.24 10.24c-.7.7-1.24 1.6-1.24 2.76H9c0-1.16-.54-2.07-1.24-2.76A6 6 0 0 1 12 3z"/>
    </svg>
  ),
  smart_fan: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="2"/>
      <path d="M12 10C12 7.5 13 4 16 4s3.5 2 2.5 4.5S15 11 12 10z"/>
      <path d="M12 14C12 16.5 11 20 8 20s-3.5-2-2.5-4.5S9 13 12 14z"/>
      <path d="M10 12C7.5 12 4 11 4 8s2-3.5 4.5-2.5S11 9 10 12z"/>
      <path d="M14 12C16.5 12 20 13 20 16s-2 3.5-4.5 2.5S13 15 14 12z"/>
    </svg>
  ),
  smart_ac: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="2" x2="12" y2="22"/>
      <polyline points="8 6 12 2 16 6"/>
      <polyline points="8 18 12 22 16 18"/>
      <line x1="2" y1="12" x2="22" y2="12"/>
      <polyline points="6 8 2 12 6 16"/>
      <polyline points="18 8 22 12 18 16"/>
    </svg>
  ),
  weather: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4" fill={color} fillOpacity="0.2"/>
      <line x1="12" y1="2" x2="12" y2="4"/>
      <line x1="12" y1="20" x2="12" y2="22"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
      <line x1="2" y1="12" x2="4" y2="12"/>
      <line x1="20" y1="12" x2="22" y2="12"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </svg>
  ),
  oura: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="14" rx="7" ry="4"/>
      <path d="M5 14V10a7 4 0 0 1 14 0v4" strokeLinejoin="round"/>
      <ellipse cx="12" cy="10" rx="7" ry="4" fill={color} fillOpacity="0.15"/>
    </svg>
  ),
  canvas: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
      <line x1="9" y1="7" x2="15" y2="7"/>
      <line x1="9" y1="11" x2="15" y2="11"/>
      <line x1="9" y1="15" x2="12" y2="15"/>
    </svg>
  ),
  fatsecret: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a7 7 0 1 0 0 14A7 7 0 0 0 12 2z" fill={color} fillOpacity="0.15"/>
      <path d="M12 6v6l4 2"/>
      <path d="M8 21h8M12 16v5"/>
    </svg>
  ),
  twilio: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9"/>
      <circle cx="9" cy="9" r="1.5" fill={color}/>
      <circle cx="15" cy="9" r="1.5" fill={color}/>
      <circle cx="9" cy="15" r="1.5" fill={color}/>
      <circle cx="15" cy="15" r="1.5" fill={color}/>
    </svg>
  ),
  ntfy: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
      <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      <circle cx="12" cy="3" r="1" fill={color}/>
    </svg>
  ),
  whoop: ({ color, size }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="2 12 5 12 7 5 9 19 11 10 13 14 15 12 22 12"/>
    </svg>
  ),
}

// ── Lettermark: colored rounded square with initial ───────────
function Lettermark({ name, color, size }) {
  return (
    <div style={{
      width: size,
      height: size,
      borderRadius: Math.round(size * 0.28),
      background: `${color}1a`,
      border: `1.5px solid ${color}55`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: Math.round(size * 0.52),
      fontWeight: 700,
      color,
      fontFamily: 'system-ui, -apple-system, sans-serif',
      flexShrink: 0,
      userSelect: 'none',
      letterSpacing: 0,
    }}>
      {name[0].toUpperCase()}
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────
export default function IntegrationIcon({ integration, size = 24 }) {
  const [logoFailed, setLogoFailed] = useState(false)

  const CustomSVG = CUSTOM_SVGS[integration.id]
  if (CustomSVG) {
    return (
      <div style={{ width: size, height: size, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CustomSVG color={integration.color} size={size} />
      </div>
    )
  }

  if (integration.logo && !logoFailed) {
    // clearbit logos are raster images that may have transparent/white bg — give them a neutral bg
    const isClearbit = integration.logo.includes('clearbit')
    return (
      <div style={{
        width: size, height: size, flexShrink: 0, display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        borderRadius: Math.round(size * 0.2),
        background: isClearbit ? 'rgba(255,255,255,0.9)' : 'transparent',
        padding: isClearbit ? Math.round(size * 0.08) : 0,
      }}>
        <img
          src={integration.logo}
          alt={integration.name}
          width={isClearbit ? size * 0.84 : size}
          height={isClearbit ? size * 0.84 : size}
          style={{ objectFit: 'contain', display: 'block' }}
          onError={() => setLogoFailed(true)}
        />
      </div>
    )
  }

  // Use emoji if available, otherwise lettermark
  if (integration.emoji) {
    return (
      <div style={{
        width: size, height: size, flexShrink: 0, display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        fontSize: Math.round(size * 0.72),
        lineHeight: 1,
        userSelect: 'none',
      }}>
        {integration.emoji}
      </div>
    )
  }

  return <Lettermark name={integration.name} color={integration.color} size={size} />
}
