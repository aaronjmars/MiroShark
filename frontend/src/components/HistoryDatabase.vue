<template>
  <div
    v-if="projects.length > 0 || loading"
    class="history-database"
    ref="historyContainer"
  >
    <!-- Background decoration: tech grid lines (only shown when projects exist) -->
    <div v-if="projects.length > 0 || loading" class="tech-grid-bg">
      <div class="grid-pattern"></div>
      <div class="gradient-overlay"></div>
    </div>

    <!-- Track Record Summary (shown when any simulation has been resolved) -->
    <div v-if="trackRecord" class="track-record-bar">
      <span class="track-record-label">Track Record</span>
      <span class="track-record-stat">{{ trackRecord.total }} resolved</span>
      <span v-if="trackRecord.overallAccuracy !== null" class="track-record-accuracy" :class="trackRecord.overallAccuracy >= 60 ? 'good' : 'poor'">
        {{ trackRecord.overallAccuracy }}% accurate
      </span>
      <span v-if="trackRecord.correct > 0" class="track-record-correct">{{ trackRecord.correct }} correct</span>
    </div>

    <!-- Title Area -->
    <div class="section-header">
      <div class="section-line"></div>
      <span class="section-title">Simulation Records</span>
      <div class="section-line"></div>
      <button
        v-if="projects.length >= 2"
        class="compare-mode-btn"
        :class="{ active: compareMode }"
        @click="toggleCompareMode"
      >{{ compareMode ? (compareSelections.length === 2 ? 'Compare →' : `${compareSelections.length}/2 selected`) : '⇄ Compare' }}</button>
    </div>

    <!-- Cards container (only shown when projects exist) -->
    <div v-if="projects.length > 0" class="cards-container" :class="{ expanded: isExpanded }" :style="containerStyle">
      <div
        v-for="(project, index) in projects"
        :key="project.simulation_id"
        class="project-card"
        :class="{ expanded: isExpanded, hovering: hoveringCard === index }"
        :style="getCardStyle(index)"
        @mouseenter="hoveringCard = index"
        @mouseleave="hoveringCard = null"
        @click="navigateToProject(project)"
      >
        <!-- Card header: simulation_id and feature availability -->
        <div class="card-header">
          <span class="card-id">{{ formatSimulationId(project.simulation_id) }}</span>
          <div class="card-status-icons">
            <span
              v-if="project.parent_simulation_id"
              class="fork-badge"
              :title="`Forked from ${formatSimulationId(project.parent_simulation_id)}`"
            >⑂</span>
            <span
              v-if="project.resolution"
              class="resolution-badge"
              :class="project.resolution.accuracy_score >= 1.0 ? 'correct' : project.resolution.accuracy_score <= 0.0 && project.resolution.accuracy_score !== null ? 'wrong' : 'neutral'"
              :title="getResolutionLabel(project)?.text"
            >{{ project.resolution.accuracy_score >= 1.0 ? '✓' : project.resolution.accuracy_score <= 0.0 && project.resolution.accuracy_score !== null ? '✗' : '○' }}</span>
            <span
              v-else-if="project.status === 'completed'"
              class="resolution-badge pending"
              title="Awaiting outcome resolution"
            >⏳</span>
            <span
              class="status-icon"
              :class="{ available: project.project_id, unavailable: !project.project_id }"
              title="Graph Build"
            >◇</span>
            <span
              class="status-icon available"
              title="Agent Setup"
            >◈</span>
            <span
              class="status-icon"
              :class="{ available: project.report_id, unavailable: !project.report_id }"
              title="Analysis Report"
            >◆</span>
          </div>
        </div>

        <!-- File List Area -->
        <div class="card-files-wrapper">
          <!-- Corner decoration - viewfinder style -->
          <div class="corner-mark top-left-only"></div>

          <!-- File List -->
          <div class="files-list" v-if="project.files && project.files.length > 0">
            <div
              v-for="(file, fileIndex) in project.files.slice(0, 3)"
              :key="fileIndex"
              class="file-item"
            >
              <span class="file-tag" :class="getFileType(file.filename)">{{ getFileTypeLabel(file.filename) }}</span>
              <span class="file-name">{{ truncateFilename(file.filename, 20) }}</span>
            </div>
            <!-- Show hint if more files exist -->
            <div v-if="project.files.length > 3" class="files-more">
              +{{ project.files.length - 3 }} files
            </div>
          </div>
          <!-- Placeholder when no files -->
          <div class="files-empty" v-else>
            <span class="empty-file-icon">◇</span>
            <span class="empty-file-text">No files</span>
          </div>
        </div>

        <!-- Card title (first 20 chars of simulation requirement) -->
        <h3 class="card-title">{{ getSimulationTitle(project.simulation_requirement) }}</h3>

        <!-- Card description (full simulation requirement) -->
        <p class="card-desc">{{ truncateText(project.simulation_requirement, 55) }}</p>

        <!-- Card Footer -->
        <div class="card-footer">
          <div class="card-datetime">
            <span class="card-date">{{ formatDate(project.created_at) }}</span>
            <span class="card-time">{{ formatTime(project.created_at) }}</span>
          </div>
          <div class="card-progress-row">
            <span class="card-progress" :class="getProgressClass(project)">
              <span class="status-dot">●</span> {{ formatRounds(project) }}
            </span>
            <button
              v-if="compareMode"
              class="compare-select-btn"
              :class="{ selected: compareSelections.includes(project.simulation_id) }"
              @click.stop="toggleCompareSelection(project.simulation_id)"
            >{{ compareSelections.includes(project.simulation_id) ? '✓' : '+' }}</button>
          </div>
        </div>

        <!-- Bottom decoration line (expands on hover) -->
        <div class="card-bottom-line"></div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <span class="loading-spinner"></span>
      <span class="loading-text">Loading...</span>
    </div>

    <!-- History Replay Detail Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="selectedProject" class="modal-overlay" @click.self="closeModal">
          <div class="modal-content">
            <!-- Modal Header -->
            <div class="modal-header">
              <div class="modal-title-section">
                <span class="modal-id">{{ formatSimulationId(selectedProject.simulation_id) }}</span>
                <span class="modal-progress" :class="getProgressClass(selectedProject)">
                  <span class="status-dot">●</span> {{ formatRounds(selectedProject) }}
                </span>
                <span class="modal-create-time">{{ formatDate(selectedProject.created_at) }} {{ formatTime(selectedProject.created_at) }}</span>
              </div>
              <button class="modal-close" @click="closeModal">×</button>
            </div>

            <!-- Modal Content -->
            <div class="modal-body">
              <!-- Simulation Requirement -->
              <div class="modal-section">
                <div class="modal-label">Simulation Requirement</div>
                <div class="modal-requirement">{{ selectedProject.simulation_requirement || 'None' }}</div>
              </div>

              <!-- File List -->
              <div class="modal-section">
                <div class="modal-label">Associated Files</div>
                <div class="modal-files" v-if="selectedProject.files && selectedProject.files.length > 0">
                  <div v-for="(file, index) in selectedProject.files" :key="index" class="modal-file-item">
                    <span class="file-tag" :class="getFileType(file.filename)">{{ getFileTypeLabel(file.filename) }}</span>
                    <span class="modal-file-name">{{ file.filename }}</span>
                  </div>
                </div>
                <div class="modal-empty" v-else>No associated files</div>
              </div>
            </div>

            <!-- Simulation Replay Divider -->
            <div class="modal-divider">
              <span class="divider-line"></span>
              <span class="divider-text">Simulation Replay</span>
              <span class="divider-line"></span>
            </div>

            <!-- Navigation Buttons -->
            <div class="modal-actions">
              <button
                class="modal-btn btn-project"
                @click="goToProject"
                :disabled="!selectedProject.project_id"
              >
                <span class="btn-step">Step1</span>
                <span class="btn-icon">◇</span>
                <span class="btn-text">Graph Build</span>
              </button>
              <button
                class="modal-btn btn-simulation"
                @click="goToSimulation"
              >
                <span class="btn-step">Step2</span>
                <span class="btn-icon">◈</span>
                <span class="btn-text">Agent Setup</span>
              </button>
              <button
                class="modal-btn btn-simrun"
                @click="goToSimulationRun"
              >
                <span class="btn-step">Step3</span>
                <span class="btn-icon">◆</span>
                <span class="btn-text">Simulation Run</span>
              </button>
              <button
                class="modal-btn btn-replay"
                @click="goToReplay"
                :disabled="!(selectedProject.current_round > 0)"
              >
                <span class="btn-step">▶</span>
                <span class="btn-icon">◈</span>
                <span class="btn-text">Replay</span>
              </button>
              <button
                class="modal-btn btn-report"
                @click="goToReport"
                :disabled="!selectedProject.report_id"
              >
                <span class="btn-step">Step4</span>
                <span class="btn-icon">◆</span>
                <span class="btn-text">Analysis Report</span>
              </button>
              <button
                class="modal-btn btn-interaction"
                @click="goToInteraction"
                :disabled="!selectedProject.report_id"
              >
                <span class="btn-step">Step5</span>
                <span class="btn-icon">◈</span>
                <span class="btn-text">Deep Interaction</span>
              </button>
            </div>
            <!-- Non-replayable Hint -->
            <div class="modal-playback-hint">
              <span class="hint-text">Select a step to replay from the simulation history</span>
            </div>

            <!-- Resolve Prediction Section (completed simulations only) -->
            <div v-if="selectedProject.status === 'completed' || selectedProject.current_round > 0" class="modal-resolve-section">
              <div class="modal-divider">
                <span class="divider-line"></span>
                <span class="divider-text">Prediction Outcome</span>
                <span class="divider-line"></span>
              </div>

              <!-- Already resolved: show result -->
              <div v-if="selectedProject.resolution && !showResolvePanel" class="resolve-result">
                <div class="resolve-result-row">
                  <span class="resolve-label">Actual Outcome</span>
                  <span class="resolve-value outcome-badge" :class="selectedProject.resolution.actual_outcome === 'YES' ? 'yes' : 'no'">
                    {{ selectedProject.resolution.actual_outcome }}
                  </span>
                </div>
                <div v-if="selectedProject.resolution.predicted_consensus" class="resolve-result-row">
                  <span class="resolve-label">Agent Consensus</span>
                  <span class="resolve-value outcome-badge" :class="selectedProject.resolution.predicted_consensus === 'YES' ? 'yes' : 'no'">
                    {{ selectedProject.resolution.predicted_consensus }}
                    <span class="resolve-confidence">{{ Math.round(selectedProject.resolution.predicted_confidence * 100) }}%</span>
                  </span>
                </div>
                <div v-if="selectedProject.resolution.accuracy_score !== null" class="resolve-result-row">
                  <span class="resolve-label">Accuracy</span>
                  <span class="resolve-value accuracy-value"
                    :class="selectedProject.resolution.accuracy_score >= 1.0 ? 'correct' : selectedProject.resolution.accuracy_score <= 0.0 ? 'wrong' : 'split'">
                    {{ selectedProject.resolution.accuracy_score >= 1.0 ? '✓ Correct' : selectedProject.resolution.accuracy_score <= 0.0 ? '✗ Incorrect' : '~ Split' }}
                  </span>
                </div>
                <div v-if="selectedProject.resolution.notes" class="resolve-notes">{{ selectedProject.resolution.notes }}</div>
                <button class="resolve-reopen-btn" @click="openResolvePanel">Re-resolve</button>
              </div>

              <!-- Not yet resolved or re-resolving -->
              <div v-else-if="!showResolvePanel" class="resolve-intro">
                <p class="resolve-desc">Did the simulation correctly predict what happened? Record the real-world outcome to build your accuracy track record.</p>
                <button class="resolve-trigger-btn" @click="openResolvePanel">Record Outcome</button>
              </div>

              <div v-if="showResolvePanel" class="resolve-form">
                <p class="resolve-form-label">What actually happened?</p>
                <div v-if="resolveError" class="resolve-error">{{ resolveError }}</div>
                <div class="resolve-buttons">
                  <button class="resolve-outcome-btn yes" :disabled="resolving" @click="executeResolve('YES')">
                    <span v-if="resolving" class="loading-spinner-small"></span>
                    YES — It happened
                  </button>
                  <button class="resolve-outcome-btn no" :disabled="resolving" @click="executeResolve('NO')">
                    <span v-if="resolving" class="loading-spinner-small"></span>
                    NO — It didn't happen
                  </button>
                </div>
                <button class="resolve-cancel-btn" @click="closeResolvePanel" :disabled="resolving">Cancel</button>
              </div>
            </div>

            <!-- Fork Section -->
            <div class="modal-fork-section">
              <div class="modal-divider">
                <span class="divider-line"></span>
                <span class="divider-text">Fork</span>
                <span class="divider-line"></span>
              </div>

              <div v-if="!showForkPanel" class="fork-intro">
                <p class="fork-desc">Clone this simulation with a new scenario — agent profiles are reused instantly.</p>
                <button class="fork-trigger-btn" @click="openForkPanel">⑂ Fork Simulation</button>
                <div v-if="selectedProject.parent_simulation_id" class="fork-lineage-badge">
                  ⑂ Forked from <span class="fork-parent-id">{{ formatSimulationId(selectedProject.parent_simulation_id) }}</span>
                </div>
              </div>

              <div v-else class="fork-form">
                <label class="fork-label">Scenario (edit to explore a variant)</label>
                <textarea
                  v-model="forkRequirement"
                  class="fork-textarea"
                  placeholder="Describe the scenario you want to simulate..."
                  rows="3"
                ></textarea>
                <p class="fork-note">Agent profiles will be copied from the parent simulation — no re-preparation needed.</p>
                <div v-if="forkError" class="fork-error">{{ forkError }}</div>
                <div class="fork-actions">
                  <button class="fork-cancel-btn" @click="closeForkPanel" :disabled="forking">Cancel</button>
                  <button class="fork-submit-btn" @click="executeFork" :disabled="forking">
                    {{ forking ? 'Forking...' : '⑂ Fork & Open' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, onActivated, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getSimulationHistory, forkSimulation, resolveSimulation } from '../api/simulation'

const router = useRouter()
const route = useRoute()

// State
const projects = ref([])
const loading = ref(true)
const isExpanded = ref(false)
const hoveringCard = ref(null)
const historyContainer = ref(null)
const selectedProject = ref(null)  // Currently selected project (for modal)
let observer = null

// Compare mode
const compareMode = ref(false)
const compareSelections = ref([])

// Fork mode
const showForkPanel = ref(false)
const forkRequirement = ref('')
const forking = ref(false)
const forkError = ref('')

// Resolve mode
const showResolvePanel = ref(false)
const resolving = ref(false)
const resolveError = ref('')

const toggleCompareMode = () => {
  if (compareMode.value && compareSelections.value.length === 2) {
    // Navigate to comparison view
    router.push({
      name: 'Compare',
      params: { id1: compareSelections.value[0], id2: compareSelections.value[1] }
    })
    compareMode.value = false
    compareSelections.value = []
    return
  }
  compareMode.value = !compareMode.value
  compareSelections.value = []
}

const toggleCompareSelection = (simId) => {
  const idx = compareSelections.value.indexOf(simId)
  if (idx >= 0) {
    compareSelections.value.splice(idx, 1)
  } else if (compareSelections.value.length < 2) {
    compareSelections.value.push(simId)
  }
  // Auto-navigate when two are selected
  if (compareSelections.value.length === 2) {
    router.push({
      name: 'Compare',
      params: { id1: compareSelections.value[0], id2: compareSelections.value[1] }
    })
    compareMode.value = false
    compareSelections.value = []
  }
}
let isAnimating = false  // Animation lock to prevent flickering
let expandDebounceTimer = null  // Debounce timer
let pendingState = null  // Target state to be executed

// Card layout configuration - adjusted to wider proportions
const CARDS_PER_ROW = 4
const CARD_WIDTH = 280
const CARD_HEIGHT = 280
const CARD_GAP = 24

// Dynamically compute container height style
const containerStyle = computed(() => {
  if (!isExpanded.value) {
    // Collapsed state: fixed height
    return { minHeight: '420px' }
  }

  // Expanded state: dynamically compute height based on card count
  const total = projects.value.length
  if (total === 0) {
    return { minHeight: '280px' }
  }

  const rows = Math.ceil(total / CARDS_PER_ROW)
  // Compute actual required height: rows * card height + (rows-1) * gap + small bottom margin
  const expandedHeight = rows * CARD_HEIGHT + (rows - 1) * CARD_GAP + 10

  return { minHeight: `${expandedHeight}px` }
})

// Get card style
const getCardStyle = (index) => {
  const total = projects.value.length

  if (isExpanded.value) {
    // Expanded state: grid layout
    const transition = 'transform 700ms cubic-bezier(0.23, 1, 0.32, 1), opacity 700ms cubic-bezier(0.23, 1, 0.32, 1), box-shadow 0.3s ease, border-color 0.3s ease'

    const col = index % CARDS_PER_ROW
    const row = Math.floor(index / CARDS_PER_ROW)

    // Compute the number of cards in the current row to center each row
    const currentRowStart = row * CARDS_PER_ROW
    const currentRowCards = Math.min(CARDS_PER_ROW, total - currentRowStart)

    const rowWidth = currentRowCards * CARD_WIDTH + (currentRowCards - 1) * CARD_GAP

    const startX = -(rowWidth / 2) + (CARD_WIDTH / 2)
    const colInRow = index % CARDS_PER_ROW
    const x = startX + colInRow * (CARD_WIDTH + CARD_GAP)

    // Expand downward, increase spacing from title
    const y = 20 + row * (CARD_HEIGHT + CARD_GAP)

    return {
      transform: `translate(${x}px, ${y}px) rotate(0deg) scale(1)`,
      zIndex: 100 + index,
      opacity: 1,
      transition: transition
    }
  } else {
    // Collapsed state: fan stack
    const transition = 'transform 700ms cubic-bezier(0.23, 1, 0.32, 1), opacity 700ms cubic-bezier(0.23, 1, 0.32, 1), box-shadow 0.3s ease, border-color 0.3s ease'

    const centerIndex = (total - 1) / 2
    const offset = index - centerIndex

    const x = offset * 35
    // Adjust starting position, close to title but with appropriate spacing
    const y = 25 + Math.abs(offset) * 8
    const r = offset * 3
    const s = 0.95 - Math.abs(offset) * 0.05

    return {
      transform: `translate(${x}px, ${y}px) rotate(${r}deg) scale(${s})`,
      zIndex: 10 + index,
      opacity: 1,
      transition: transition
    }
  }
}

// Get style class based on round progress
const getProgressClass = (simulation) => {
  const current = simulation.current_round || 0
  const total = simulation.total_rounds || 0

  if (total === 0 || current === 0) {
    // Not started
    return 'not-started'
  } else if (current >= total) {
    // Completed
    return 'completed'
  } else {
    // In progress
    return 'in-progress'
  }
}

// Format date (date part only)
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toISOString().slice(0, 10)
  } catch {
    return dateStr?.slice(0, 10) || ''
  }
}

