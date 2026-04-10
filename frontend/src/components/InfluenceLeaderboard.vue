<template>
  <div class="influence-leaderboard">
    <!-- Header -->
    <div class="lb-header">
      <div class="lb-title">
        <span class="lb-icon">◈</span>
        <span class="lb-label">AGENT INFLUENCE LEADERBOARD</span>
      </div>
      <button
        class="export-btn"
        :disabled="!agents.length"
        @click="exportReport"
        title="Download influence report as JSON"
      >
        Export JSON ↓
      </button>
    </div>

    <!-- Score legend -->
    <div class="lb-legend">
      <span class="legend-item"><span class="legend-dot engage"></span>Engagement ×3</span>
      <span class="legend-item"><span class="legend-dot follow"></span>Follows ×2</span>
      <span class="legend-item"><span class="legend-dot platform"></span>Platforms ×5</span>
      <span class="legend-item"><span class="legend-dot post"></span>Posts ×1</span>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="lb-loading">
      <div class="pulse-ring"></div>
      <span>Computing influence scores...</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="lb-error">{{ error }}</div>

    <!-- Empty -->
    <div v-else-if="!agents.length" class="lb-empty">
      No simulation data available yet. Run the simulation first.
    </div>

    <!-- Leaderboard rows -->
    <div v-else class="lb-list">
      <div
        v-for="agent in agents"
        :key="agent.agent_name"
        class="lb-row"
        :class="{ 'top-three': agent.rank <= 3 }"
      >
        <!-- Rank -->
        <div class="lb-rank" :class="'rank-' + Math.min(agent.rank, 4)">
          {{ String(agent.rank).padStart(2, '0') }}
        </div>

        <!-- Agent identity -->
        <div class="lb-identity">
          <div class="lb-avatar">{{ agent.agent_name[0].toUpperCase() }}</div>
          <div class="lb-info">
            <div class="lb-name">{{ agent.agent_name }}</div>
            <div class="lb-platforms">
              <span v-if="agent.platforms.includes('twitter')" class="platform-pill twitter">X</span>
              <span v-if="agent.platforms.includes('reddit')" class="platform-pill reddit">Reddit</span>
            </div>
          </div>
        </div>

        <!-- Score breakdown -->
        <div class="lb-breakdown">
          <div class="bd-item" title="Engagement received (likes, reposts, quotes)">
            <span class="bd-label engage">ENG</span>
            <span class="bd-value">{{ agent.engagement_received }}</span>
          </div>
          <div class="bd-item" title="Follows received">
            <span class="bd-label follow">FOL</span>
            <span class="bd-value">{{ agent.follows_received }}</span>
          </div>
          <div class="bd-item" title="Original posts created">
            <span class="bd-label post">PST</span>
            <span class="bd-value">{{ agent.posts_created }}</span>
          </div>
        </div>

        <!-- Score bar + value -->
        <div class="lb-score">
          <span class="score-num">{{ agent.influence_score }}</span>
          <div class="score-bar-track">
            <div
              class="score-bar-fill"
              :style="{ width: scoreBarPct(agent.influence_score) + '%' }"
            ></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div v-if="totalAgents > agents.length" class="lb-footer">
      Showing top {{ agents.length }} of {{ totalAgents }} agents
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getInfluenceLeaderboard } from '../api/simulation'

const props = defineProps({
  simulationId: { type: String, required: true },
  visible: { type: Boolean, default: false }
})

const loading = ref(false)
const error = ref('')
const agents = ref([])
const totalAgents = ref(0)

const maxScore = computed(() =>
  agents.value.length ? agents.value[0].influence_score : 1
)

const scoreBarPct = (score) => {
  const max = maxScore.value || 1
  return Math.round((score / max) * 100)
}

const load = async () => {
  if (!props.simulationId) return
  loading.value = true
  error.value = ''
  try {
    const res = await getInfluenceLeaderboard(props.simulationId)
    if (res.data?.success) {
      agents.value = res.data.data.agents || []
      totalAgents.value = res.data.data.total_agents || 0
    } else {
      error.value = res.data?.error || 'Failed to load influence data.'
    }
  } catch (err) {
    error.value = err.message || 'Failed to load influence data.'
  } finally {
    loading.value = false
  }
}

