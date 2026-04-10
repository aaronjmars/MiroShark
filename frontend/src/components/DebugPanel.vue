<template>
  <div v-if="isVisible" class="debug-panel" :class="{ 'debug-panel--collapsed': isCollapsed }">
    <!-- Header -->
    <div class="debug-header" @click="isCollapsed = !isCollapsed">
      <div class="debug-header__left">
        <span class="debug-header__icon">&#9881;</span>
        <span class="debug-header__title">OBSERVABILITY</span>
        <span v-if="connected" class="debug-header__status debug-header__status--live">LIVE</span>
        <span v-else class="debug-header__status debug-header__status--off">OFF</span>
        <span v-if="stats.llm_calls" class="debug-header__stat">{{ stats.llm_calls }} calls</span>
        <span v-if="stats.tokens_total" class="debug-header__stat">{{ formatTokens(stats.tokens_total) }} tok</span>
      </div>
      <div class="debug-header__right">
        <button class="debug-btn debug-btn--icon" :class="{ 'debug-btn--copied': justCopied }" @click.stop="copyAll" :title="justCopied ? 'Copied!' : 'Copy all events'">{{ justCopied ? '&#10003;' : '&#9112;' }}</button>
        <button class="debug-btn debug-btn--icon" @click.stop="clearEvents" title="Clear">&#10005;</button>
        <button class="debug-btn debug-btn--icon" @click.stop="isVisible = false" title="Close (Ctrl+Shift+D)">&#9866;</button>
      </div>
    </div>

    <!-- Body -->
    <div v-show="!isCollapsed" class="debug-body">
      <!-- Tabs -->
      <div class="debug-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="debug-tab"
          :class="{ 'debug-tab--active': activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span v-if="tab.key === 'errors' && errorCount > 0" class="debug-tab__badge">{{ errorCount }}</span>
        </button>
      </div>

      <!-- Filters -->
      <div class="debug-filters">
        <select v-model="filterPlatform" class="debug-select">
          <option value="">All platforms</option>
          <option value="twitter">Twitter</option>
          <option value="reddit">Reddit</option>
        </select>
        <input
          v-model="filterText"
          class="debug-input"
          placeholder="Filter..."
        />
        <label class="debug-checkbox">
          <input type="checkbox" v-model="autoScroll" />
          Auto-scroll
        </label>
      </div>

      <!-- Tab Content -->
      <div class="debug-content" ref="contentRef">

        <!-- Live Feed -->
        <div v-if="activeTab === 'feed'" class="debug-feed">
          <div v-if="filteredEvents.length === 0" class="debug-empty">
            No events yet. Waiting for activity...
          </div>
          <div
            v-for="event in filteredEvents"
            :key="event.event_id"
            class="debug-event"
            :class="'debug-event--' + event.event_type"
            @click="toggleExpand(event.event_id)"
          >
            <div class="debug-event__row">
              <span class="debug-event__time">{{ formatTime(event.timestamp) }}</span>
              <span class="debug-event__badge" :class="'debug-badge--' + event.event_type">
                {{ event.event_type }}
              </span>
              <span v-if="event.platform" class="debug-event__platform">{{ event.platform }}</span>
              <span v-if="event.agent_name" class="debug-event__agent">{{ event.agent_name }}</span>
              <span class="debug-event__preview">{{ getPreview(event) }}</span>
            </div>
            <div v-if="expandedIds.has(event.event_id)" class="debug-event__detail">
              <pre>{{ JSON.stringify(event.data, null, 2) }}</pre>
            </div>
          </div>
        </div>

        <!-- LLM Calls -->
        <div v-if="activeTab === 'llm'" class="debug-llm">
          <div class="debug-llm__summary">
            <div class="debug-stat-card">
              <div class="debug-stat-card__value">{{ stats.llm_calls }}</div>
              <div class="debug-stat-card__label">Total Calls</div>
            </div>
            <div class="debug-stat-card">
              <div class="debug-stat-card__value">{{ formatTokens(stats.tokens_total) }}</div>
              <div class="debug-stat-card__label">Total Tokens</div>
            </div>
            <div class="debug-stat-card">
              <div class="debug-stat-card__value">{{ stats.avg_latency_ms }}ms</div>
              <div class="debug-stat-card__label">Avg Latency</div>
            </div>
            <div class="debug-stat-card">
              <div class="debug-stat-card__value">{{ stats.errors }}</div>
              <div class="debug-stat-card__label">Errors</div>
            </div>
          </div>
          <div class="debug-llm__table">
            <div class="debug-table-header">
              <span class="debug-col--time">Time</span>
              <span class="debug-col--caller">Caller</span>
              <span class="debug-col--model">Model</span>
              <span class="debug-col--tokens">In/Out</span>
              <span class="debug-col--latency">Latency</span>
            </div>
            <div
              v-for="event in llmEvents"
              :key="event.event_id"
              class="debug-table-row"
              @click="toggleExpand(event.event_id)"
            >
              <span class="debug-col--time">{{ formatTime(event.timestamp) }}</span>
              <span class="debug-col--caller">{{ event.data?.caller }}</span>
              <span class="debug-col--model">{{ shortModel(event.data?.model) }}</span>
              <span class="debug-col--tokens">
                {{ event.data?.tokens_input ?? '?' }}/{{ event.data?.tokens_output ?? '?' }}
              </span>
              <span class="debug-col--latency" :class="latencyClass(event.data?.latency_ms)">
                {{ event.data?.latency_ms }}ms
              </span>
              <div v-if="expandedIds.has(event.event_id)" class="debug-table-row__detail">
                <div v-if="event.data?.response_preview" class="debug-detail-section">
                  <strong>Response preview:</strong>
                  <pre>{{ event.data.response_preview }}</pre>
                </div>
                <div v-if="event.data?.messages" class="debug-detail-section">
                  <strong>Messages:</strong>
                  <pre>{{ JSON.stringify(event.data.messages, null, 2) }}</pre>
                </div>
                <div v-if="event.data?.response" class="debug-detail-section">
                  <strong>Full response:</strong>
                  <pre>{{ event.data.response }}</pre>
                </div>
                <div v-if="event.data?.error" class="debug-detail-section debug-detail-section--error">
                  <strong>Error:</strong> {{ event.data.error }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Agent Trace -->
        <div v-if="activeTab === 'agents'" class="debug-agents">
          <div v-if="agentDecisions.length === 0" class="debug-empty">
            No agent decisions recorded yet.
          </div>
          <div
            v-for="event in agentDecisions"
            :key="event.event_id"
            class="debug-agent-card"
            @click="toggleExpand(event.event_id)"
          >
            <div class="debug-agent-card__header">
              <span class="debug-event__time">{{ formatTime(event.timestamp) }}</span>
              <span v-if="event.round_num" class="debug-agent-card__round">R{{ event.round_num }}</span>
              <span class="debug-agent-card__name">{{ event.agent_name || `Agent #${event.agent_id}` }}</span>
              <span
                class="debug-agent-card__action"
                :class="event.data?.success ? 'debug-agent-card__action--ok' : 'debug-agent-card__action--fail'"
              >
                {{ event.data?.parsed_action?.action_type || 'unknown' }}
              </span>
            </div>
            <div v-if="expandedIds.has(event.event_id)" class="debug-agent-card__detail">
              <div v-if="event.data?.env_prompt_preview" class="debug-detail-section">
                <strong>Environment observation:</strong>
                <pre>{{ event.data.env_prompt || event.data.env_prompt_preview }}</pre>
              </div>
              <div v-if="event.data?.llm_response_preview" class="debug-detail-section">
                <strong>LLM response:</strong>
                <pre>{{ event.data.llm_response || event.data.llm_response_preview }}</pre>
              </div>
              <div v-if="event.data?.tool_calls?.length" class="debug-detail-section">
                <strong>Tool calls:</strong>
                <pre>{{ JSON.stringify(event.data.tool_calls, null, 2) }}</pre>
              </div>
              <div v-if="event.data?.error" class="debug-detail-section debug-detail-section--error">
                <strong>Error:</strong> {{ event.data.error }}
              </div>
            </div>
          </div>
        </div>

        <!-- Errors -->
        <div v-if="activeTab === 'errors'" class="debug-errors">
          <div v-if="errorEvents.length === 0" class="debug-empty">
            No errors recorded.
          </div>
          <div
            v-for="event in errorEvents"
            :key="event.event_id"
            class="debug-error-card"
            @click="toggleExpand(event.event_id)"
          >
            <div class="debug-error-card__header">
              <span class="debug-event__time">{{ formatTime(event.timestamp) }}</span>
              <span class="debug-error-card__class">{{ event.data?.error_class || event.event_type }}</span>
              <span class="debug-error-card__msg">{{ event.data?.message || event.data?.error || 'Unknown error' }}</span>
            </div>
            <div v-if="expandedIds.has(event.event_id)" class="debug-error-card__detail">
              <div v-if="event.data?.context" class="debug-detail-section">
                <strong>Context:</strong> {{ event.data.context }}
              </div>
              <pre v-if="event.data?.traceback" class="debug-traceback">{{ event.data.traceback }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { streamEvents, getObservabilityStats } from '../api/observability'

const route = useRoute()

// State
const isVisible = ref(false)
const isCollapsed = ref(false)
const activeTab = ref('feed')
const autoScroll = ref(true)
const filterPlatform = ref('')
const filterText = ref('')
const contentRef = ref(null)
const connected = ref(false)
const expandedIds = reactive(new Set())

const events = ref([])
const stats = ref({
  llm_calls: 0, tokens_input: 0, tokens_output: 0, tokens_total: 0,
  avg_latency_ms: 0, errors: 0, events_by_type: {}, models_used: {},
})

const MAX_EVENTS = 2000
const justCopied = ref(false)

const tabs = [
  { key: 'feed', label: 'Live Feed' },
  { key: 'llm', label: 'LLM Calls' },
  { key: 'agents', label: 'Agent Trace' },
  { key: 'errors', label: 'Errors' },
]

// SSE connection
let eventSource = null
let statsTimer = null

const simulationId = computed(() => {
  return route.params?.simulationId || route.params?.id || null
})

function connectSSE() {
  disconnectSSE()
  try {
    eventSource = streamEvents(simulationId.value, '')
    eventSource.onopen = () => { connected.value = true }
    eventSource.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        if (event.type === 'heartbeat') return
        addEvent(event)
      } catch {}
    }
    // Named event handlers
    for (const et of ['llm_call', 'agent_decision', 'round_boundary', 'graph_build', 'graph_ner', 'error', 'system']) {
      eventSource.addEventListener(et, (e) => {
        try {
          addEvent(JSON.parse(e.data))
        } catch {}
      })
    }
    eventSource.onerror = () => {
      connected.value = false
      // Auto-reconnect after 3 seconds
      setTimeout(() => {
        if (isVisible.value) connectSSE()
      }, 3000)
    }
  } catch {
    connected.value = false
  }
}

