<template>
  <div class="replay-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROSHARK</div>
      </div>

      <div class="header-center">
        <div class="replay-badge">REPLAY</div>
      </div>

      <div class="header-right">
        <button class="back-btn" @click="goBack">← Back</button>
      </div>
    </header>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <div class="pulse-ring"></div>
      <span>Loading simulation data...</span>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      <span>{{ error }}</span>
      <button class="action-btn secondary" @click="router.push('/')">Home</button>
    </div>

    <!-- Main Replay -->
    <template v-else>
      <!-- Playback Controls -->
      <div class="playback-bar">
        <div class="playback-controls">
          <!-- Play/Pause -->
          <button class="control-btn play" @click="togglePlay">
            <svg v-if="!isPlaying" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <rect x="6" y="4" width="4" height="16"/>
              <rect x="14" y="4" width="4" height="16"/>
            </svg>
          </button>

          <!-- Speed -->
          <div class="speed-controls">
            <button
              v-for="s in speeds"
              :key="s"
              class="speed-btn"
              :class="{ active: speed === s }"
              @click="speed = s"
            >{{ s }}x</button>
          </div>

          <!-- Round Info -->
          <div class="round-display">
            <span class="round-label">ROUND</span>
            <span class="round-current">{{ currentRound }}</span>
            <span class="round-separator">/</span>
            <span class="round-total">{{ totalRounds }}</span>
          </div>
        </div>

        <!-- Scrubber -->
        <div class="scrubber-container">
          <input
            type="range"
            class="scrubber"
            :min="0"
            :max="totalRounds"
            :value="currentRound"
            @input="onScrub"
          />
          <div class="scrubber-progress" :style="{ width: progressPercent + '%' }"></div>
        </div>

        <!-- Stats -->
        <div class="playback-stats">
          <span class="stat-item">
            <span class="stat-label">EVENTS</span>
            <span class="stat-value">{{ visibleActions.length }}</span>
            <span class="stat-total">/ {{ allActions.length }}</span>
          </span>
          <span class="stat-divider"></span>
          <span class="stat-item">
            <svg class="platform-icon" viewBox="0 0 24 24" width="11" height="11" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
            <span class="stat-value">{{ visibleTwitterCount }}</span>
          </span>
          <span class="stat-divider"></span>
          <span class="stat-item">
            <span class="stat-label">Reddit</span>
            <span class="stat-value">{{ visibleRedditCount }}</span>
          </span>
        </div>
      </div>

      <!-- Timeline Feed -->
      <div class="main-content-area" ref="scrollContainer">
        <!-- Round Markers -->
        <div class="timeline-feed">
          <div class="timeline-axis"></div>

          <TransitionGroup name="replay-item">
            <div
              v-for="action in visibleActions"
              :key="action._uniqueId"
              class="timeline-item"
              :class="[action.platform, { 'new-round': action._isRoundStart }]"
            >
              <!-- Round Divider -->
              <div v-if="action._isRoundStart" class="round-divider">
                <span class="round-tag">ROUND {{ action.round_num }}</span>
              </div>

              <div class="timeline-marker">
                <div class="marker-dot"></div>
              </div>

              <div class="timeline-card">
                <div class="card-header">
                  <div class="agent-info">
                    <div class="avatar-placeholder">{{ (action.agent_name || 'A')[0] }}</div>
                    <span class="agent-name">{{ action.agent_name }}</span>
                  </div>

                  <div class="header-meta">
                    <div class="platform-indicator" :class="action.platform">
                      <svg v-if="action.platform === 'twitter'" viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                      <img v-else-if="action.platform === 'reddit'" src="/reddit.png" class="platform-logo" alt="Reddit" />
                    </div>
                    <div class="action-badge" :class="getActionTypeClass(action.action_type)">
                      {{ getActionTypeLabel(action.action_type) }}
                    </div>
                  </div>
                </div>

                <div class="card-body">
                  <!-- CREATE_POST -->
                  <div v-if="action.action_type === 'CREATE_POST' && action.action_args?.content" class="content-text main-text">
                    {{ action.action_args.content }}
                  </div>

                  <!-- QUOTE_POST -->
                  <template v-if="action.action_type === 'QUOTE_POST'">
                    <div v-if="action.action_args?.quote_content" class="content-text">
                      {{ action.action_args.quote_content }}
                    </div>
                    <div v-if="action.action_args?.original_content" class="quoted-block">
                      <div class="quote-label">@{{ action.action_args.original_author_name || 'User' }}</div>
                      <div class="quote-text">{{ truncate(action.action_args.original_content, 150) }}</div>
                    </div>
                  </template>

                  <!-- REPOST -->
                  <template v-if="action.action_type === 'REPOST'">
                    <div class="repost-info">Reposted @{{ action.action_args?.original_author_name || 'User' }}</div>
                    <div v-if="action.action_args?.original_content" class="repost-content">
                      {{ truncate(action.action_args.original_content, 200) }}
                    </div>
                  </template>

                  <!-- LIKE_POST -->
                  <template v-if="action.action_type === 'LIKE_POST'">
                    <div class="like-info">Liked @{{ action.action_args?.post_author_name || 'User' }}'s post</div>
                    <div v-if="action.action_args?.post_content" class="liked-content">
                      "{{ truncate(action.action_args.post_content, 120) }}"
                    </div>
                  </template>

                  <!-- CREATE_COMMENT -->
                  <template v-if="action.action_type === 'CREATE_COMMENT'">
                    <div v-if="action.action_args?.content" class="content-text">
                      {{ action.action_args.content }}
                    </div>
                    <div v-if="action.action_args?.post_id" class="comment-context">
                      Reply to post #{{ action.action_args.post_id }}
                    </div>
                  </template>

                  <!-- FOLLOW -->
                  <template v-if="action.action_type === 'FOLLOW'">
                    <div class="follow-info">Followed @{{ action.action_args?.target_user_name || action.action_args?.target_user || 'User' }}</div>
                  </template>

                  <!-- SEARCH_POSTS -->
                  <template v-if="action.action_type === 'SEARCH_POSTS'">
                    <div class="search-info">Search: <span class="search-query">"{{ action.action_args?.query || '' }}"</span></div>
                  </template>

                  <!-- DISLIKE_POST -->
                  <template v-if="action.action_type === 'DISLIKE_POST'">
                    <div class="like-info">Disliked @{{ action.action_args?.post_author_name || 'User' }}'s post</div>
                  </template>

                  <!-- BUY_SHARES -->
                  <template v-if="action.action_type === 'BUY_SHARES'">
                    <div class="trade-info">
                      <span class="trade-direction buy">BUY</span>
                      <span>{{ formatNum(action.action_args?.shares) }} <strong>{{ action.action_args?.outcome }}</strong> @ ${{ formatNum(action.action_args?.price) }}</span>
                    </div>
                  </template>

                  <!-- SELL_SHARES -->
                  <template v-if="action.action_type === 'SELL_SHARES'">
                    <div class="trade-info">
                      <span class="trade-direction sell">SELL</span>
                      <span>{{ formatNum(action.action_args?.shares) }} <strong>{{ action.action_args?.outcome }}</strong> → ${{ formatNum(action.action_args?.usd_received) }}</span>
                    </div>
                  </template>

                  <!-- CREATE_MARKET -->
                  <template v-if="action.action_type === 'CREATE_MARKET'">
                    <div class="market-question">"{{ action.action_args?.question }}"</div>
                  </template>

                  <!-- DO_NOTHING -->
                  <template v-if="action.action_type === 'DO_NOTHING'">
                    <div class="idle-info">Action Skipped</div>
                  </template>

                  <!-- Generic fallback -->
                  <div v-if="!knownTypes.includes(action.action_type) && action.action_args?.content" class="content-text">
                    {{ action.action_args.content }}
                  </div>
                </div>

                <div class="card-footer">
                  <span class="time-tag">R{{ action.round_num }} • {{ formatTime(action.timestamp) }}</span>
                </div>
              </div>
            </div>
          </TransitionGroup>

          <div v-if="allActions.length === 0" class="empty-state">
            <span>No simulation data found</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getRunStatusDetail } from '../api/simulation'