const exportReport = () => {
  const payload = {
    simulation_id: props.simulationId,
    generated_at: new Date().toISOString(),
    agents: agents.value,
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `influence-report-${props.simulationId}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// Load when becoming visible or when simulationId changes
watch(() => props.visible, (val) => { if (val) load() })
watch(() => props.simulationId, () => { if (props.visible) load() })
onMounted(() => { if (props.visible) load() })
</script>

<style scoped>
/* ── Container ── */
.influence-leaderboard {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  font-family: var(--font-mono);
  background: var(--background);
}

/* ── Header ── */
.lb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.08);
  flex-shrink: 0;
}

.lb-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lb-icon {
  color: var(--color-green);
  font-size: 14px;
}

.lb-label {
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.5);
}

.export-btn {
  background: none;
  border: 1px solid rgba(10,10,10,0.15);
  padding: 4px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 1px;
  cursor: pointer;
  color: rgba(10,10,10,0.5);
  transition: all 0.15s ease;
}

.export-btn:hover:not(:disabled) {
  border-color: var(--color-orange);
  color: var(--color-orange);
}

.export-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ── Legend ── */
.lb-legend {
  display: flex;
  gap: 16px;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.05);
  flex-shrink: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 1px;
}

.legend-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.legend-dot.engage { background: var(--color-orange); }
.legend-dot.follow { background: var(--color-green); }
.legend-dot.platform { background: #8b5cf6; }
.legend-dot.post { background: rgba(10,10,10,0.3); }

/* ── States ── */
.lb-loading,
.lb-empty,
.lb-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 12px;
  padding: 40px;
  font-size: 13px;
  color: rgba(10,10,10,0.35);
  letter-spacing: 1px;
}

.lb-error { color: var(--color-red, #e53e3e); }

.pulse-ring {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-orange);
  border-radius: 50%;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.4); opacity: 0.4; }
}

/* ── List ── */
.lb-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.lb-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.04);
  transition: background 0.1s ease;
}

.lb-row:hover {
  background: rgba(10,10,10,0.02);
}

.lb-row.top-three {
  border-left: 3px solid var(--color-orange);
}

/* ── Rank ── */
.lb-rank {
  width: 28px;
  font-size: 13px;
  font-weight: 700;
  color: rgba(10,10,10,0.2);
  flex-shrink: 0;
  text-align: right;
}

.lb-rank.rank-1 { color: #f59e0b; }
.lb-rank.rank-2 { color: rgba(10,10,10,0.5); }
.lb-rank.rank-3 { color: #b45309; }

/* ── Identity ── */
.lb-identity {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.lb-avatar {
  width: 28px;
  height: 28px;
  background: rgba(10,10,10,0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: rgba(10,10,10,0.4);
  flex-shrink: 0;
}

.lb-info {
  min-width: 0;
}

.lb-name {
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--foreground);
  margin-bottom: 3px;
}

.lb-platforms {
  display: flex;
  gap: 4px;
}

.platform-pill {
  font-size: 9px;
  padding: 1px 5px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.platform-pill.twitter { background: rgba(10,10,10,0.07); color: rgba(10,10,10,0.5); }
.platform-pill.reddit { background: rgba(255,69,0,0.1); color: #c44b00; }

/* ── Breakdown ── */
.lb-breakdown {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.bd-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  min-width: 32px;
}

.bd-label {
  font-size: 9px;
  letter-spacing: 1px;
  opacity: 0.5;
}

.bd-label.engage { color: var(--color-orange); }
.bd-label.follow { color: var(--color-green); }
.bd-label.post   { color: rgba(10,10,10,0.5); }

.bd-value {
  font-size: 13px;
  font-weight: 700;
  color: var(--foreground);
}

/* ── Score ── */
.lb-score {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
  min-width: 60px;
}

.score-num {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-orange);
}

.score-bar-track {
  width: 60px;
  height: 3px;
  background: rgba(10,10,10,0.08);
}

.score-bar-fill {
  height: 100%;
  background: var(--color-orange);
  transition: width 0.4s ease;
}

/* ── Footer ── */
.lb-footer {
  padding: 8px 16px;
  font-size: 11px;
  color: rgba(10,10,10,0.3);
  letter-spacing: 1px;
  text-align: center;
  border-top: 1px solid rgba(10,10,10,0.05);
  flex-shrink: 0;
}
</style>