function disconnectSSE() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  connected.value = false
}

function addEvent(event) {
  events.value.push(event)
  if (events.value.length > MAX_EVENTS) {
    events.value = events.value.slice(-MAX_EVENTS)
  }

  // Update local stats
  if (event.event_type === 'llm_call') {
    stats.value.llm_calls++
    stats.value.tokens_input += event.data?.tokens_input || 0
    stats.value.tokens_output += event.data?.tokens_output || 0
    stats.value.tokens_total += event.data?.tokens_total || 0
    if (event.data?.error) stats.value.errors++
  } else if (event.event_type === 'error') {
    stats.value.errors++
  }

  if (autoScroll.value) {
    nextTick(() => {
      if (contentRef.value) {
        contentRef.value.scrollTop = contentRef.value.scrollHeight
      }
    })
  }
}

function clearEvents() {
  events.value = []
  stats.value = {
    llm_calls: 0, tokens_input: 0, tokens_output: 0, tokens_total: 0,
    avg_latency_ms: 0, errors: 0, events_by_type: {}, models_used: {},
  }
}

async function copyAll() {
  const payload = JSON.stringify(events.value, null, 2)
  try {
    await navigator.clipboard.writeText(payload)
    justCopied.value = true
    setTimeout(() => { justCopied.value = false }, 1500)
  } catch {
    // Fallback for non-HTTPS contexts
    const ta = document.createElement('textarea')
    ta.value = payload
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    justCopied.value = true
    setTimeout(() => { justCopied.value = false }, 1500)
  }
}