const route = useRoute()
const router = useRouter()

const simulationId = ref(route.params.simulationId)
const loading = ref(true)
const error = ref(null)

const allActions = ref([])
const totalRounds = ref(0)
const currentRound = ref(0)
const isPlaying = ref(false)
const speed = ref(1)
const speeds = [0.5, 1, 2, 5]
const scrollContainer = ref(null)

let playInterval = null

const knownTypes = [
  'CREATE_POST', 'QUOTE_POST', 'REPOST', 'LIKE_POST', 'DISLIKE_POST',
  'CREATE_COMMENT', 'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS',
  'FOLLOW', 'MUTE', 'UPVOTE_POST', 'DOWNVOTE_POST', 'DO_NOTHING',
  'BUY_SHARES', 'SELL_SHARES', 'CREATE_MARKET', 'BROWSE_MARKETS',
  'VIEW_PORTFOLIO', 'COMMENT_ON_MARKET'
]

// Visible actions up to current round
const visibleActions = computed(() => {
  return allActions.value.filter(a => a.round_num <= currentRound.value)
})

const visibleTwitterCount = computed(() => visibleActions.value.filter(a => a.platform === 'twitter').length)
const visibleRedditCount = computed(() => visibleActions.value.filter(a => a.platform === 'reddit').length)

