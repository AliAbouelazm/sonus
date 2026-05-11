import { useState, useEffect, useCallback, useRef } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  pointerWithin,
} from '@dnd-kit/core'

import { CATEGORIES_LEFT, CATEGORIES_RIGHT, getById } from '../data/integrations.js'
import { useWS } from '../contexts/WebSocketContext.jsx'
import CategoryPanel from '../components/CategoryPanel.jsx'
import Brain from '../components/Brain.jsx'
import ConfigModal from '../components/ConfigModal.jsx'
import { IntegrationBlockOverlay } from '../components/IntegrationBlock.jsx'

export default function IntegrationsPage() {
  const [connected, setConnected] = useState([])
  const [loadingInitial, setLoadingInitial] = useState(true)
  const [devices, setDevices] = useState({})

  const [activeDrag, setActiveDrag] = useState(null)
  const [isOverBrain, setIsOverBrain] = useState(false)

  const [modalIntegration, setModalIntegration] = useState(null)
  const [modalExisting, setModalExisting] = useState(null)

  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const [recentering, setRecentering] = useState(false)
  const panRef = useRef({ active: false, startMx: 0, startMy: 0, startPx: 0, startPy: 0, liveX: 0, liveY: 0 })
  const pannableRef = useRef(null)
  const brainAreaRef = useRef(null)

  const isOffCenter = Math.abs(pan.x) > 8 || Math.abs(pan.y) > 8

  function handleBrainAreaMouseDown(e) {
    if (e.button !== 0) return
    if (e.target.closest('.conn-node') || e.target.closest('.brain')) return
    panRef.current = { active: true, startMx: e.clientX, startMy: e.clientY, startPx: pan.x, startPy: pan.y, liveX: pan.x, liveY: pan.y }
    setIsPanning(true)
  }

  function handleBrainAreaMouseMove(e) {
    if (!panRef.current.active) return
    const { startMx, startMy, startPx, startPy } = panRef.current
    const x = startPx + e.clientX - startMx
    const y = startPy + e.clientY - startMy
    panRef.current.liveX = x
    panRef.current.liveY = y
    if (pannableRef.current) {
      pannableRef.current.style.transform = `translate(${x}px, ${y}px)`
    }
    if (brainAreaRef.current) {
      brainAreaRef.current.style.setProperty('--grid-x', `${x % 40}px`)
      brainAreaRef.current.style.setProperty('--grid-y', `${y % 40}px`)
    }
  }

  function handleBrainAreaMouseUp() {
    if (panRef.current.active) {
      setPan({ x: panRef.current.liveX, y: panRef.current.liveY })
    }
    panRef.current.active = false
    setIsPanning(false)
  }

  function recenter() {
    setRecentering(true)
    setPan({ x: 0, y: 0 })
    panRef.current.liveX = 0
    panRef.current.liveY = 0
    setTimeout(() => setRecentering(false), 500)
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  )

  const { lastMessage } = useWS()

  async function fetchConnected() {
    try {
      const res = await fetch('/api/integrations')
      if (!res.ok) return
      const data = await res.json()
      const enriched = data.integrations.map((cfg) => ({
        ...getById(cfg.integration_id),
        ...cfg,
      }))
      setConnected(enriched)
    } catch (_) {
      // Backend might not be running; swallow error gracefully
    } finally {
      setLoadingInitial(false)
    }
  }

  useEffect(() => {
    fetchConnected()
    fetch('/api/devices')
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data && typeof data === 'object') setDevices(data) })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!lastMessage) return

    if (lastMessage.type === 'reset') {
      setConnected([])
      setDevices({})
      return
    }

    if (lastMessage.type === 'device_update') {
      setDevices((prev) => ({
        ...prev,
        [lastMessage.device_id]: {
          device_id: lastMessage.device_id,
          device_type: lastMessage.device_type,
          state: lastMessage.state,
        },
      }))
      return
    }

    if (lastMessage.type === 'integration_update') {
      fetchConnected()
      return
    }
  }, [lastMessage])

  const connectedIds = new Set(
    connected.filter((c) => !c.allow_multiple).map((c) => c.integration_id)
  )

  const connectedMap = {}
  for (const c of connected) {
    connectedMap[c.integration_id] = c
  }

  function handleDragStart(event) {
    setActiveDrag(event.active.data.current?.integration || null)
  }

  function handleDragOver(event) {
    setIsOverBrain(event.over?.id === 'brain')
  }

  function handleDragEnd(event) {
    setIsOverBrain(false)
    setActiveDrag(null)

    const { active, over } = event
    if (!over || over.id !== 'brain') return

    const integration = active.data.current?.integration
    if (!integration) return

    setModalIntegration(integration)
    setModalExisting(null)
  }

  function handleDragCancel() {
    setIsOverBrain(false)
    setActiveDrag(null)
  }

  function handleClickConnected(integration) {
    setModalIntegration(getById(integration.integration_id) || integration)
    setModalExisting(integration)
  }

  const closeModal = useCallback(() => {
    setModalIntegration(null)
    setModalExisting(null)
  }, [])

  const handleSave = useCallback(async (payload) => {
    const res = await fetch('/api/integrations/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || `Server error (${res.status})`)
    }
    await fetchConnected()
    closeModal()
  }, [closeModal])

  const handleDisconnect = useCallback(async () => {
    if (!modalExisting) return
    const res = await fetch(`/api/integrations/${encodeURIComponent(modalExisting.instance_id)}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || `Server error (${res.status})`)
    }
    setConnected((prev) => prev.filter((c) => c.instance_id !== modalExisting.instance_id))
    closeModal()
  }, [modalExisting, closeModal])

  return (
    <>
      <DndContext
        sensors={sensors}
        collisionDetection={pointerWithin}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        <div className="integrations-page">
          <CategoryPanel
            categories={CATEGORIES_LEFT}
            connectedIds={connectedIds}
            connectedMap={connectedMap}
            side="left"
          />

          <div
            ref={brainAreaRef}
            className="brain-area"
            style={{
              cursor: isPanning ? 'grabbing' : 'grab',
              '--grid-x': `${pan.x % 40}px`,
              '--grid-y': `${pan.y % 40}px`,
            }}
            onMouseDown={handleBrainAreaMouseDown}
            onMouseMove={handleBrainAreaMouseMove}
            onMouseUp={handleBrainAreaMouseUp}
            onMouseLeave={handleBrainAreaMouseUp}
          >
            <div
              ref={pannableRef}
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px)`,
                transition: recentering ? 'transform 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94)' : 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Brain
                connected={connected}
                devices={devices}
                isOver={isOverBrain}
                onClickConnected={handleClickConnected}
              />
            </div>

            {!loadingInitial && connected.length === 0 && !activeDrag && (
              <div className="drop-hint">
                Drag an integration and drop it on the brain to connect
              </div>
            )}

            {isOffCenter && (
              <button className="recenter-btn" onClick={recenter}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>
                </svg>
                recenter
              </button>
            )}
          </div>

          <CategoryPanel
            categories={CATEGORIES_RIGHT}
            connectedIds={connectedIds}
            connectedMap={connectedMap}
            side="right"
          />
        </div>

        <DragOverlay dropAnimation={null}>
          {activeDrag ? <IntegrationBlockOverlay integration={activeDrag} /> : null}
        </DragOverlay>
      </DndContext>

      {modalIntegration && (
        <ConfigModal
          key={modalExisting?.instance_id ?? modalIntegration.id}
          integration={modalIntegration}
          existingConfig={modalExisting}
          onSave={handleSave}
          onDisconnect={handleDisconnect}
          onClose={closeModal}
        />
      )}
    </>
  )
}