async function fetchStats() {
  try {
    const res = await getObservabilityStats(simulationId.value)
    if (res.stats) stats.value = res.stats
  } catch {}
}

// Filtered views
const filteredEvents = computed(() => {
  return events.value.filter(e => {
    if (filterPlatform.value && e.platform !== filterPlatform.value) return false
    if (filterText.value) {
      const text = filterText.value.toLowerCase()
      const str = JSON.stringify(e).toLowerCase()
      if (!str.includes(text)) return false
    }
    return true
  })
})

const llmEvents = computed(() => events.value.filter(e => e.event_type === 'llm_call'))
const agentDecisions = computed(() => events.value.filter(e => e.event_type === 'agent_decision'))
const errorEvents = computed(() => events.value.filter(e =>
  e.event_type === 'error' || (e.event_type === 'llm_call' && e.data?.error)
))
const errorCount = computed(() => errorEvents.value.length)

// Helpers
function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return ts }
}

function formatTokens(n) {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function shortModel(model) {
  if (!model) return '?'
  // Show last segment of model path
  const parts = model.split('/')
  return parts[parts.length - 1]
}

function latencyClass(ms) {
  if (!ms) return ''
  if (ms > 10000) return 'debug-latency--slow'
  if (ms > 3000) return 'debug-latency--medium'
  return 'debug-latency--fast'
}

function getPreview(event) {
  const d = event.data
  if (!d) return ''
  if (event.event_type === 'llm_call') {
    return `${d.caller || '?'} [${shortModel(d.model)}] ${d.latency_ms}ms ${d.tokens_total || '?'}tok`
  }
  if (event.event_type === 'agent_decision') {
    return d.parsed_action?.action_type || d.error || ''
  }
  if (event.event_type === 'round_boundary') {
    return `${d.boundary} ${d.actions_count != null ? d.actions_count + ' actions' : ''}`
  }
  if (event.event_type === 'graph_build') {
    return d.phase + (d.node_count ? ` (${d.node_count} nodes)` : '')
  }
  if (event.event_type === 'error') {
    return d.message || d.error_class || ''
  }
  return ''
}

function toggleExpand(id) {
  if (expandedIds.has(id)) {
    expandedIds.delete(id)
  } else {
    expandedIds.add(id)
  }
}

// Keyboard shortcut
function onKeydown(e) {
  if (e.ctrlKey && e.shiftKey && e.key === 'D') {
    e.preventDefault()
    isVisible.value = !isVisible.value
  }
}

// Lifecycle
watch(isVisible, (val) => {
  if (val) {
    connectSSE()
    fetchStats()
    statsTimer = setInterval(fetchStats, 15000)
  } else {
    disconnectSSE()
    if (statsTimer) clearInterval(statsTimer)
  }
})

watch(simulationId, () => {
  if (isVisible.value) {
    clearEvents()
    connectSSE()
    fetchStats()
  }
})

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  disconnectSSE()
  if (statsTimer) clearInterval(statsTimer)
})
</script>