const progressPercent = computed(() => {
  if (totalRounds.value === 0) return 0
  return (currentRound.value / totalRounds.value) * 100
})

// Load data
const loadData = async () => {
  loading.value = true
  error.value = null

  try {
    const detailRes = await getRunStatusDetail(simulationId.value)

    if (!detailRes.success || !detailRes.data) {
      error.value = 'Failed to load simulation data'
      return
    }

    const actions = detailRes.data.all_actions || []
    if (actions.length === 0) {
      error.value = 'No actions found for this simulation'
      return
    }

    // Sort by round then timestamp
    actions.sort((a, b) => {
      if (a.round_num !== b.round_num) return a.round_num - b.round_num
      return new Date(a.timestamp) - new Date(b.timestamp)
    })

    // Mark round starts
    let prevRound = -1
    actions.forEach((action, i) => {
      action._uniqueId = action.id || `${action.timestamp}-${action.platform}-${action.agent_id}-${action.action_type}-${i}`
      if (action.round_num !== prevRound) {
        action._isRoundStart = true
        prevRound = action.round_num
      }
    })

    allActions.value = actions

    // Get total rounds
    const maxRound = actions.length > 0 ? Math.max(...actions.map(a => a.round_num)) : 0
    totalRounds.value = detailRes.data.total_rounds || maxRound
    currentRound.value = 0
  } catch (err) {
    error.value = `Error: ${err.message}`
  } finally {
    loading.value = false
  }
}

// Playback
const togglePlay = () => {
  if (isPlaying.value) {
    pause()
  } else {
    play()
  }
}

const play = () => {
  if (currentRound.value >= totalRounds.value) {
    currentRound.value = 0
  }
  isPlaying.value = true
  startPlayback()
}

const pause = () => {
  isPlaying.value = false
  stopPlayback()
}

const startPlayback = () => {
  stopPlayback()
  const interval = Math.max(100, 1000 / speed.value)
  playInterval = setInterval(() => {
    if (currentRound.value >= totalRounds.value) {
      pause()
      return
    }
    currentRound.value++
  }, interval)
}

const stopPlayback = () => {
  if (playInterval) {
    clearInterval(playInterval)
    playInterval = null
  }
}

const onScrub = (e) => {
  const val = parseInt(e.target.value)
  currentRound.value = val
  if (isPlaying.value) {
    stopPlayback()
    startPlayback()
  }
}

// Restart playback when speed changes
watch(speed, () => {
  if (isPlaying.value) {
    stopPlayback()
    startPlayback()
  }
})

// Auto-scroll on round change
watch(currentRound, () => {
  nextTick(() => {
    const el = scrollContainer.value
    if (el && isPlaying.value) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  })
})

const goBack = () => {
  router.back()
}

