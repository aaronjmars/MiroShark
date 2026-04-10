<template>
  <div class="workbench-panel">
    <div class="scroll-container">
      <!-- Step 01: Ontology -->
      <div class="step-card" :class="{ 'active': currentPhase === 0, 'completed': currentPhase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">Ontology Generation</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 0" class="badge success">Completed</span>
            <span v-else-if="currentPhase === 0" class="badge processing">Generating</span>
            <span v-else class="badge pending">Waiting</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/graph/ontology/generate</p>
          <p class="description">
            LLM analyzes document content and simulation requirements, extracts reality seeds, and automatically generates a suitable ontology structure
          </p>

          <!-- Loading / Progress -->
          <div v-if="currentPhase === 0 && ontologyProgress" class="progress-section">
            <div class="spinner-sm"></div>
            <span>{{ ontologyProgress.message || 'Analyzing documents...' }}</span>
          </div>

          <!-- Detail Overlay -->
          <div v-if="selectedOntologyItem" class="ontology-detail-overlay">
            <div class="detail-header">
               <div class="detail-title-group">
                  <span class="detail-type-badge">{{ selectedOntologyItem.itemType === 'entity' ? 'ENTITY' : 'RELATION' }}</span>
                  <span class="detail-name">{{ selectedOntologyItem.name }}</span>
               </div>
               <button class="close-btn" @click="selectedOntologyItem = null">×</button>
            </div>
            <div class="detail-body">
               <div class="detail-desc">{{ selectedOntologyItem.description }}</div>

               <!-- Attributes -->
               <div class="detail-section" v-if="selectedOntologyItem.attributes?.length">
                  <span class="section-label">ATTRIBUTES</span>
                  <div class="attr-list">
                     <div v-for="attr in selectedOntologyItem.attributes" :key="attr.name" class="attr-item">
                        <span class="attr-name">{{ attr.name }}</span>
                        <span class="attr-type">({{ attr.type }})</span>
                        <span class="attr-desc">{{ attr.description }}</span>
                     </div>
                  </div>
               </div>

               <!-- Examples (Entity) -->
               <div class="detail-section" v-if="selectedOntologyItem.examples?.length">
                  <span class="section-label">EXAMPLES</span>
                  <div class="example-list">
                     <span v-for="ex in selectedOntologyItem.examples" :key="ex" class="example-tag">{{ ex }}</span>
                  </div>
               </div>

               <!-- Source/Target (Relation) -->
               <div class="detail-section" v-if="selectedOntologyItem.source_targets?.length">
                  <span class="section-label">CONNECTIONS</span>
                  <div class="conn-list">
                     <div v-for="(conn, idx) in selectedOntologyItem.source_targets" :key="idx" class="conn-item">
                        <span class="conn-node">{{ conn.source }}</span>
                        <span class="conn-arrow">→</span>
                        <span class="conn-node">{{ conn.target }}</span>
                     </div>
                  </div>
               </div>
            </div>
          </div>

          <!-- Generated Entity Tags -->
          <div v-if="projectData?.ontology?.entity_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">GENERATED ENTITY TYPES</span>
            <div class="tags-list">
              <span
                v-for="entity in projectData.ontology.entity_types"
                :key="entity.name"
                class="entity-tag clickable"
                @click="selectOntologyItem(entity, 'entity')"
              >
                {{ entity.name }}
              </span>
            </div>
          </div>

          <!-- Generated Relation Tags -->
          <div v-if="projectData?.ontology?.edge_types" class="tags-container" :class="{ 'dimmed': selectedOntologyItem }">
            <span class="tag-label">GENERATED RELATION TYPES</span>
            <div class="tags-list">
              <span
                v-for="rel in projectData.ontology.edge_types"
                :key="rel.name"
                class="entity-tag clickable"
                @click="selectOntologyItem(rel, 'relation')"
              >
                {{ rel.name }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 02: Graph Build -->
      <div class="step-card" :class="{ 'active': currentPhase === 1, 'completed': currentPhase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">GraphRAG Build</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase > 1" class="badge success">Completed</span>
            <span v-else-if="currentPhase === 1" class="badge processing">{{ buildProgress?.progress || 0 }}%</span>
            <span v-else class="badge pending">Waiting</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/graph/build</p>
          <p class="description">
            Based on the generated ontology, automatically chunks documents and builds a knowledge graph via Neo4j, extracting entities and relationships, forming temporal memory and community summaries
          </p>

          <!-- Stats Cards -->
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.nodes }}</span>
              <span class="stat-label">Entity Nodes</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.edges }}</span>
              <span class="stat-label">Relation Edges</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ graphStats.types }}</span>
              <span class="stat-label">Schema Types</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 03: Complete -->
      <div class="step-card" :class="{ 'active': currentPhase === 2, 'completed': currentPhase >= 2 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">Build Complete</span>
          </div>
          <div class="step-status">
            <span v-if="currentPhase >= 2" class="badge accent">Ready to launch</span>
          </div>
        </div>

        <div class="card-content">
          <p class="description">Graph build is complete. Please proceed to the next step for simulation agent setup.</p>

          <!-- Existing simulations -->
          <div v-if="existingSimulations.length > 0" class="existing-sims">
            <div
              v-for="sim in existingSimulations"
              :key="sim.simulation_id"
              class="sim-entry"
              @click="resumeSimulation(sim.simulation_id)"
            >
              <span class="sim-id mono">{{ sim.simulation_id }}</span>
              <span class="sim-status" :class="sim.status">{{ sim.status }}</span>
              <span class="sim-arrow">→</span>
            </div>
          </div>

          <button
            class="action-btn"
            :disabled="currentPhase < 2 || creatingSimulation"
            @click="handleEnterEnvSetup"
          >
            <span v-if="creatingSimulation" class="spinner-sm"></span>
            {{ creatingSimulation ? 'Creating...' : (existingSimulations.length > 0 ? 'New Simulation ➝' : 'Enter Agent Setup ➝') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom Info / Logs -->
    <div class="system-logs" :class="{ collapsed: dashboardCollapsed }">
      <div class="log-header" @click="dashboardCollapsed = !dashboardCollapsed">
        <span class="log-title">SYSTEM DASHBOARD <span class="log-toggle">{{ dashboardCollapsed ? '▲' : '▼' }}</span></span>
        <span class="log-id">{{ projectData?.project_id || 'NO_PROJECT' }}</span>
      </div>
      <div v-show="!dashboardCollapsed" class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { createSimulation, listSimulations } from '../api/simulation'

const router = useRouter()

const props = defineProps({
  currentPhase: { type: Number, default: 0 },
  projectData: Object,
  ontologyProgress: Object,
  buildProgress: Object,
  graphData: Object,
  systemLogs: { type: Array, default: () => [] }
})

defineEmits(['next-step'])

const selectedOntologyItem = ref(null)
const logContent = ref(null)
const dashboardCollapsed = ref(true)
const creatingSimulation = ref(false)
const existingSimulations = ref([])

// Check for existing simulations for this project
const loadExistingSimulations = async () => {
  if (!props.projectData?.project_id) return
  try {
    const res = await listSimulations(props.projectData.project_id)
    if (res.success && res.data) {
      existingSimulations.value = res.data
    }
  } catch (err) {
    // silent
  }
}

onMounted(loadExistingSimulations)
watch(() => props.projectData?.project_id, loadExistingSimulations)

const resumeSimulation = (simId) => {
  router.push({ name: 'Simulation', params: { simulationId: simId } })
}

// Enter agent setup - create simulation and navigate
const handleEnterEnvSetup = async () => {
  if (!props.projectData?.project_id || !props.projectData?.graph_id) {
    console.error('Missing project or graph information')
    return
  }

  creatingSimulation.value = true

  try {
    const res = await createSimulation({
      project_id: props.projectData.project_id,
      graph_id: props.projectData.graph_id,
      enable_twitter: true,
      enable_reddit: true,
    })

    if (res.success && res.data?.simulation_id) {
      // Navigate to simulation page
      router.push({
        name: 'Simulation',
        params: { simulationId: res.data.simulation_id }
      })
    } else {
      console.error('Failed to create simulation:', res.error)
      alert('Failed to create simulation: ' + (res.error || 'Unknown error'))
    }
  } catch (err) {
    console.error('Simulation creation error:', err)
    alert('Simulation creation error: ' + err.message)
  } finally {
    creatingSimulation.value = false
  }
}

const selectOntologyItem = (item, type) => {
  selectedOntologyItem.value = { ...item, itemType: type }
}

const graphStats = computed(() => {
  const nodes = props.graphData?.node_count || props.graphData?.nodes?.length || 0
  const edges = props.graphData?.edge_count || props.graphData?.edges?.length || 0
  const types = props.projectData?.ontology?.entity_types?.length || 0
  return { nodes, edges, types }
})

const formatDate = (dateStr) => {
  if (!dateStr) return '--:--:--'
  const d = new Date(dateStr)
  return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + d.getMilliseconds()
}

// Auto-scroll logs
watch(() => props.systemLogs.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.workbench-panel {
  height: 100%;
  background-color: #FAFAFA;
  background-image:
    linear-gradient(rgba(10,10,10,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(10,10,10,0.03) 1px, transparent 1px);
  background-size: 22px 22px;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.step-card {
  background: #FAFAFA;
  padding: 22px;
  border: 2px solid rgba(10,10,10,0.08);
  transition: all 0.3s ease;
  position: relative;
}

/* Corner markers: orange top-left, green bottom-right */
.step-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 16px;
  height: 16px;
  border-top: 3px solid #FF6B1A;
  border-left: 3px solid #FF6B1A;
}

.step-card::after {
  content: '';
  position: absolute;
  bottom: 0;
  right: 0;
  width: 16px;
  height: 16px;
  border-bottom: 3px solid #43C165;
  border-right: 3px solid #43C165;
}

.step-card.active {
  border-color: #FF6B1A;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 22px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 11px;
}

.step-num {
  font-family: var(--font-mono);
  font-size: 20px;
  font-weight: 700;
  color: rgba(10,10,10,0.12);
}

.step-card.active .step-num,
.step-card.completed .step-num {
  color: #0A0A0A;
}

.step-title {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
}

.badge {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 4px 8px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.badge.success { background: #43C165; color: #FAFAFA; }
.badge.processing { background: #FF6B1A; color: #FAFAFA; }
.badge.accent { background: #FF6B1A; color: #FAFAFA; }
.badge.pending { background: #F5F5F5; color: rgba(10,10,10,0.4); }

.api-note {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  margin-bottom: 8px;
}

.description {
  font-size: 12px;
  color: rgba(10,10,10,0.5);
  line-height: 1.5;
  margin-bottom: 22px;
}

/* Step 01 Tags */
.tags-container {
  margin-top: 11px;
  transition: opacity 0.3s;
}

.tags-container.dimmed {
    opacity: 0.3;
    pointer-events: none;
}

.tag-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.4);
  margin-bottom: 8px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.entity-tag {
  background: #F5F5F5;
  border: 1px solid rgba(10,10,10,0.08);
  padding: 4px 10px;
  font-size: 11px;
  color: rgba(10,10,10,0.7);
  font-family: var(--font-mono);
  transition: all 0.2s;
}

.entity-tag.clickable {
    cursor: pointer;
}

.entity-tag.clickable:hover {
    background: rgba(10,10,10,0.12);
    border-color: rgba(10,10,10,0.2);
}

/* Ontology Detail Overlay */
.ontology-detail-overlay {
    position: absolute;
    top: 60px;
    left: 22px;
    right: 22px;
    bottom: 22px;
    background: rgba(250, 250, 250, 0.98);
    backdrop-filter: blur(4px);
    z-index: 10;
    border: 2px solid rgba(10,10,10,0.08);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

.detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 11px 22px;
    border-bottom: 2px solid rgba(10,10,10,0.08);
    background: #FAFAFA;
}

.detail-title-group {
    display: flex;
    align-items: center;
    gap: 8px;
}

.detail-type-badge {
    font-family: var(--font-mono);
    font-size: 9px;
    font-weight: 700;
    color: #FAFAFA;
    background: #0A0A0A;
    padding: 2px 6px;
    text-transform: uppercase;
    letter-spacing: 3px;
}

.detail-name {
    font-size: 14px;
    font-weight: 700;
    font-family: var(--font-mono);
}

.close-btn {
    background: none;
    border: none;
    font-size: 18px;
    color: rgba(10,10,10,0.4);
    cursor: pointer;
    line-height: 1;
}

.close-btn:hover {
    color: rgba(10,10,10,0.7);
}

.detail-body {
    flex: 1;
    overflow-y: auto;
    padding: 22px;
}

.detail-desc {
    font-size: 12px;
    color: rgba(10,10,10,0.6);
    line-height: 1.5;
    margin-bottom: 22px;
    padding-bottom: 11px;
    border-bottom: 1px dashed rgba(10,10,10,0.08);
}

.detail-section {
    margin-bottom: 22px;
}

.section-label {
    display: block;
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    color: rgba(10,10,10,0.4);
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 3px;
}

.attr-list, .conn-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.attr-item {
    font-size: 11px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: baseline;
    padding: 4px;
    background: #F5F5F5;
}

.attr-name {
    font-family: var(--font-mono);
    font-weight: 600;
    color: #0A0A0A;
}

.attr-type {
    color: rgba(10,10,10,0.4);
    font-size: 10px;
}

.attr-desc {
    color: rgba(10,10,10,0.5);
    flex: 1;
    min-width: 150px;
}

.example-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.example-tag {
    font-size: 11px;
    background: #FAFAFA;
    border: 1px solid rgba(10,10,10,0.12);
    padding: 3px 8px;
    color: rgba(10,10,10,0.5);
}

.conn-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    padding: 6px;
    background: #F5F5F5;
    font-family: var(--font-mono);
}

.conn-node {
    font-weight: 600;
    color: rgba(10,10,10,0.7);
}

.conn-arrow {
    color: rgba(10,10,10,0.2);
}

/* Step 02 Stats */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 11px;
  background: #F5F5F5;
  padding: 22px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #0A0A0A;
  font-family: var(--font-mono);
}

.stat-label {
  font-family: var(--font-mono);
  font-size: 9px;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-top: 4px;
  display: block;
}

/* Step 03 Button */
.action-btn {
  width: 100%;
  background: #0A0A0A;
  color: #FAFAFA;
  border: none;
  padding: 14px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.action-btn:hover:not(:disabled) {
  opacity: 0.8;
}

.action-btn:disabled {
  background: rgba(10,10,10,0.2);
  cursor: not-allowed;
}

.existing-sims {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 11px;
}

.sim-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 11px;
  border: 2px solid rgba(10,10,10,0.12);
  cursor: pointer;
  transition: all 0.15s;
  font-size: 11px;
}

.sim-entry:hover {
  background: #F5F5F5;
  border-color: rgba(10,10,10,0.7);
}

.sim-id {
  flex: 1;
  color: rgba(10,10,10,0.7);
  font-weight: 500;
}

.sim-status {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  padding: 2px 6px;
  background: #F5F5F5;
  color: rgba(10,10,10,0.5);
}

.sim-status.ready, .sim-status.completed { color: #FAFAFA; background: #43C165; }
.sim-status.running { color: #FAFAFA; background: #FF6B1A; }
.sim-status.failed { color: #FAFAFA; background: #FF4444; }
.sim-status.paused, .sim-status.stopped { color: #0A0A0A; background: #FFB347; }

.sim-arrow {
  color: rgba(10,10,10,0.4);
  font-size: 12px;
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 11px;
  font-size: 12px;
  color: #FF6B1A;
  margin-bottom: 11px;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,107,26,0.3);
  border-top-color: #FF6B1A;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* System Logs */
.system-logs {
  background: #0A0A0A;
  color: rgba(250,250,250,0.8);
  padding: 22px;
  font-family: var(--font-mono);
  border-top: 2px solid rgba(250,250,250,0.08);
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid rgba(250,250,250,0.1);
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(250,250,250,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
  cursor: pointer;
  user-select: none;
}

.system-logs.collapsed .log-header {
  border-bottom: none;
  padding-bottom: 0;
  margin-bottom: 0;
}

.log-toggle {
  font-size: 8px;
  opacity: 0.5;
  margin-left: 4px;
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 80px;
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: rgba(250,250,250,0.15);
}

.log-line {
  font-size: 11px;
  display: flex;
  gap: 11px;
  line-height: 1.5;
}

.log-time {
  color: #FF6B1A;
  min-width: 75px;
}

.log-msg {
  color: rgba(250,250,250,0.6);
  word-break: break-all;
}

.log-id {
  color: #43C165;
}
</style>