<style scoped>
/* ── Panel Container ── */
.debug-panel {
  position: fixed;
  bottom: 0;
  right: 0;
  width: 560px;
  max-height: 70vh;
  background: #0A0A0A;
  color: #E0E0E0;
  font-family: 'Space Mono', 'Courier New', monospace;
  font-size: 11px;
  border-top: 3px solid var(--color-orange, #FF6B1A);
  border-left: 3px solid var(--color-orange, #FF6B1A);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  box-shadow: -4px -4px 20px rgba(0,0,0,0.4);
}

.debug-panel--collapsed {
  max-height: auto;
}

/* ── Header ── */
.debug-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: #141414;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid #222;
  flex-shrink: 0;
}

.debug-header__left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.debug-header__right {
  display: flex;
  gap: 4px;
}

.debug-header__icon {
  font-size: 13px;
  color: var(--color-orange, #FF6B1A);
}

.debug-header__title {
  font-size: 10px;
  font-weight: bold;
  letter-spacing: 2px;
  color: var(--color-orange, #FF6B1A);
}

.debug-header__status {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 2px;
  font-weight: bold;
  letter-spacing: 1px;
}

.debug-header__status--live {
  background: rgba(67, 193, 101, 0.2);
  color: #43C165;
  border: 1px solid rgba(67, 193, 101, 0.4);
}

.debug-header__status--off {
  background: rgba(255, 68, 68, 0.15);
  color: #FF4444;
  border: 1px solid rgba(255, 68, 68, 0.3);
}

.debug-header__stat {
  font-size: 9px;
  color: #888;
}

/* ── Buttons ── */
.debug-btn--icon {
  background: none;
  border: none;
  color: #666;
  font-size: 12px;
  padding: 2px 5px;
  cursor: pointer;
  line-height: 1;
}
.debug-btn--icon:hover {
  color: #fff;
}

.debug-btn--copied {
  color: #43C165 !important;
}

/* ── Body ── */
.debug-body {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 1;
  min-height: 0;
}

/* ── Tabs ── */
.debug-tabs {
  display: flex;
  border-bottom: 1px solid #222;
  flex-shrink: 0;
}

.debug-tab {
  flex: 1;
  padding: 5px 8px;
  background: none;
  border: none;
  color: #666;
  font-family: inherit;
  font-size: 10px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  position: relative;
}

.debug-tab:hover {
  color: #aaa;
}

.debug-tab--active {
  color: var(--color-orange, #FF6B1A);
  border-bottom-color: var(--color-orange, #FF6B1A);
}

.debug-tab__badge {
  position: absolute;
  top: 2px;
  right: 4px;
  background: #FF4444;
  color: #fff;
  font-size: 8px;
  padding: 0 4px;
  border-radius: 6px;
  min-width: 14px;
  text-align: center;
}

/* ── Filters ── */
.debug-filters {
  display: flex;
  gap: 6px;
  padding: 5px 8px;
  border-bottom: 1px solid #1a1a1a;
  flex-shrink: 0;
}

.debug-select, .debug-input {
  background: #1a1a1a;
  border: 1px solid #333;
  color: #ccc;
  font-family: inherit;
  font-size: 10px;
  padding: 3px 6px;
  border-radius: 2px;
}

.debug-input {
  flex: 1;
}

.debug-checkbox {
  display: flex;
  align-items: center;
  gap: 3px;
  color: #888;
  font-size: 10px;
  white-space: nowrap;
}

.debug-checkbox input {
  accent-color: var(--color-orange, #FF6B1A);
}

/* ── Content area ── */
.debug-content {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  max-height: 50vh;
}

.debug-content::-webkit-scrollbar { width: 6px; }
.debug-content::-webkit-scrollbar-track { background: #0A0A0A; }
.debug-content::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }

.debug-empty {
  padding: 24px;
  text-align: center;
  color: #555;
  font-style: italic;
}

/* ── Event cards (Live Feed) ── */
.debug-event {
  padding: 4px 8px;
  border-bottom: 1px solid #151515;
  cursor: pointer;
}

.debug-event:hover {
  background: #141414;
}

.debug-event__row {
  display: flex;
  gap: 6px;
  align-items: center;
}

.debug-event__time {
  color: #555;
  flex-shrink: 0;
  font-size: 10px;
}

.debug-event__badge {
  font-size: 8px;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.debug-badge--llm_call { background: rgba(99,102,241,0.2); color: #818cf8; }
.debug-badge--agent_decision { background: rgba(67,193,101,0.2); color: #43C165; }
.debug-badge--round_boundary { background: rgba(255,179,71,0.2); color: #FFB347; }
.debug-badge--graph_build { background: rgba(59,130,246,0.2); color: #60a5fa; }
.debug-badge--graph_ner { background: rgba(59,130,246,0.15); color: #93c5fd; }
.debug-badge--error { background: rgba(255,68,68,0.2); color: #FF4444; }
.debug-badge--system { background: rgba(255,255,255,0.1); color: #888; }

.debug-event__platform {
  color: #FFB347;
  font-size: 9px;
}

.debug-event__agent {
  color: #43C165;
  font-size: 10px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.debug-event__preview {
  color: #888;
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.debug-event__detail {
  margin-top: 4px;
  padding: 6px;
  background: #111;
  border-radius: 2px;
  overflow-x: auto;
}

.debug-event__detail pre {
  margin: 0;
  font-size: 10px;
  color: #aaa;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

/* ── LLM calls table ── */
.debug-llm__summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  padding: 8px;
  border-bottom: 1px solid #1a1a1a;
}

.debug-stat-card {
  background: #141414;
  padding: 6px 8px;
  border-radius: 3px;
  text-align: center;
  border: 1px solid #222;
}

.debug-stat-card__value {
  font-size: 16px;
  font-weight: bold;
  color: var(--color-orange, #FF6B1A);
}

.debug-stat-card__label {
  font-size: 9px;
  color: #666;
  margin-top: 2px;
}

.debug-table-header {
  display: flex;
  padding: 4px 8px;
  border-bottom: 1px solid #222;
  color: #555;
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.debug-table-row {
  display: flex;
  flex-wrap: wrap;
  padding: 3px 8px;
  border-bottom: 1px solid #111;
  cursor: pointer;
}

.debug-table-row:hover {
  background: #141414;
}

.debug-col--time { width: 65px; flex-shrink: 0; color: #555; }
.debug-col--caller { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #93c5fd; }
.debug-col--model { width: 100px; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; color: #ddd; }
.debug-col--tokens { width: 70px; flex-shrink: 0; text-align: right; color: #aaa; }
.debug-col--latency { width: 65px; flex-shrink: 0; text-align: right; }

.debug-latency--fast { color: #43C165; }
.debug-latency--medium { color: #FFB347; }
.debug-latency--slow { color: #FF4444; }

.debug-table-row__detail {
  width: 100%;
  padding: 6px 0 4px 0;
}

/* ── Detail sections (shared) ── */
.debug-detail-section {
  margin-bottom: 6px;
}

.debug-detail-section strong {
  display: block;
  color: #888;
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}

.debug-detail-section pre {
  margin: 0;
  font-size: 10px;
  color: #aaa;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
  background: #111;
  padding: 4px 6px;
  border-radius: 2px;
}

.debug-detail-section--error {
  color: #FF4444;
}

/* ── Agent trace cards ── */
.debug-agent-card {
  padding: 5px 8px;
  border-bottom: 1px solid #151515;
  cursor: pointer;
}

.debug-agent-card:hover {
  background: #141414;
}

.debug-agent-card__header {
  display: flex;
  gap: 6px;
  align-items: center;
}

.debug-agent-card__round {
  background: rgba(255,179,71,0.2);
  color: #FFB347;
  font-size: 9px;
  padding: 1px 4px;
  border-radius: 2px;
}

.debug-agent-card__name {
  color: #43C165;
  font-size: 10px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.debug-agent-card__action {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 2px;
}

.debug-agent-card__action--ok {
  background: rgba(67,193,101,0.15);
  color: #43C165;
}

.debug-agent-card__action--fail {
  background: rgba(255,68,68,0.15);
  color: #FF4444;
}

.debug-agent-card__detail {
  margin-top: 4px;
}

/* ── Error cards ── */
.debug-error-card {
  padding: 5px 8px;
  border-bottom: 1px solid #151515;
  border-left: 3px solid #FF4444;
  cursor: pointer;
}

.debug-error-card:hover {
  background: #141414;
}

.debug-error-card__header {
  display: flex;
  gap: 6px;
  align-items: center;
}

.debug-error-card__class {
  color: #FF4444;
  font-weight: bold;
}

.debug-error-card__msg {
  color: #ccc;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.debug-error-card__detail {
  margin-top: 4px;
}

.debug-traceback {
  margin: 4px 0 0 0;
  font-size: 10px;
  color: #FF8888;
  background: #1a0000;
  padding: 6px;
  border-radius: 2px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 250px;
  overflow-y: auto;
}
</style>