// Format time (hours:minutes)
const formatTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${hours}:${minutes}`
  } catch {
    return ''
  }
}

// Truncate text
const truncateText = (text, maxLength) => {
  if (!text) return ''
  return text.length > maxLength ? text.slice(0, maxLength) + '...' : text
}

// Generate title from simulation requirement (first 20 chars)
const getSimulationTitle = (requirement) => {
  if (!requirement) return 'Untitled Simulation'
  const title = requirement.slice(0, 20)
  return requirement.length > 20 ? title + '...' : title
}

// Format simulation_id display (first 6 chars)
const formatSimulationId = (simulationId) => {
  if (!simulationId) return 'SIM_UNKNOWN'
  const prefix = simulationId.replace('sim_', '').slice(0, 6)
  return `SIM_${prefix.toUpperCase()}`
}

// Format rounds display (current/total rounds)
const formatRounds = (simulation) => {
  const current = simulation.current_round || 0
  const total = simulation.total_rounds || 0
  if (total === 0) return 'Not Started'
  return `${current}/${total} rounds`
}

// Get file type (for styling)
const getFileType = (filename) => {
  if (!filename) return 'other'
  const ext = filename.split('.').pop()?.toLowerCase()
  const typeMap = {
    'pdf': 'pdf',
    'doc': 'doc', 'docx': 'doc',
    'xls': 'xls', 'xlsx': 'xls', 'csv': 'xls',
    'ppt': 'ppt', 'pptx': 'ppt',
    'txt': 'txt', 'md': 'txt', 'json': 'code',
    'jpg': 'img', 'jpeg': 'img', 'png': 'img', 'gif': 'img',
    'zip': 'zip', 'rar': 'zip', '7z': 'zip'
  }
  return typeMap[ext] || 'other'
}

// Get file type label text
const getFileTypeLabel = (filename) => {
  if (!filename) return 'FILE'
  const ext = filename.split('.').pop()?.toUpperCase()
  return ext || 'FILE'
}

// Truncate filename (preserve extension)
const truncateFilename = (filename, maxLength) => {
  if (!filename) return 'Unknown file'
  if (filename.length <= maxLength) return filename

  const ext = filename.includes('.') ? '.' + filename.split('.').pop() : ''
  const nameWithoutExt = filename.slice(0, filename.length - ext.length)
  const truncatedName = nameWithoutExt.slice(0, maxLength - ext.length - 3) + '...'
  return truncatedName + ext
}

// Open project detail modal
const navigateToProject = (simulation) => {
  selectedProject.value = simulation
}

// Close modal
const closeModal = () => {
  selectedProject.value = null
  showForkPanel.value = false
  forkError.value = ''
  showResolvePanel.value = false
  resolveError.value = ''
}

// Navigate to graph build page (Project)
const goToProject = () => {
  if (selectedProject.value?.project_id) {
    router.push({
      name: 'Process',
      params: { projectId: selectedProject.value.project_id }
    })
    closeModal()
  }
}

// Navigate to agent setup page (Simulation)
const goToSimulation = () => {
  if (selectedProject.value?.simulation_id) {
    router.push({
      name: 'Simulation',
      params: { simulationId: selectedProject.value.simulation_id }
    })
    closeModal()
  }
}

// Navigate to simulation run page (Step 3)
const goToSimulationRun = () => {
  if (selectedProject.value?.simulation_id) {
    router.push({
      name: 'SimulationRun',
      params: { simulationId: selectedProject.value.simulation_id }
    })
    closeModal()
  }
}

// Navigate to replay page
const goToReplay = () => {
  if (selectedProject.value?.simulation_id) {
    router.push({
      name: 'Replay',
      params: { simulationId: selectedProject.value.simulation_id }
    })
    closeModal()
  }
}

// Navigate to analysis report page (Report)
const goToReport = () => {
  if (selectedProject.value?.report_id) {
    router.push({
      name: 'Report',
      params: { reportId: selectedProject.value.report_id }
    })
    closeModal()
  }
}

// Navigate to deep interaction page
const goToInteraction = () => {
  if (selectedProject.value?.report_id) {
    router.push({
      name: 'Interaction',
      params: { reportId: selectedProject.value.report_id }
    })
    closeModal()
  }
}

// Open fork panel for selected simulation
const openForkPanel = () => {
  forkRequirement.value = selectedProject.value?.simulation_requirement || ''
  forkError.value = ''
  showForkPanel.value = true
}

// Close fork panel
const closeForkPanel = () => {
  showForkPanel.value = false
  forkError.value = ''
}

// Execute fork
const executeFork = async () => {
  if (!selectedProject.value) return
  forking.value = true
  forkError.value = ''
  try {
    const response = await forkSimulation({
      parent_simulation_id: selectedProject.value.simulation_id,
      simulation_requirement: forkRequirement.value || undefined,
    })
    if (response.success) {
      const newSimId = response.data.simulation_id
      showForkPanel.value = false
      closeModal()
      await loadHistory()
      router.push({ name: 'SimulationRun', params: { simulationId: newSimId } })
    } else {
      forkError.value = response.error || 'Fork failed'
    }
  } catch (err) {
    forkError.value = err?.response?.data?.error || err.message || 'Fork failed'
  } finally {
    forking.value = false
  }
}

// Compute track record from resolved simulations
const trackRecord = computed(() => {
  const resolved = projects.value.filter(p => p.resolution)
  const withScore = resolved.filter(p => p.resolution.accuracy_score !== null && p.resolution.accuracy_score !== undefined)
  if (resolved.length === 0) return null
  const correct = withScore.filter(p => p.resolution.accuracy_score === 1.0).length
  const overallAccuracy = withScore.length > 0 ? Math.round((correct / withScore.length) * 100) : null
  return {
    total: resolved.length,
    withScore: withScore.length,
    correct,
    overallAccuracy,
  }
})

// Resolution helpers
const getResolutionLabel = (project) => {
  const r = project.resolution
  if (!r) return null
  if (r.accuracy_score === null || r.accuracy_score === undefined) {
    return { text: `Resolved: ${r.actual_outcome}`, cls: 'resolved-no-score' }
  }
  if (r.accuracy_score >= 1.0) {
    const pct = r.predicted_confidence ? Math.round(r.predicted_confidence * 100) : null
    return { text: `✓ Correct${pct ? ` — ${pct}% confident` : ''}`, cls: 'resolved-correct' }
  }
  if (r.accuracy_score <= 0.0) {
    const pct = r.predicted_confidence ? Math.round(r.predicted_confidence * 100) : null
    return { text: `✗ Incorrect${pct ? ` — ${pct}% confident` : ''}`, cls: 'resolved-wrong' }
  }
  return { text: '~ Split', cls: 'resolved-split' }
}

const openResolvePanel = () => {
  resolveError.value = ''
  showResolvePanel.value = true
}

const closeResolvePanel = () => {
  showResolvePanel.value = false
  resolveError.value = ''
}

const executeResolve = async (outcome) => {
  if (!selectedProject.value) return
  resolving.value = true
  resolveError.value = ''
  try {
    const response = await resolveSimulation(selectedProject.value.simulation_id, {
      actual_outcome: outcome,
    })
    if (response.success) {
      // Patch the local project object so the UI updates without a full reload
      selectedProject.value.resolution = response.data
      const idx = projects.value.findIndex(p => p.simulation_id === selectedProject.value.simulation_id)
      if (idx >= 0) projects.value[idx].resolution = response.data
      showResolvePanel.value = false
    } else {
      resolveError.value = response.error || 'Resolve failed'
    }
  } catch (err) {
    resolveError.value = err?.response?.data?.error || err.message || 'Resolve failed'
  } finally {
    resolving.value = false
  }
}

// Load history projects
const loadHistory = async () => {
  try {
    loading.value = true
    const response = await getSimulationHistory(20)
    if (response.success) {
      projects.value = response.data || []
    }
  } catch (error) {
    console.error('Failed to load history projects:', error)
    projects.value = []
  } finally {
    loading.value = false
  }
}

// Initialize IntersectionObserver
const initObserver = () => {
  if (observer) {
    observer.disconnect()
  }

  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        const shouldExpand = entry.isIntersecting

        // Update pending target state (record latest target state regardless of animation)
        pendingState = shouldExpand

        // Clear previous debounce timer (new scroll intent overrides old one)
        if (expandDebounceTimer) {
          clearTimeout(expandDebounceTimer)
          expandDebounceTimer = null
        }

        // If animating, just record state and wait for animation to finish
        if (isAnimating) return

        // If target state matches current state, no action needed
        if (shouldExpand === isExpanded.value) {
          pendingState = null
          return
        }

        // Use debounce delay for state transition to prevent rapid flickering
        // Shorter delay for expanding (50ms), longer for collapsing (200ms) for stability
        const delay = shouldExpand ? 50 : 200

        expandDebounceTimer = setTimeout(() => {
          // Check if animating
          if (isAnimating) return

          // Check if pending state still needs to execute (may have been overridden by subsequent scroll)
          if (pendingState === null || pendingState === isExpanded.value) return

          // Set animation lock
          isAnimating = true
          isExpanded.value = pendingState
          pendingState = null

          // Unlock after animation completes, and check for pending state changes
          setTimeout(() => {
            isAnimating = false

            // After animation ends, check if there's a new pending state
            if (pendingState !== null && pendingState !== isExpanded.value) {
              // Wait a short time before executing to avoid switching too fast
              expandDebounceTimer = setTimeout(() => {
                if (pendingState !== null && pendingState !== isExpanded.value) {
                  isAnimating = true
                  isExpanded.value = pendingState
                  pendingState = null
                  setTimeout(() => {
                    isAnimating = false
                  }, 750)
                }
              }, 100)
            }
          }, 750)
        }, delay)
      })
    },
    {
      // Use multiple thresholds for smoother detection
      threshold: [0.4, 0.6, 0.8],
      // Adjust rootMargin, shrink viewport bottom upward, requiring more scrolling to trigger expansion
      rootMargin: '0px 0px -150px 0px'
    }
  )

  // Start observing
  if (historyContainer.value) {
    observer.observe(historyContainer.value)
  }
}

// Watch route changes, reload data when returning to home page
watch(() => route.path, (newPath) => {
  if (newPath === '/') {
    loadHistory()
  }
})

onMounted(async () => {
  // Ensure DOM is rendered before loading data
  await nextTick()
  await loadHistory()

  // Initialize observer after DOM render
  setTimeout(() => {
    initObserver()
  }, 100)
})

// If using keep-alive, reload data when component is activated
onActivated(() => {
  loadHistory()
})

onUnmounted(() => {
  // Clean up Intersection Observer
  if (observer) {
    observer.disconnect()
    observer = null
  }
  // Clean up debounce timer
  if (expandDebounceTimer) {
    clearTimeout(expandDebounceTimer)
    expandDebounceTimer = null
  }
})
</script>

<style scoped>
/* Container */
.history-database {
  position: relative;
  width: 100%;
  min-height: 280px;
  margin-top: 40px;
  padding: 34px 0 40px;
  overflow: visible;
}

/* Simplified display when no projects */
.history-database.no-projects {
  min-height: auto;
  padding: 40px 0 22px;
}

/* Tech grid background */
.tech-grid-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  pointer-events: none;
}

/* Design system background grid */
.grid-pattern {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image:
    linear-gradient(rgba(67, 193, 101, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(67, 193, 101, 0.04) 1px, transparent 1px);
  background-size: 70px 70px;
  background-position: top left;
}

.gradient-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background:
    linear-gradient(to right, rgba(250, 250, 250, 0.9) 0%, transparent 15%, transparent 85%, rgba(250, 250, 250, 0.9) 100%),
    linear-gradient(to bottom, rgba(250, 250, 250, 0.8) 0%, transparent 20%, transparent 80%, rgba(250, 250, 250, 0.8) 100%);
  pointer-events: none;
}

/* Title area - design system label style */
.section-header {
  position: relative;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 22px;
  margin-bottom: 22px;
  font-family: var(--font-mono);
  padding: 0 40px;
}

.section-line {
  flex: 1;
  height: 7px;
  background: repeating-linear-gradient(-45deg, #FF6B1A, #FF6B1A 11px, #FAFAFA 11px, #FAFAFA 22px);
  max-width: 300px;
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  color: rgba(10, 10, 10, 0.5);
  letter-spacing: 3px;
  text-transform: uppercase;
}

/* Cards container */
.cards-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 0 40px;
  transition: min-height 700ms cubic-bezier(0.23, 1, 0.32, 1);
}

/* Project card - flat, bordered, sharp edges, corner markers */
.project-card {
  position: absolute;
  width: 280px;
  background: #FAFAFA;
  border: 2px solid rgba(10, 10, 10, 0.08);
  padding: 14px;
  cursor: pointer;
  transition: border-color 0.3s ease, transform 700ms cubic-bezier(0.23, 1, 0.32, 1), opacity 700ms cubic-bezier(0.23, 1, 0.32, 1);
}

/* Corner markers: orange top-left, green bottom-right */
.project-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 12px;
  height: 12px;
  border-top: 2px solid #FF6B1A;
  border-left: 2px solid #FF6B1A;
  pointer-events: none;
  z-index: 10;
}

.project-card::after {
  content: '';
  position: absolute;
  bottom: 0;
  right: 0;
  width: 12px;
  height: 12px;
  border-bottom: 2px solid #43C165;
  border-right: 2px solid #43C165;
  pointer-events: none;
  z-index: 10;
}

.project-card:hover {
  border-color: #FF6B1A;
  z-index: 1000 !important;
}

.project-card.hovering {
  z-index: 1000 !important;
}

/* Card header */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 11px;
  padding-bottom: 11px;
  border-bottom: 1px solid rgba(10, 10, 10, 0.08);
  font-family: var(--font-mono);
  font-size: 11px;
}

.card-id {
  color: rgba(10, 10, 10, 0.5);
  letter-spacing: 3px;
  font-weight: 500;
  text-transform: uppercase;
}

/* Feature status icon group */
.card-status-icons {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-icon {
  font-size: 0.75rem;
  transition: all 0.2s ease;
  cursor: default;
}

.status-icon.available {
  opacity: 1;
}

/* Feature colors - design system */
.status-icon:nth-child(1).available { color: #FF6B1A; } /* Graph Build - Orange */
.status-icon:nth-child(2).available { color: #FFB347; } /* Agent Setup - Amber */
.status-icon:nth-child(3).available { color: #43C165; } /* Analysis Report - Green */

.status-icon.unavailable {
  color: rgba(10, 10, 10, 0.12);
  opacity: 0.5;
}

/* Round progress display */
.card-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 3px;
  font-weight: 600;
  font-size: 11px;
  font-family: var(--font-mono);
  text-transform: uppercase;
}

.status-dot {
  font-size: 0.5rem;
}

/* Progress status colors */
.card-progress.completed { color: #43C165; }    /* Completed - Green */
.card-progress.in-progress { color: #FF6B1A; }  /* In Progress - Orange */
.card-progress.not-started { color: rgba(10, 10, 10, 0.4); }  /* Not Started - Gray */
.card-status.pending { color: rgba(10, 10, 10, 0.4); }

/* File list area */
.card-files-wrapper {
  position: relative;
  width: 100%;
  min-height: 48px;
  max-height: 110px;
  margin-bottom: 11px;
  padding: 8px 10px;
  background: #F5F5F5;
  border: 1px solid rgba(10, 10, 10, 0.08);
  overflow: hidden;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* More files hint */
.files-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3px 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.5);
  background: rgba(250, 250, 250, 0.5);
  letter-spacing: 3px;
  text-transform: uppercase;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  background: rgba(250, 250, 250, 0.7);
  transition: all 0.2s ease;
}

.file-item:hover {
  background: #FAFAFA;
  transform: translateX(2px);
  border-color: rgba(10, 10, 10, 0.08);
}

/* Minimal file tag style - flat, no rounded corners */
.file-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 16px;
  padding: 0 4px;
  font-family: var(--font-mono);
  font-size: 0.55rem;
  font-weight: 600;
  line-height: 1;
  text-transform: uppercase;
  letter-spacing: 3px;
  flex-shrink: 0;
  min-width: 28px;
  border: 1px solid rgba(10, 10, 10, 0.08);
}

/* File tag colors - flat design system palette */
.file-tag.pdf { background: rgba(255, 68, 68, 0.08); color: #FF4444; border-color: rgba(255, 68, 68, 0.15); }
.file-tag.doc { background: rgba(255, 107, 26, 0.08); color: #FF6B1A; border-color: rgba(255, 107, 26, 0.15); }
.file-tag.xls { background: rgba(67, 193, 101, 0.08); color: #43C165; border-color: rgba(67, 193, 101, 0.15); }
.file-tag.ppt { background: rgba(255, 179, 71, 0.08); color: #FFB347; border-color: rgba(255, 179, 71, 0.15); }
.file-tag.txt { background: rgba(10, 10, 10, 0.04); color: rgba(10, 10, 10, 0.5); border-color: rgba(10, 10, 10, 0.08); }
.file-tag.code { background: rgba(255, 107, 26, 0.06); color: rgba(10, 10, 10, 0.5); border-color: rgba(10, 10, 10, 0.08); }
.file-tag.img { background: rgba(67, 193, 101, 0.06); color: rgba(10, 10, 10, 0.5); border-color: rgba(10, 10, 10, 0.08); }
.file-tag.zip { background: rgba(255, 179, 71, 0.06); color: rgba(10, 10, 10, 0.5); border-color: rgba(10, 10, 10, 0.08); }
.file-tag.other { background: #F5F5F5; color: rgba(10, 10, 10, 0.5); border-color: rgba(10, 10, 10, 0.08); }

.file-name {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.5);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  letter-spacing: 0.1px;
}

/* No files placeholder */
.files-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 48px;
  color: rgba(10, 10, 10, 0.4);
}

.empty-file-icon {
  font-size: 1rem;
  opacity: 0.5;
}

.empty-file-text {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 3px;
  text-transform: uppercase;
}

/* Hover effect for file area */
.project-card:hover .card-files-wrapper {
  border-color: rgba(10, 10, 10, 0.12);
  background: #FAFAFA;
}

/* Corner decoration - orange */
.corner-mark.top-left-only {
  position: absolute;
  top: 6px;
  left: 6px;
  width: 8px;
  height: 8px;
  border-top: 1.5px solid #FF6B1A;
  border-left: 1.5px solid #FF6B1A;
  pointer-events: none;
  z-index: 10;
}

/* Card title */
.card-title {
  font-family: var(--font-display);
  font-size: 0.9rem;
  font-weight: 700;
  color: #0A0A0A;
  margin: 0 0 6px 0;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color 0.3s ease;
}

.project-card:hover .card-title {
  color: #FF6B1A;
}

/* Card description */
.card-desc {
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgba(10, 10, 10, 0.5);
  margin: 0 0 16px 0;
  line-height: 1.5;
  height: 34px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* Card footer */
.card-footer {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 11px;
  border-top: 1px solid rgba(10, 10, 10, 0.08);
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.4);
  font-weight: 500;
}

/* Date time combination */
.card-datetime {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Footer round progress display */
.card-footer .card-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 3px;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
}

.card-footer .status-dot {
  font-size: 0.5rem;
}

/* Progress status colors - footer */
.card-footer .card-progress.completed { color: #43C165; }
.card-footer .card-progress.in-progress { color: #FF6B1A; }
.card-footer .card-progress.not-started { color: rgba(10, 10, 10, 0.4); }

/* Bottom decoration line - orange */
.card-bottom-line {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 2px;
  width: 0;
  background-color: #FF6B1A;
  transition: width 0.5s cubic-bezier(0.23, 1, 0.32, 1);
  z-index: 20;
}

.project-card:hover .card-bottom-line {
  width: 100%;
}

/* Empty state */
.empty-state, .loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 56px;
  color: rgba(10, 10, 10, 0.4);
}

.empty-icon {
  font-size: 2rem;
  opacity: 0.5;
}

/* Loading spinner - orange */
.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(10, 10, 10, 0.08);
  border-top-color: #FF6B1A;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Responsive */
@media (max-width: 1200px) {
  .project-card {
    width: 240px;
  }
}

@media (max-width: 768px) {
  .cards-container {
    padding: 0 22px;
  }
  .project-card {
    width: 200px;
  }
}

/* ===== History Replay Detail Modal Styles ===== */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(10, 10, 10, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: #FAFAFA;
  width: 560px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  border: 2px solid rgba(10, 10, 10, 0.12);
  font-family: var(--font-mono);
}

/* Animation transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-content {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.modal-leave-active .modal-content {
  transition: all 0.2s ease-in;
}

.modal-enter-from .modal-content {
  transform: scale(0.95) translateY(10px);
  opacity: 0;
}

.modal-leave-to .modal-content {
  transform: scale(0.95) translateY(10px);
  opacity: 0;
}

/* Modal header */
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 22px 34px;
  border-bottom: 2px solid rgba(10, 10, 10, 0.08);
  background: #FAFAFA;
}

.modal-title-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.modal-id {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 600;
  color: #0A0A0A;
  letter-spacing: 3px;
  text-transform: uppercase;
}

.modal-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  padding: 4px 8px;
  background: #F5F5F5;
  border: 1px solid rgba(10, 10, 10, 0.08);
}

.modal-progress.completed { color: #43C165; background: rgba(67, 193, 101, 0.08); border-color: rgba(67, 193, 101, 0.15); }
.modal-progress.in-progress { color: #FF6B1A; background: rgba(255, 107, 26, 0.08); border-color: rgba(255, 107, 26, 0.15); }
.modal-progress.not-started { color: rgba(10, 10, 10, 0.4); background: #F5F5F5; border-color: rgba(10, 10, 10, 0.08); }

.modal-create-time {
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgba(10, 10, 10, 0.4);
  letter-spacing: 3px;
}

.modal-close {
  width: 34px;
  height: 34px;
  border: 2px solid rgba(10, 10, 10, 0.08);
  background: transparent;
  font-size: 1.5rem;
  color: rgba(10, 10, 10, 0.4);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.modal-close:hover {
  background: #F5F5F5;
  color: #0A0A0A;
  border-color: #FF6B1A;
}

/* Modal content */
.modal-body {
  padding: 22px 34px;
}

.modal-section {
  margin-bottom: 22px;
}

.modal-section:last-child {
  margin-bottom: 0;
}

.modal-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.5);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 11px;
  font-weight: 500;
}

.modal-requirement {
  font-size: 0.95rem;
  color: rgba(10, 10, 10, 0.7);
  line-height: 1.6;
  padding: 16px;
  background: #F5F5F5;
  border: 1px solid rgba(10, 10, 10, 0.08);
}

.modal-files {
  display: flex;
  flex-direction: column;
  gap: 11px;
  max-height: 200px;
  overflow-y: auto;
  padding-right: 4px;
}

/* Custom scrollbar style */
.modal-files::-webkit-scrollbar {
  width: 4px;
}

.modal-files::-webkit-scrollbar-track {
  background: #F5F5F5;
}

.modal-files::-webkit-scrollbar-thumb {
  background: rgba(10, 10, 10, 0.12);
}

.modal-files::-webkit-scrollbar-thumb:hover {
  background: rgba(10, 10, 10, 0.4);
}

.modal-file-item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 14px;
  background: #FAFAFA;
  border: 1px solid rgba(10, 10, 10, 0.08);
  transition: all 0.2s ease;
}

.modal-file-item:hover {
  border-color: rgba(10, 10, 10, 0.12);
}

.modal-file-name {
  font-size: 13px;
  color: rgba(10, 10, 10, 0.5);
  font-family: var(--font-mono);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.modal-empty {
  font-size: 13px;
  color: rgba(10, 10, 10, 0.4);
  font-family: var(--font-mono);
  padding: 16px;
  background: #F5F5F5;
  border: 1px dashed rgba(10, 10, 10, 0.12);
  text-align: center;
}

/* Simulation replay divider - warning stripes */
.modal-divider {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 11px 34px 0;
  background: #FAFAFA;
}

.divider-line {
  flex: 1;
  height: 7px;
  background: repeating-linear-gradient(-45deg, #FF6B1A, #FF6B1A 11px, #FAFAFA 11px, #FAFAFA 22px);
}

.divider-text {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.4);
  letter-spacing: 3px;
  text-transform: uppercase;
  white-space: nowrap;
}

/* Navigation buttons */
.modal-actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 11px;
  padding: 22px 34px;
  background: #FAFAFA;
}

.modal-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border: 2px solid rgba(10, 10, 10, 0.08);
  background: #FAFAFA;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}

.modal-btn:hover:not(:disabled) {
  border-color: #FF6B1A;
  transform: translateY(-2px);
}

.modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: #F5F5F5;
}

.btn-step {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  color: rgba(10, 10, 10, 0.4);
  letter-spacing: 3px;
  text-transform: uppercase;
}

.btn-icon {
  font-size: 1.4rem;
  line-height: 1;
  transition: color 0.2s ease;
}

.btn-text {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: rgba(10, 10, 10, 0.5);
}

.modal-btn.btn-project .btn-icon { color: #FF6B1A; }
.modal-btn.btn-simulation .btn-icon { color: #FFB347; }
.modal-btn.btn-simrun .btn-icon { color: #FF6B1A; }
.modal-btn.btn-replay .btn-icon { color: #FF6B1A; }
.modal-btn.btn-report .btn-icon { color: #43C165; }
.modal-btn.btn-interaction .btn-icon { color: #FF6B1A; }

.modal-btn:hover:not(:disabled) .btn-text {
  color: #0A0A0A;
}

/* Non-replayable hint */
.modal-playback-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 34px 22px;
  background: #FAFAFA;
}

.hint-text {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.4);
  letter-spacing: 3px;
  text-align: center;
  line-height: 1.5;
}

.card-progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Compare mode */
.compare-mode-btn {
  padding: 5px 14px;
  border: 1px solid rgba(10,10,10,0.2);
  background: transparent;
  color: rgba(10,10,10,0.5);
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
  font-family: 'Space Mono', monospace;
  transition: all 0.15s;
  flex-shrink: 0;
}
.compare-mode-btn:hover { border-color: #FF6B1A; color: #FF6B1A; }
.compare-mode-btn.active { border-color: #FF6B1A; color: #FF6B1A; background: rgba(255,107,26,0.06); }

.compare-select-btn {
  padding: 2px 8px;
  border: 1px solid rgba(10,10,10,0.2);
  background: transparent;
  color: rgba(10,10,10,0.4);
  border-radius: 3px;
  cursor: pointer;
  font-size: 11px;
  font-family: 'Space Mono', monospace;
  transition: all 0.15s;
}
.compare-select-btn:hover { border-color: #FF6B1A; color: #FF6B1A; }
.compare-select-btn.selected { border-color: #FF6B1A; color: #FF6B1A; background: rgba(255,107,26,0.1); }

/* ===== Fork badge on cards ===== */
.fork-badge {
  font-size: 0.8rem;
  color: #FFB347;
  opacity: 0.8;
  cursor: default;
}

/* ===== Fork section in modal ===== */
.modal-fork-section {
  background: #FAFAFA;
  padding: 0 0 22px;
}

.fork-intro {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 16px 34px 0;
}

.fork-desc {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.4);
  letter-spacing: 1px;
  text-align: center;
  margin: 0;
}

.fork-trigger-btn {
  padding: 8px 22px;
  border: 1px solid rgba(255, 179, 71, 0.5);
  background: rgba(255, 179, 71, 0.06);
  color: #CC8800;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 2px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.fork-trigger-btn:hover {
  border-color: #FFB347;
  background: rgba(255, 179, 71, 0.12);
}

.fork-lineage-badge {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.4);
  letter-spacing: 2px;
}

.fork-parent-id {
  color: #FFB347;
  font-weight: 600;
}

/* Fork form */
.fork-form {
  padding: 16px 34px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fork-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.5);
  text-transform: uppercase;
  letter-spacing: 3px;
}

.fork-textarea {
  width: 100%;
  padding: 10px 12px;
  background: #F5F5F5;
  border: 1px solid rgba(10, 10, 10, 0.12);
  font-family: var(--font-mono);
  font-size: 12px;
  color: #0A0A0A;
  resize: vertical;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.fork-textarea:focus {
  border-color: #FFB347;
}

.fork-note {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10, 10, 10, 0.35);
  letter-spacing: 1px;
  margin: 0;
}

.fork-error {
  font-family: var(--font-mono);
  font-size: 11px;
  color: #FF4444;
  padding: 6px 10px;
  background: rgba(255, 68, 68, 0.06);
  border: 1px solid rgba(255, 68, 68, 0.15);
}

.fork-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.fork-cancel-btn {
  padding: 8px 16px;
  border: 1px solid rgba(10, 10, 10, 0.12);
  background: transparent;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10, 10, 10, 0.5);
  cursor: pointer;
  letter-spacing: 2px;
  transition: all 0.2s;
}

.fork-cancel-btn:hover:not(:disabled) {
  border-color: rgba(10, 10, 10, 0.3);
  color: #0A0A0A;
}

.fork-submit-btn {
  padding: 8px 18px;
  border: 1px solid rgba(255, 179, 71, 0.6);
  background: rgba(255, 179, 71, 0.08);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: #CC8800;
  cursor: pointer;
  letter-spacing: 2px;
  transition: all 0.2s;
}

.fork-submit-btn:hover:not(:disabled) {
  background: rgba(255, 179, 71, 0.18);
  border-color: #FFB347;
}

.fork-submit-btn:disabled,
.fork-cancel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── Resolution badge on history cards ── */
.resolution-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  font-size: 9px;
  font-weight: 700;
  border: 1px solid currentColor;
}
.resolution-badge.correct  { color: #22c55e; background: rgba(34,197,94,0.1); }
.resolution-badge.wrong    { color: #ef4444; background: rgba(239,68,68,0.1); }
.resolution-badge.neutral  { color: #a78bfa; background: rgba(167,139,250,0.1); }
.resolution-badge.pending  { font-size: 8px; color: rgba(10,10,10,0.4); border-color: rgba(10,10,10,0.2); background: transparent; }

/* ── Track Record bar ── */
.track-record-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  margin-bottom: 10px;
  border: 1px solid rgba(10,10,10,0.08);
  background: rgba(10,10,10,0.02);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 1px;
}
.track-record-label {
  font-weight: 700;
  color: rgba(10,10,10,0.5);
  text-transform: uppercase;
  font-size: 9px;
  letter-spacing: 2px;
}
.track-record-stat { color: rgba(10,10,10,0.6); }
.track-record-accuracy.good  { color: #22c55e; font-weight: 600; }
.track-record-accuracy.poor  { color: #ef4444; font-weight: 600; }
.track-record-correct        { color: rgba(10,10,10,0.4); }

/* ── Resolve modal section ── */
.modal-resolve-section {
  margin-top: 12px;
  padding-top: 0;
}

.resolve-intro {
  padding: 0 20px 16px;
}
.resolve-desc {
  font-size: 12px;
  color: rgba(10,10,10,0.55);
  margin: 8px 0 12px;
  line-height: 1.5;
}
.resolve-trigger-btn {
  padding: 7px 16px;
  border: 1px solid rgba(10,10,10,0.2);
  background: transparent;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.7);
  cursor: pointer;
  letter-spacing: 2px;
  transition: all 0.2s;
}
.resolve-trigger-btn:hover {
  border-color: rgba(10,10,10,0.5);
  color: #0A0A0A;
}

.resolve-form {
  padding: 0 20px 16px;
}
.resolve-form-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  letter-spacing: 2px;
  text-transform: uppercase;
  margin: 8px 0 12px;
}
.resolve-buttons {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}
.resolve-outcome-btn {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 2px;
  cursor: pointer;
  transition: all 0.2s;
}
.resolve-outcome-btn.yes {
  border-color: rgba(34,197,94,0.5);
  background: rgba(34,197,94,0.06);
  color: #16a34a;
}
.resolve-outcome-btn.yes:hover:not(:disabled) {
  background: rgba(34,197,94,0.15);
  border-color: #22c55e;
}
.resolve-outcome-btn.no {
  border-color: rgba(239,68,68,0.5);
  background: rgba(239,68,68,0.06);
  color: #dc2626;
}
.resolve-outcome-btn.no:hover:not(:disabled) {
  background: rgba(239,68,68,0.15);
  border-color: #ef4444;
}
.resolve-outcome-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.resolve-cancel-btn {
  padding: 6px 14px;
  border: 1px solid rgba(10,10,10,0.12);
  background: transparent;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.4);
  cursor: pointer;
  letter-spacing: 2px;
  transition: all 0.2s;
}
.resolve-cancel-btn:hover:not(:disabled) {
  border-color: rgba(10,10,10,0.3);
  color: #0A0A0A;
}
.resolve-cancel-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.resolve-error {
  font-size: 11px;
  color: #ef4444;
  margin-bottom: 8px;
  padding: 6px 10px;
  border: 1px solid rgba(239,68,68,0.3);
  background: rgba(239,68,68,0.05);
}

/* Resolved result display */
.resolve-result {
  padding: 0 20px 16px;
}
.resolve-result-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.resolve-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  letter-spacing: 1px;
  text-transform: uppercase;
  min-width: 120px;
}
.resolve-value { font-family: var(--font-mono); font-size: 12px; font-weight: 600; }
.outcome-badge { padding: 2px 8px; border: 1px solid currentColor; }
.outcome-badge.yes { color: #16a34a; background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.4); }
.outcome-badge.no  { color: #dc2626; background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.4); }
.resolve-confidence { font-size: 10px; font-weight: 400; margin-left: 4px; opacity: 0.7; }
.accuracy-value { font-size: 12px; }
.accuracy-value.correct { color: #16a34a; }
.accuracy-value.wrong   { color: #dc2626; }
.accuracy-value.split   { color: #a78bfa; }
.resolve-notes {
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  margin-top: 6px;
  font-style: italic;
}
.resolve-reopen-btn {
  margin-top: 10px;
  padding: 5px 12px;
  border: 1px solid rgba(10,10,10,0.1);
  background: transparent;
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.35);
  cursor: pointer;
  letter-spacing: 1px;
  transition: all 0.2s;
}
.resolve-reopen-btn:hover { border-color: rgba(10,10,10,0.3); color: rgba(10,10,10,0.7); }
</style>