// Helpers
const getActionTypeLabel = (type) => {
  const labels = {
    'CREATE_POST': 'POST', 'REPOST': 'REPOST', 'LIKE_POST': 'LIKE',
    'CREATE_COMMENT': 'COMMENT', 'LIKE_COMMENT': 'LIKE', 'DISLIKE_POST': 'DISLIKE',
    'DISLIKE_COMMENT': 'DISLIKE', 'MUTE': 'MUTE', 'DO_NOTHING': 'IDLE',
    'FOLLOW': 'FOLLOW', 'SEARCH_POSTS': 'SEARCH', 'QUOTE_POST': 'QUOTE',
    'UPVOTE_POST': 'UPVOTE', 'DOWNVOTE_POST': 'DOWNVOTE',
    'BUY_SHARES': 'BUY', 'SELL_SHARES': 'SELL', 'CREATE_MARKET': 'NEW MARKET',
    'BROWSE_MARKETS': 'BROWSE', 'VIEW_PORTFOLIO': 'PORTFOLIO', 'COMMENT_ON_MARKET': 'COMMENT',
  }
  return labels[type] || type || 'UNKNOWN'
}

const getActionTypeClass = (type) => {
  const classes = {
    'CREATE_POST': 'badge-post', 'REPOST': 'badge-action', 'LIKE_POST': 'badge-action',
    'CREATE_COMMENT': 'badge-comment', 'LIKE_COMMENT': 'badge-action', 'QUOTE_POST': 'badge-post',
    'FOLLOW': 'badge-meta', 'SEARCH_POSTS': 'badge-meta', 'UPVOTE_POST': 'badge-action',
    'DOWNVOTE_POST': 'badge-action', 'DISLIKE_POST': 'badge-action', 'DISLIKE_COMMENT': 'badge-action',
    'MUTE': 'badge-meta', 'DO_NOTHING': 'badge-idle',
    'BUY_SHARES': 'badge-trade-buy', 'SELL_SHARES': 'badge-trade-sell',
    'CREATE_MARKET': 'badge-post', 'BROWSE_MARKETS': 'badge-meta',
    'VIEW_PORTFOLIO': 'badge-meta', 'COMMENT_ON_MARKET': 'badge-comment',
  }
  return classes[type] || 'badge-default'
}

const truncate = (content, max = 100) => {
  if (!content) return ''
  return content.length > max ? content.substring(0, max) + '...' : content
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return '' }
}

const formatNum = (n) => {
  if (n == null) return '?'
  return Number(n).toFixed(1)
}

onMounted(() => {
  loadData()
})

onUnmounted(() => {
  stopPlayback()
})
</script>

<style scoped>
.replay-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #FAFAFA;
  overflow: hidden;
  font-family: var(--font-display);
}

/* Header */
.app-header {
  height: 60px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  background: #0A0A0A;
  z-index: 100;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.replay-badge {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 4px;
  color: #FF6B1A;
  background: rgba(255,107,26,0.1);
  padding: 4px 16px;
  border: 1px solid rgba(255,107,26,0.3);
}

.brand {
  font-family: var(--font-mono);
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 3px;
  text-transform: uppercase;
  cursor: pointer;
  color: #FAFAFA;
}

.back-btn {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: rgba(250,250,250,0.5);
  background: none;
  border: 1px solid rgba(250,250,250,0.2);
  padding: 5px 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.back-btn:hover {
  color: #FAFAFA;
  border-color: rgba(250,250,250,0.4);
}

/* Loading / Error */
.loading-state, .error-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 16px;
  color: rgba(10,10,10,0.3);
  font-family: var(--font-mono);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.pulse-ring {
  width: 32px;
  height: 32px;
  border: 2px solid #FF6B1A;
  animation: ripple 2s infinite;
}

@keyframes ripple {
  0% { transform: scale(0.8); opacity: 1; }
  100% { transform: scale(2.5); opacity: 0; }
}

/* Playback Bar */
.playback-bar {
  background: #0A0A0A;
  padding: 12px 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
  z-index: 10;
}

.playback-controls {
  display: flex;
  align-items: center;
  gap: 16px;
}

.control-btn.play {
  width: 36px;
  height: 36px;
  background: #FF6B1A;
  color: #FAFAFA;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
  flex-shrink: 0;
}

.control-btn.play:hover {
  background: #E05A10;
}

.speed-controls {
  display: flex;
  gap: 4px;
}

.speed-btn {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  padding: 4px 10px;
  border: 1px solid rgba(250,250,250,0.15);
  background: transparent;
  color: rgba(250,250,250,0.4);
  cursor: pointer;
  transition: all 0.2s;
}

.speed-btn.active {
  background: rgba(255,107,26,0.15);
  color: #FF6B1A;
  border-color: rgba(255,107,26,0.4);
}

.speed-btn:hover:not(.active) {
  border-color: rgba(250,250,250,0.3);
  color: rgba(250,250,250,0.6);
}

.round-display {
  font-family: var(--font-mono);
  font-size: 14px;
  color: rgba(250,250,250,0.6);
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-left: auto;
}

.round-label {
  font-size: 9px;
  letter-spacing: 3px;
  color: rgba(250,250,250,0.3);
  margin-right: 6px;
}

.round-current {
  font-size: 20px;
  font-weight: 700;
  color: #FF6B1A;
}

.round-separator {
  color: rgba(250,250,250,0.2);
}

.round-total {
  color: rgba(250,250,250,0.4);
}

/* Scrubber */
.scrubber-container {
  position: relative;
  height: 6px;
  background: rgba(250,250,250,0.1);
}

.scrubber {
  position: absolute;
  width: 100%;
  height: 100%;
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  cursor: pointer;
  z-index: 2;
  margin: 0;
}

.scrubber::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  background: #FF6B1A;
  border: none;
  cursor: pointer;
  margin-top: -4px;
}

.scrubber::-moz-range-thumb {
  width: 14px;
  height: 14px;
  background: #FF6B1A;
  border: none;
  cursor: pointer;
}

.scrubber::-webkit-slider-runnable-track {
  height: 6px;
  background: transparent;
}

.scrubber::-moz-range-track {
  height: 6px;
  background: transparent;
}

.scrubber-progress {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: #FF6B1A;
  pointer-events: none;
  z-index: 1;
  transition: width 0.1s linear;
}

/* Stats */
.playback-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(250,250,250,0.4);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-label {
  font-size: 8px;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.stat-value {
  color: rgba(250,250,250,0.7);
  font-weight: 600;
}

.stat-total {
  color: rgba(250,250,250,0.3);
}

.stat-divider {
  width: 1px;
  height: 12px;
  background: rgba(250,250,250,0.1);
}

.platform-icon {
  color: rgba(250,250,250,0.5);
}

/* Main Content */
.main-content-area {
  flex: 1;
  overflow-y: auto;
  background: #FAFAFA;
}

/* Timeline (reused from Step3) */
.timeline-feed {
  padding: 22px 0;
  position: relative;
  min-height: 100%;
  max-width: 900px;
  margin: 0 auto;
}

.timeline-axis {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(10,10,10,0.08);
  transform: translateX(-50%);
}

.timeline-item {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 34px;
  position: relative;
  width: 100%;
}

.round-divider {
  position: absolute;
  left: 50%;
  top: -20px;
  transform: translateX(-50%);
  z-index: 3;
}

.round-tag {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 3px;
  color: #FF6B1A;
  background: rgba(255,107,26,0.08);
  border: 1px solid rgba(255,107,26,0.2);
  padding: 2px 10px;
  text-transform: uppercase;
}

.timeline-marker {
  position: absolute;
  left: 50%;
  top: 24px;
  width: 10px;
  height: 10px;
  background: #FAFAFA;
  border: 1px solid rgba(10,10,10,0.2);
  transform: translateX(-50%);
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
}

.marker-dot {
  width: 4px;
  height: 4px;
  background: rgba(10,10,10,0.2);
}

.timeline-item.twitter .marker-dot { background: #0A0A0A; }
.timeline-item.reddit .marker-dot { background: #FF6B1A; }
.timeline-item.twitter .timeline-marker { border-color: #0A0A0A; }
.timeline-item.reddit .timeline-marker { border-color: #FF6B1A; }

.timeline-card {
  width: calc(100% - 48px);
  margin-left: 32px;
  background: #FAFAFA;
  padding: 16px 20px;
  border: 2px solid rgba(10,10,10,0.08);
  position: relative;
  transition: all 0.2s;
}

.timeline-card:hover { border-color: #FF6B1A; }
.timeline-item.twitter .timeline-card { border-left: 2px solid #0A0A0A; }
.timeline-item.reddit .timeline-card { border-left: 2px solid #FF6B1A; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 11px;
  padding-bottom: 11px;
  border-bottom: 1px solid rgba(10,10,10,0.08);
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 11px;
}

.avatar-placeholder {
  width: 24px;
  height: 24px;
  min-width: 24px;
  background: #0A0A0A;
  color: #FAFAFA;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.agent-name {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: #0A0A0A;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.platform-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
}

.platform-indicator.twitter { background: #0A0A0A; color: #FAFAFA; }
.platform-logo { width: 20px; height: 20px; object-fit: contain; }

.action-badge {
  font-family: var(--font-mono);
  font-size: 9px;
  padding: 2px 6px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  border: 1px solid transparent;
}

.badge-post { background: rgba(10,10,10,0.06); color: rgba(10,10,10,0.7); border-color: rgba(10,10,10,0.12); }
.badge-comment { background: rgba(10,10,10,0.06); color: rgba(10,10,10,0.5); border-color: rgba(10,10,10,0.12); }
.badge-action { background: #FAFAFA; color: rgba(10,10,10,0.5); border: 1px solid rgba(10,10,10,0.12); }
.badge-meta { background: #FAFAFA; color: rgba(10,10,10,0.4); border: 1px dashed rgba(10,10,10,0.2); }
.badge-idle { opacity: 0.5; }
.badge-trade-buy { background: rgba(67,193,101,0.1); color: #43C165; border-color: rgba(67,193,101,0.2); }
.badge-trade-sell { background: rgba(255,68,68,0.1); color: #FF4444; border-color: rgba(255,68,68,0.2); }

.content-text {
  font-size: 13px;
  line-height: 1.6;
  color: rgba(10,10,10,0.7);
  margin-bottom: 11px;
}

.content-text.main-text { font-size: 14px; color: #0A0A0A; }

.quoted-block, .repost-content {
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  padding: 11px 12px;
  margin-top: 8px;
  font-size: 12px;
  color: rgba(10,10,10,0.5);
}

.quote-label { font-size: 11px; color: rgba(10,10,10,0.4); margin-bottom: 4px; }

.repost-info, .like-info, .search-info, .follow-info, .idle-info, .comment-context {
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  margin-bottom: 6px;
}

.liked-content {
  font-size: 12px;
  color: rgba(10,10,10,0.4);
  font-style: italic;
}

.search-query {
  font-family: var(--font-mono);
  background: rgba(10,10,10,0.06);
  padding: 0 4px;
}

.trade-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgba(10,10,10,0.7);
}

.trade-direction {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  letter-spacing: 3px;
}
.trade-direction.buy { background: rgba(67,193,101,0.1); color: #43C165; }
.trade-direction.sell { background: rgba(255,68,68,0.1); color: #FF4444; }

.market-question {
  font-size: 12px;
  color: rgba(10,10,10,0.7);
  font-style: italic;
}

.card-footer {
  margin-top: 11px;
  display: flex;
  justify-content: flex-end;
  font-size: 10px;
  color: rgba(10,10,10,0.2);
  font-family: var(--font-mono);
}

/* Animations */
.replay-item-enter-active {
  transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
}

.replay-item-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.replay-item-leave-active {
  transition: all 0.2s ease;
}

.replay-item-leave-to {
  opacity: 0;
}

.action-btn.secondary {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  padding: 5px 12px;
  border: 2px solid rgba(10,10,10,0.12);
  background: #FAFAFA;
  color: rgba(10,10,10,0.7);
  cursor: pointer;
}
</style>
