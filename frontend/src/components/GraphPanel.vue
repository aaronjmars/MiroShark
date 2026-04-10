<template>
  <div class="graph-panel">
    <div class="panel-header">
      <span class="panel-title">Graph Overview</span>
      <!-- Top Toolbar (Internal Top Right) -->
      <div class="header-tools">
        <button class="tool-btn" @click="$emit('refresh')" :disabled="loading" title="Refresh Graph">
          <span class="icon-refresh" :class="{ 'spinning': loading }">↻</span>
          <span class="btn-text">Refresh</span>
        </button>
        <button class="tool-btn" @click="$emit('toggle-maximize')" title="Maximize/Restore">
          <span class="icon-maximize">⛶</span>
        </button>
      </div>
    </div>
    
    <div class="graph-container" ref="graphContainer">
      <!-- Graph Visualization -->
      <div v-if="graphData" class="graph-view">
        <svg ref="graphSvg" class="graph-svg"></svg>
        
        <!-- Building/Simulating Hint -->
        <div v-if="(currentPhase === 1 || isSimulating) && !hideUpdateHint" class="graph-building-hint">
          <div class="memory-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="memory-icon">
              <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-4.04z" />
              <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-4.04z" />
            </svg>
          </div>
          Updating in real time...
          <span class="hint-close" @click="hideUpdateHint = true">&times;</span>
        </div>
        
        
        <!-- Node/Edge Detail Panel -->
        <div v-if="selectedItem" class="detail-panel">
          <div class="detail-panel-header">
            <span class="detail-title">{{ selectedItem.type === 'node' ? 'Agent Details' : 'Relationship' }}</span>
            <span v-if="selectedItem.type === 'node'" class="detail-type-badge" :style="{ background: selectedItem.color, color: '#fff' }">
              {{ selectedItem.entityType }}
            </span>
            <button class="detail-close" @click="closeDetailPanel">×</button>
          </div>
          
          <!-- Node Details -->
          <div v-if="selectedItem.type === 'node'" class="detail-content">
            <div class="detail-row">
              <span class="detail-label">Name:</span>
              <span class="detail-value">{{ selectedItem.data.name }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">UUID:</span>
              <span class="detail-value uuid-text copyable" @click="copyText(selectedItem.data.uuid)">{{ selectedItem.data.uuid }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.created_at">
              <span class="detail-label">Created:</span>
              <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
            </div>
            
            <!-- Properties -->
            <div class="detail-section" v-if="selectedItem.data.attributes && Object.keys(selectedItem.data.attributes).length > 0">
              <div class="section-title">Properties:</div>
              <div class="properties-list">
                <div v-for="(value, key) in selectedItem.data.attributes" :key="key" class="property-item">
                  <span class="property-key">{{ key }}:</span>
                  <span class="property-value">{{ value || 'None' }}</span>
                </div>
              </div>
            </div>
            
            <!-- Summary -->
            <div class="detail-section" v-if="selectedItem.data.summary">
              <div class="section-title">Summary:</div>
              <div class="summary-text">{{ selectedItem.data.summary }}</div>
            </div>
            
            <!-- Labels -->
            <div class="detail-section" v-if="selectedItem.data.labels && selectedItem.data.labels.length > 0">
              <div class="section-title">Labels:</div>
              <div class="labels-list">
                <span v-for="label in selectedItem.data.labels" :key="label" class="label-tag">
                  {{ label }}
                </span>
              </div>
            </div>

            <!-- Agent Actions (shown during simulation) -->
            <div class="detail-section" v-if="simulationId">
              <div class="section-title actions-title" @click="actionsExpanded = !actionsExpanded" style="cursor: pointer;">
                <span class="actions-toggle">{{ actionsExpanded ? '▼' : '▶' }}</span>
                Agent Actions
                <span v-if="agentActionsLoading" class="actions-loading">loading...</span>
                <span v-else-if="agentActions.length > 0" class="actions-count">{{ agentActions.length }}</span>
              </div>
              <div v-show="actionsExpanded">
                <div v-if="agentActions.length > 0" class="agent-actions-list">
                  <div
                    v-for="(action, idx) in agentActions"
                    :key="idx"
                    class="action-item"
                    :class="{ expanded: expandedActions.has(idx) }"
                    @click="toggleAction(idx)"
                  >
                    <div class="action-header">
                      <span class="action-platform" :class="action.platform">{{ action.platform }}</span>
                      <span class="action-type">{{ action.action_type }}</span>
                      <span class="action-round" v-if="action.round_num != null">R{{ action.round_num }}</span>
                      <span class="action-expand-icon">{{ expandedActions.has(idx) ? '−' : '+' }}</span>
                    </div>
                    <div class="action-content" :class="{ 'action-content-full': expandedActions.has(idx) }" v-if="action.action_args?.content">{{ action.action_args.content }}</div>

                    <!-- Expanded details -->
                    <div v-show="expandedActions.has(idx)" class="action-details">
                      <div class="action-detail-row" v-if="action.timestamp">
                        <span class="action-detail-label">Time</span>
                        <span class="action-detail-value">{{ action.timestamp }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.agent_name">
                        <span class="action-detail-label">Agent</span>
                        <span class="action-detail-value">{{ action.agent_name }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.agent_id != null">
                        <span class="action-detail-label">Agent ID</span>
                        <span class="action-detail-value mono">{{ action.agent_id }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.action_args?.post_id != null">
                        <span class="action-detail-label">Post ID</span>
                        <span class="action-detail-value mono">#{{ action.action_args.post_id }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.action_args?.comment_id != null">
                        <span class="action-detail-label">Comment ID</span>
                        <span class="action-detail-value mono">#{{ action.action_args.comment_id }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.action_args?.target_post_id != null">
                        <span class="action-detail-label">Target Post</span>
                        <span class="action-detail-value mono">#{{ action.action_args.target_post_id }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.action_args?.market_id != null">
                        <span class="action-detail-label">Market</span>
                        <span class="action-detail-value mono">#{{ action.action_args.market_id }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.action_args?.outcome">
                        <span class="action-detail-label">Position</span>
                        <span class="action-detail-value" :class="action.action_args.outcome === 'YES' ? 'text-green' : 'text-orange'">{{ action.action_args.outcome }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.action_args?.cost != null">
                        <span class="action-detail-label">Cost</span>
                        <span class="action-detail-value">${{ action.action_args.cost.toFixed(2) }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.action_args?.shares != null">
                        <span class="action-detail-label">Shares</span>
                        <span class="action-detail-value">{{ action.action_args.shares.toFixed(2) }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.action_args?.price != null">
                        <span class="action-detail-label">Price</span>
                        <span class="action-detail-value">${{ action.action_args.price.toFixed(4) }}</span>
                      </div>
                      <div class="action-detail-row" v-else-if="action.action_args?.usd_received != null && action.action_args?.shares">
                        <span class="action-detail-label">Price</span>
                        <span class="action-detail-value">${{ (action.action_args.usd_received / action.action_args.shares).toFixed(4) }}</span>
                      </div>
                      <div class="action-detail-row" v-if="action.action_args?.usd_received != null">
                        <span class="action-detail-label">Received</span>
                        <span class="action-detail-value text-green">${{ action.action_args.usd_received.toFixed(2) }}</span>
                      </div>
                      <div class="action-detail-row">
                        <span class="action-detail-label">Success</span>
                        <span class="action-detail-value" :class="action.success ? 'text-green' : 'text-orange'">{{ action.success ? 'YES' : 'NO' }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else-if="!agentActionsLoading" class="actions-empty">No actions recorded yet</div>
              </div>
            </div>
          </div>
          
          <!-- Edge Details -->
          <div v-else class="detail-content">
            <!-- Self-loop Group Details -->
            <template v-if="selectedItem.data.isSelfLoopGroup">
              <div class="edge-relation-header self-loop-header">
                {{ selectedItem.data.source_name }} - Self Relations
                <span class="self-loop-count">{{ selectedItem.data.selfLoopCount }} items</span>
              </div>
              
              <div class="self-loop-list">
                <div 
                  v-for="(loop, idx) in selectedItem.data.selfLoopEdges" 
                  :key="loop.uuid || idx" 
                  class="self-loop-item"
                  :class="{ expanded: expandedSelfLoops.has(loop.uuid || idx) }"
                >
                  <div 
                    class="self-loop-item-header"
                    @click="toggleSelfLoop(loop.uuid || idx)"
                  >
                    <span class="self-loop-index">#{{ idx + 1 }}</span>
                    <span class="self-loop-name">{{ loop.name || loop.fact_type || 'RELATED' }}</span>
                    <span class="self-loop-toggle">{{ expandedSelfLoops.has(loop.uuid || idx) ? '−' : '+' }}</span>
                  </div>
                  
                  <div class="self-loop-item-content" v-show="expandedSelfLoops.has(loop.uuid || idx)">
                    <div class="detail-row" v-if="loop.uuid">
                      <span class="detail-label">UUID:</span>
                      <span class="detail-value uuid-text copyable" @click="copyText(loop.uuid)">{{ loop.uuid }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact">
                      <span class="detail-label">Fact:</span>
                      <span class="detail-value fact-text">{{ loop.fact }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact_type">
                      <span class="detail-label">Type:</span>
                      <span class="detail-value">{{ loop.fact_type }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.created_at">
                      <span class="detail-label">Created:</span>
                      <span class="detail-value">{{ formatDateTime(loop.created_at) }}</span>
                    </div>
                    <div v-if="loop.episodes && loop.episodes.length > 0" class="self-loop-episodes">
                      <span class="detail-label">Episodes:</span>
                      <div class="episodes-list compact">
                        <span v-for="ep in loop.episodes" :key="ep" class="episode-tag small">{{ ep }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            
            <!-- Normal Edge Details -->
            <template v-else>
              <div class="edge-relation-header">
                {{ selectedItem.data.source_name }} → {{ selectedItem.data.name || 'RELATED_TO' }} → {{ selectedItem.data.target_name }}
              </div>
              
              <div class="detail-row">
                <span class="detail-label">UUID:</span>
                <span class="detail-value uuid-text copyable" @click="copyText(selectedItem.data.uuid)">{{ selectedItem.data.uuid }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Label:</span>
                <span class="detail-value">{{ selectedItem.data.name || 'RELATED_TO' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Type:</span>
                <span class="detail-value">{{ selectedItem.data.fact_type || 'Unknown' }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.fact">
                <span class="detail-label">Fact:</span>
                <span class="detail-value fact-text">{{ selectedItem.data.fact }}</span>
              </div>
              
              <!-- Episodes -->
              <div class="detail-section" v-if="selectedItem.data.episodes && selectedItem.data.episodes.length > 0">
                <div class="section-title">Episodes:</div>
                <div class="episodes-list">
                  <span v-for="ep in selectedItem.data.episodes" :key="ep" class="episode-tag">
                    {{ ep }}
                  </span>
                </div>
              </div>
              
              <div class="detail-row" v-if="selectedItem.data.created_at">
                <span class="detail-label">Created:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.valid_at">
                <span class="detail-label">Valid From:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.valid_at) }}</span>
              </div>
            </template>
          </div>
        </div>
      </div>
      
      <!-- Loading State -->
      <div v-else-if="loading" class="graph-state">
        <div class="loading-spinner"></div>
        <p>Loading graph data...</p>
      </div>
      
      <!-- Waiting/Empty State -->
      <div v-else class="graph-state">
        <div class="empty-icon">❖</div>
        <p class="empty-text">Waiting for ontology generation...</p>
      </div>
    </div>

    <!-- Bottom Legend (Bottom Left) -->
    <div v-if="graphData && entityTypes.length" class="graph-legend">
      <span class="legend-title">Entity Types</span>
      <div class="legend-items">
        <div
          class="legend-item"
          :class="{ hidden: hiddenTypes.has(type.name) }"
          v-for="type in entityTypes"
          :key="type.name"
          @click="toggleEntityType(type.name)"
        >
          <span class="legend-dot" :style="{ background: hiddenTypes.has(type.name) ? '#CCC' : type.color }"></span>
          <span class="legend-label">{{ type.name }}</span>
        </div>
      </div>
    </div>
    
    <!-- Edge Labels Toggle -->
    <div v-if="graphData" class="graph-toggles">
      <div class="toggle-row">
        <label class="toggle-switch">
          <input type="checkbox" v-model="showLinks" />
          <span class="slider"></span>
        </label>
        <span class="toggle-label">Show Links</span>
      </div>
      <div class="toggle-row">
        <label class="toggle-switch">
          <input type="checkbox" v-model="showEdgeLabels" />
          <span class="slider"></span>
        </label>
        <span class="toggle-label">Show Edge Labels</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import * as d3 from 'd3'
import { getSimulationActions } from '../api/simulation'

const props = defineProps({
  graphData: Object,
  loading: Boolean,
  currentPhase: Number,
  isSimulating: Boolean,
  simulationId: String
})

const emit = defineEmits(['refresh', 'toggle-maximize'])

// Agent actions state
const agentActions = ref([])
const agentActionsLoading = ref(false)
const actionsExpanded = ref(true)
const expandedActions = ref(new Set())

const toggleAction = (idx) => {
  const s = new Set(expandedActions.value)
  if (s.has(idx)) s.delete(idx)
  else s.add(idx)
  expandedActions.value = s
}

const graphContainer = ref(null)
const graphSvg = ref(null)
const selectedItem = ref(null)
const showLinks = ref(true) // Show node links by default
const showEdgeLabels = ref(false) // Show edge labels off by default
const expandedSelfLoops = ref(new Set()) // Expanded self-loop items
const showSimulationFinishedHint = ref(false) // Post-simulation hint
const hideUpdateHint = ref(false)
const hiddenTypes = ref(new Set())

const toggleEntityType = (typeName) => {
  const s = new Set(hiddenTypes.value)
  if (s.has(typeName)) {
    s.delete(typeName)
  } else {
    s.add(typeName)
  }
  hiddenTypes.value = s
}

const copyText = (text) => {
  if (!text) return
  navigator.clipboard.writeText(text)
}
const wasSimulating = ref(false) // Track whether simulation was previously running

// Dismiss simulation finished hint
const dismissFinishedHint = () => {
  showSimulationFinishedHint.value = false
}

// Watch isSimulating changes to detect simulation end
watch(() => props.isSimulating, (newValue, oldValue) => {
  if (wasSimulating.value && !newValue) {
    // Transitioned from simulating to not simulating, show finished hint
    showSimulationFinishedHint.value = true
  }
  wasSimulating.value = newValue
}, { immediate: true })

// Toggle self-loop item expand/collapse state
const toggleSelfLoop = (id) => {
  const newSet = new Set(expandedSelfLoops.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  expandedSelfLoops.value = newSet
}

// Compute entity types for legend
const entityTypes = computed(() => {
  if (!props.graphData?.nodes) return []
  const typeMap = {}
  // Aesthetic color palette
  const colors = ['#FF6B1A', '#43C165', '#0A0A0A', '#FFB347', '#FF4444', '#FF8C42', '#2D9B5E', '#D45B1A', '#7A7A7A', '#B8522E']
  
  props.graphData.nodes.forEach(node => {
    const type = node.labels?.find(l => l !== 'Entity') || 'Entity'
    if (!typeMap[type]) {
      typeMap[type] = { name: type, count: 0, color: colors[Object.keys(typeMap).length % colors.length] }
    }
    typeMap[type].count++
  })
  return Object.values(typeMap)
})

// Format date/time
const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true 
    })
  } catch {
    return dateStr
  }
}

const closeDetailPanel = () => {
  selectedItem.value = null
  expandedSelfLoops.value = new Set()
  agentActions.value = []
  expandedActions.value = new Set()
}

// Fetch agent actions when a node is selected during simulation
const fetchAgentActions = async (agentName) => {
  if (!props.simulationId || !agentName) return
  agentActionsLoading.value = true
  agentActions.value = []
  expandedActions.value = new Set()
  try {
    const res = await getSimulationActions(props.simulationId, { limit: 200 })
    if (res.success && res.data) {
      const all = Array.isArray(res.data) ? res.data : (res.data.actions || [])
      agentActions.value = all.filter(a => a.agent_name === agentName)
    }
  } catch (e) {
    console.warn('Failed to fetch agent actions:', e)
  } finally {
    agentActionsLoading.value = false
  }
}

watch(selectedItem, (item) => {
  if (item?.type === 'node' && props.simulationId) {
    fetchAgentActions(item.data?.name)
  }
})

let currentSimulation = null
let linkLabelsRef = null
let linkLabelBgRef = null

const renderGraph = () => {
  if (!graphSvg.value || !props.graphData) return
  
  // Stop previous simulation
  if (currentSimulation) {
    currentSimulation.stop()
  }
  
  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight
  
  const svg = d3.select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    
  svg.selectAll('*').remove()
  
  const nodesData = props.graphData.nodes || []
  const edgesData = props.graphData.edges || []
  
  if (nodesData.length === 0) return

  // Prep data
  const nodeMap = {}
  nodesData.forEach(n => nodeMap[n.uuid] = n)
  
  const nodes = nodesData.map(n => ({
    id: n.uuid,
    name: n.name || 'Unnamed',
    type: n.labels?.find(l => l !== 'Entity') || 'Entity',
    rawData: n
  }))
  
  const nodeIds = new Set(nodes.map(n => n.id))
  
  // Process edge data, calculate edge count and index between the same pair of nodes
  const edgePairCount = {}
  const selfLoopEdges = {} // Self-loop edges grouped by node
  const tempEdges = edgesData
    .filter(e => nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid))
  
  // Count edges between each pair of nodes, collect self-loop edges
  tempEdges.forEach(e => {
    if (e.source_node_uuid === e.target_node_uuid) {
      // Self-loop - collect into array
      if (!selfLoopEdges[e.source_node_uuid]) {
        selfLoopEdges[e.source_node_uuid] = []
      }
      selfLoopEdges[e.source_node_uuid].push({
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      })
    } else {
      const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
      edgePairCount[pairKey] = (edgePairCount[pairKey] || 0) + 1
    }
  })
  
  // Track current edge index for each pair of nodes
  const edgePairIndex = {}
  const processedSelfLoopNodes = new Set() // Processed self-loop nodes
  
  const edges = []
  
  tempEdges.forEach(e => {
    const isSelfLoop = e.source_node_uuid === e.target_node_uuid
    
    if (isSelfLoop) {
      // Self-loop edge - only add one merged self-loop per node
      if (processedSelfLoopNodes.has(e.source_node_uuid)) {
        return // Already processed, skip
      }
      processedSelfLoopNodes.add(e.source_node_uuid)
      
      const allSelfLoops = selfLoopEdges[e.source_node_uuid]
      const nodeName = nodeMap[e.source_node_uuid]?.name || 'Unknown'
      
      edges.push({
        source: e.source_node_uuid,
        target: e.target_node_uuid,
        type: 'SELF_LOOP',
        name: `Self Relations (${allSelfLoops.length})`,
        curvature: 0,
        isSelfLoop: true,
        rawData: {
          isSelfLoopGroup: true,
          source_name: nodeName,
          target_name: nodeName,
          selfLoopCount: allSelfLoops.length,
          selfLoopEdges: allSelfLoops // Store detailed info for all self-loop edges
        }
      })
      return
    }
    
    const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
    const totalCount = edgePairCount[pairKey]
    const currentIndex = edgePairIndex[pairKey] || 0
    edgePairIndex[pairKey] = currentIndex + 1
    
    // Check if edge direction matches normalized direction (source UUID < target UUID)
    const isReversed = e.source_node_uuid > e.target_node_uuid
    
    // Calculate curvature: spread out for multiple edges, straight line for single edge
    let curvature = 0
    if (totalCount > 1) {
      // Evenly distribute curvature for clear distinction
      // Curvature range increases with more edges
      const curvatureRange = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = ((currentIndex / (totalCount - 1)) - 0.5) * curvatureRange * 2
      
      // If edge direction is opposite to normalized direction, flip curvature
      // This ensures all edges distribute in the same reference frame without overlap
      if (isReversed) {
        curvature = -curvature
      }
    }
    
    edges.push({
      source: e.source_node_uuid,
      target: e.target_node_uuid,
      type: e.fact_type || e.name || 'RELATED',
      name: e.name || e.fact_type || 'RELATED',
      curvature,
      isSelfLoop: false,
      pairIndex: currentIndex,
      pairTotal: totalCount,
      rawData: {
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      }
    })
  })
    
  // Color scale
  const colorMap = {}
  entityTypes.value.forEach(t => colorMap[t.name] = t.color)
  const getColor = (type) => colorMap[type] || '#999'

  // Simulation - dynamically adjust node spacing based on edge count
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(d => {
      // Dynamically adjust distance based on edge count between this pair of nodes
      // Base distance 150, increase by 40 per additional edge
      const baseDistance = 150
      const edgeCount = d.pairTotal || 1
      return baseDistance + (edgeCount - 1) * 50
    }))
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(50))
    // Add gravitational force toward center, keeping isolated node clusters near center
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04))
  
  currentSimulation = simulation

  const g = svg.append('g')
  
  // Zoom
  svg.call(d3.zoom().extent([[0, 0], [width, height]]).scaleExtent([0.1, 4]).on('zoom', (event) => {
    g.attr('transform', event.transform)
  }))

  // Links - use path to support curves
  const linkGroup = g.append('g').attr('class', 'links')
  
  // Calculate curve path
  const getLinkPath = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // Detect self-loop
    if (d.isSelfLoop) {
      // Self-loop: draw an arc from and back to the node
      const loopRadius = 30
      // Start from the right side of the node, loop around and return
      const x1 = sx + 8  // Start offset
      const y1 = sy - 4
      const x2 = sx + 8  // End offset
      const y2 = sy + 4
      // Draw self-loop using arc (sweep-flag=1 clockwise)
      return `M${x1},${y1} A${loopRadius},${loopRadius} 0 1,1 ${x2},${y2}`
    }
    
    if (d.curvature === 0) {
      // Straight line
      return `M${sx},${sy} L${tx},${ty}`
    }
    
    // Calculate curve control point - dynamically adjust based on edge count and distance
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    // Perpendicular offset from the line, calculated proportionally to ensure visible curves
    // More edges = larger offset ratio
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05 // Base 25%, increase 5% per additional edge
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
  }
  
  // Calculate curve midpoint (for label positioning)
  const getLinkMidpoint = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // Detect self-loop
    if (d.isSelfLoop) {
      // Self-loop label position: right side of node
      return { x: sx + 70, y: sy }
    }
    
    if (d.curvature === 0) {
      return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
    }
    
    // Quadratic Bezier curve midpoint at t=0.5
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    // Quadratic Bezier curve formula B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2, t=0.5
    const midX = 0.25 * sx + 0.5 * cx + 0.25 * tx
    const midY = 0.25 * sy + 0.5 * cy + 0.25 * ty
    
    return { x: midX, y: midY }
  }
  
  const link = linkGroup.selectAll('path')
    .data(edges)
    .enter().append('path')
    .attr('stroke', 'rgba(250,250,250,0.15)')
    .attr('stroke-width', 1.5)
    .attr('fill', 'none')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      // Reset previously selected edge styles
      linkGroup.selectAll('path').attr('stroke', 'rgba(250,250,250,0.15)').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(10,10,10,0.85)')
      linkLabels.attr('fill', 'rgba(250,250,250,0.5)')
      // Highlight currently selected edge
      d3.select(event.target).attr('stroke', '#FF6B1A').attr('stroke-width', 3)
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  // Link labels background (white background for clearer text)
  const linkLabelBg = linkGroup.selectAll('rect')
    .data(edges)
    .enter().append('rect')
    .attr('fill', 'rgba(10,10,10,0.85)')
    .attr('rx', 0)
    .attr('ry', 0)
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', 'rgba(250,250,250,0.15)').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(10,10,10,0.85)')
      linkLabels.attr('fill', 'rgba(250,250,250,0.5)')
      // Highlight corresponding edge
      link.filter(l => l === d).attr('stroke', '#FF6B1A').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', 'rgba(255, 107, 26, 0.1)')
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  // Link labels
  const linkLabels = linkGroup.selectAll('text')
    .data(edges)
    .enter().append('text')
    .text(d => d.name)
    .attr('font-size', '9px')
    .attr('fill', 'rgba(250,250,250,0.5)')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('font-family', "'Space Mono', 'Courier New', monospace")
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', 'rgba(250,250,250,0.15)').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(10,10,10,0.85)')
      linkLabels.attr('fill', 'rgba(250,250,250,0.5)')
      // Highlight corresponding edge
      link.filter(l => l === d).attr('stroke', '#FF6B1A').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', '#FF6B1A')

      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  // Save references for external show/hide control
  linkLabelsRef = linkLabels
  linkLabelBgRef = linkLabelBg

  // Nodes group
  const nodeGroup = g.append('g').attr('class', 'nodes')
  
  // Node circles
  const node = nodeGroup.selectAll('circle')
    .data(nodes)
    .enter().append('circle')
    .attr('r', 10)
    .attr('fill', d => getColor(d.type))
    .attr('data-entity-type', d => d.type)
    .attr('stroke', 'rgba(10,10,10,0.6)')
    .attr('stroke-width', 2.5)
    .style('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (event, d) => {
        // Only record position, don't restart simulation (distinguish click from drag)
        d.fx = d.x
        d.fy = d.y
        d._dragStartX = event.x
        d._dragStartY = event.y
        d._isDragging = false
      })
      .on('drag', (event, d) => {
        // Detect if actual dragging has started (moved beyond threshold)
        const dx = event.x - d._dragStartX
        const dy = event.y - d._dragStartY
        const distance = Math.sqrt(dx * dx + dy * dy)
        
        if (!d._isDragging && distance > 3) {
          // First real drag detected, restart simulation
          d._isDragging = true
          simulation.alphaTarget(0.3).restart()
        }
        
        if (d._isDragging) {
          d.fx = event.x
          d.fy = event.y
        }
      })
      .on('end', (event, d) => {
        // Only gradually stop simulation if actual dragging occurred
        if (d._isDragging) {
          simulation.alphaTarget(0)
        }
        d.fx = null
        d.fy = null
        d._isDragging = false
      })
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      // Reset all node styles
      node.attr('stroke', 'rgba(10,10,10,0.6)').attr('stroke-width', 2.5)
      linkGroup.selectAll('path').attr('stroke', 'rgba(250,250,250,0.15)').attr('stroke-width', 1.5)
      // Highlight selected node
      d3.select(event.target).attr('stroke', '#FF6B1A').attr('stroke-width', 4)
      // Highlight edges connected to this node
      link.filter(l => l.source.id === d.id || l.target.id === d.id)
        .attr('stroke', '#FF6B1A')
        .attr('stroke-width', 2.5)
      
      selectedItem.value = {
        type: 'node',
        data: d.rawData,
        entityType: d.type,
        color: getColor(d.type)
      }
    })
    .on('mouseenter', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.uuid !== d.rawData.uuid) {
        d3.select(event.target).attr('stroke', 'rgba(250,250,250,0.5)').attr('stroke-width', 3)
      }
    })
    .on('mouseleave', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.uuid !== d.rawData.uuid) {
        d3.select(event.target).attr('stroke', 'rgba(10,10,10,0.6)').attr('stroke-width', 2.5)
      }
    })

  // Node Labels
  const nodeLabels = nodeGroup.selectAll('text')
    .data(nodes)
    .enter().append('text')
    .text(d => d.name.length > 8 ? d.name.substring(0, 8) + '…' : d.name)
    .attr('font-size', '11px')
    .attr('fill', 'rgba(250,250,250,0.8)')
    .attr('font-weight', '500')
    .attr('dx', 14)
    .attr('dy', 4)
    .attr('data-entity-type', d => d.type)
    .style('pointer-events', 'none')
    .style('font-family', "'Space Mono', 'Courier New', monospace")

  simulation.on('tick', () => {
    // Update curve paths
    link.attr('d', d => getLinkPath(d))
    
    // Update edge label positions (no rotation, horizontal for better readability)
    linkLabels.each(function(d) {
      const mid = getLinkMidpoint(d)
      d3.select(this)
        .attr('x', mid.x)
        .attr('y', mid.y)
        .attr('transform', '') // Remove rotation, keep horizontal
    })
    
    // Update edge label backgrounds
    linkLabelBg.each(function(d, i) {
      const mid = getLinkMidpoint(d)
      const textEl = linkLabels.nodes()[i]
      const bbox = textEl.getBBox()
      d3.select(this)
        .attr('x', mid.x - bbox.width / 2 - 4)
        .attr('y', mid.y - bbox.height / 2 - 2)
        .attr('width', bbox.width + 8)
        .attr('height', bbox.height + 4)
        .attr('transform', '') // Remove rotation
    })

    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)

    nodeLabels
      .attr('x', d => d.x)
      .attr('y', d => d.y)
  })
  
  // Click on blank area to close detail panel
  svg.on('click', () => {
    selectedItem.value = null
    node.attr('stroke', 'rgba(10,10,10,0.6)').attr('stroke-width', 2.5)
    linkGroup.selectAll('path').attr('stroke', 'rgba(250,250,250,0.15)').attr('stroke-width', 1.5)
    linkLabelBg.attr('fill', 'rgba(10,10,10,0.85)')
    linkLabels.attr('fill', 'rgba(250,250,250,0.5)')
  })
}

watch(() => props.graphData, () => {
  nextTick(renderGraph)
}, { deep: true })

// Watch edge labels display toggle
watch(hiddenTypes, (hidden) => {
  if (!graphSvg.value) return
  const svg = d3.select(graphSvg.value)

  const isHiddenNode = d => hidden.has(d.type)
  const isHiddenEdge = d => {
    if (!d) return false
    const srcType = d.source?.type || d.sourceType
    const tgtType = d.target?.type || d.targetType
    return (srcType && hidden.has(srcType)) || (tgtType && hidden.has(tgtType))
  }

  // Hide/show nodes and labels
  svg.selectAll('circle[data-entity-type]')
    .style('display', d => isHiddenNode(d) ? 'none' : null)

  svg.selectAll('text[data-entity-type]')
    .style('display', d => isHiddenNode(d) ? 'none' : null)

  // Hide/show edges connected to hidden nodes
  svg.selectAll('path').each(function(d) {
    if (d && (d.source || d.sourceType)) {
      d3.select(this).style('display', isHiddenEdge(d) ? 'none' : null)
    }
  })

  svg.selectAll('rect').each(function(d) {
    if (d && (d.source || d.sourceType)) {
      d3.select(this).style('display', isHiddenEdge(d) ? 'none' : null)
    }
  })

  svg.selectAll('.link-label, .link-label-bg').each(function(d) {
    if (d) {
      d3.select(this).style('display', isHiddenEdge(d) ? 'none' : null)
    }
  })
}, { deep: true })

watch(showLinks, (newVal) => {
  if (!graphSvg.value) return
  const svg = d3.select(graphSvg.value)
  svg.selectAll('.links path, .links line').style('display', newVal ? null : 'none')
  svg.selectAll('.link-label, .link-label-bg, rect').each(function(d) {
    if (d && (d.source || d.sourceType)) {
      d3.select(this).style('display', newVal ? null : 'none')
    }
  })
})

watch(showEdgeLabels, (newVal) => {
  if (linkLabelsRef) {
    linkLabelsRef.style('display', newVal ? 'block' : 'none')
  }
  if (linkLabelBgRef) {
    linkLabelBgRef.style('display', newVal ? 'block' : 'none')
  }
})

const handleResize = () => {
  nextTick(renderGraph)
}

let resizeObserver = null

onMounted(() => {
  window.addEventListener('resize', handleResize)
  // Re-render when container becomes visible (e.g. switching from workbench to graph view)
  if (graphContainer.value) {
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0 && entry.contentRect.height > 0 && props.graphData) {
          nextTick(renderGraph)
        }
      }
    })
    resizeObserver.observe(graphContainer.value)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
  if (currentSimulation) {
    currentSimulation.stop()
  }
})
</script>

<style scoped>
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #0A0A0A;
  background-image:
    linear-gradient(rgba(67,193,101,0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(67,193,101,0.06) 1px, transparent 1px);
  background-size: 70px 70px;
  overflow: hidden;
}

/* Corner markers */
.graph-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #FF6B1A 40px, transparent 40px, transparent calc(100% - 40px), #FF6B1A calc(100% - 40px));
  z-index: 30;
  pointer-events: none;
}

.graph-panel::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #43C165 40px, transparent 40px, transparent calc(100% - 40px), #43C165 calc(100% - 40px));
  z-index: 30;
  pointer-events: none;
}

.panel-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 16px 20px;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to bottom, rgba(10,10,10,0.95), rgba(10,10,10,0));
  pointer-events: none;
}

.panel-title {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: rgba(250,250,250,0.5);
  text-transform: uppercase;
  letter-spacing: 3px;
  pointer-events: auto;
}

.header-tools {
  pointer-events: auto;
  display: flex;
  gap: 10px;
  align-items: center;
}

.tool-btn {
  height: 32px;
  padding: 0 12px;
  border: 2px solid rgba(250,250,250,0.12);
  background: rgba(10,10,10,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  color: rgba(250,250,250,0.5);
  transition: all 0.2s;
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.tool-btn:hover {
  background: rgba(250,250,250,0.1);
  color: #FAFAFA;
  border-color: #FF6B1A;
}

.tool-btn .btn-text {
  font-size: 11px;
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.icon-refresh.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.graph-container {
  width: 100%;
  height: 100%;
}

.graph-view, .graph-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.graph-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: rgba(250,250,250,0.4);
  font-family: var(--font-mono);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.2;
}

/* Entity Types Legend - Bottom Left */
.graph-legend {
  position: absolute;
  bottom: 24px;
  left: 24px;
  background: rgba(10,10,10,0.85);
  backdrop-filter: blur(8px);
  padding: 12px 16px;
  border: 2px solid rgba(250,250,250,0.08);
  z-index: 10;
}

.legend-title {
  display: block;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: #FF6B1A;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  max-width: 320px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(250,250,250,0.5);
  cursor: pointer;
  user-select: none;
  transition: opacity 0.15s;
}

.legend-item:hover {
  opacity: 0.8;
}

.legend-item.hidden {
  opacity: 0.4;
}

.legend-item.hidden .legend-label {
  text-decoration: line-through;
}

.legend-dot {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
}

.legend-label {
  white-space: nowrap;
}

/* Graph Toggles - Top Right */
.graph-toggles {
  position: absolute;
  top: 60px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: rgba(10,10,10,0.85);
  backdrop-filter: blur(8px);
  padding: 8px 14px;
  border: 2px solid rgba(250,250,250,0.08);
  z-index: 10;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(250,250,250,0.15);
  transition: 0.3s;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: rgba(250,250,250,0.7);
  transition: 0.3s;
}

input:checked + .slider {
  background-color: #FF6B1A;
}

input:checked + .slider:before {
  transform: translateX(18px);
}

.toggle-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(250,250,250,0.5);
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* Detail Panel - Right Side */
.detail-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 320px;
  max-height: calc(100% - 100px);
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  overflow: hidden;
  font-family: var(--font-mono);
  font-size: 13px;
  z-index: 20;
  display: flex;
  flex-direction: column;
}

.detail-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: var(--color-gray);
  border-bottom: 2px solid rgba(10,10,10,0.08);
  flex-shrink: 0;
}

.detail-title {
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.detail-type-badge {
  padding: 4px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  margin-left: auto;
  margin-right: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.detail-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: rgba(10,10,10,0.4);
  line-height: 1;
  padding: 0;
  transition: color 0.2s;
}

.detail-close:hover {
  color: rgba(10,10,10,0.7);
}

.detail-content {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.detail-row {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.detail-label {
  color: rgba(10,10,10,0.4);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  min-width: 80px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.detail-value {
  color: rgba(10,10,10,0.7);
  flex: 1;
  word-break: break-word;
}

.detail-value.uuid-text {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.5);
}

.detail-value.uuid-text.copyable {
  cursor: pointer;
}

.detail-value.uuid-text.copyable:hover {
  color: #0A0A0A;
  text-decoration: underline;
}

.detail-value.uuid-text.copyable:active {
  color: #43C165;
}

.detail-value.fact-text {
  line-height: 1.5;
  color: rgba(10,10,10,0.6);
}

.detail-section {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 2px solid rgba(10,10,10,0.08);
}

.section-title {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: rgba(10,10,10,0.5);
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 2px;
}

.properties-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.property-item {
  display: flex;
  gap: 8px;
}

.property-key {
  color: rgba(10,10,10,0.4);
  font-family: var(--font-mono);
  font-weight: 500;
  min-width: 90px;
}

.property-value {
  color: rgba(10,10,10,0.7);
  flex: 1;
}

.summary-text {
  line-height: 1.6;
  color: rgba(10,10,10,0.6);
  font-size: 12px;
}

.labels-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.label-tag {
  display: inline-block;
  padding: 4px 12px;
  background: var(--color-gray);
  border: 2px solid rgba(10,10,10,0.12);
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.5);
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* Agent Actions */
.actions-title {
  display: flex;
  align-items: center;
  gap: 8px;
  user-select: none;
}

.actions-toggle {
  font-size: 9px;
  color: rgba(10,10,10,0.4);
  width: 12px;
}

.actions-loading {
  font-size: 10px;
  color: #FF6B1A;
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

.actions-count {
  font-size: 10px;
  background: #FF6B1A;
  color: #FAFAFA;
  padding: 1px 6px;
  font-family: var(--font-mono);
}

.agent-actions-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 400px;
  overflow-y: auto;
  margin-top: 8px;
}

.agent-actions-list::-webkit-scrollbar { width: 4px; }
.agent-actions-list::-webkit-scrollbar-thumb { background: rgba(10,10,10,0.12); }

.action-item {
  padding: 10px;
  border: 2px solid rgba(10,10,10,0.06);
  background: #FAFAFA;
  transition: border-color 0.15s;
  cursor: pointer;
}

.action-item:hover {
  border-color: rgba(10,10,10,0.15);
}

.action-item.expanded {
  border-color: #FF6B1A;
}

.action-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.action-platform {
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 700;
  padding: 2px 6px;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: #FAFAFA;
  background: #0A0A0A;
}

.action-platform.twitter { background: #0A0A0A; }
.action-platform.reddit { background: #FF6B1A; }

.action-type {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.5);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.action-round {
  font-family: var(--font-mono);
  font-size: 10px;
  color: #FF6B1A;
  font-weight: 700;
}

.action-expand-icon {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 14px;
  color: rgba(10,10,10,0.3);
  width: 16px;
  text-align: center;
}

.action-content {
  font-size: 12px;
  color: rgba(10,10,10,0.7);
  line-height: 1.5;
  margin-top: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.action-content-full {
  display: block;
  -webkit-line-clamp: unset;
}

/* Expanded action details */
.action-details {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed rgba(10,10,10,0.08);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.action-detail-row {
  display: flex;
  gap: 8px;
  font-size: 11px;
  align-items: baseline;
}

.action-detail-label {
  font-family: var(--font-mono);
  font-size: 9px;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 2px;
  min-width: 70px;
  flex-shrink: 0;
}

.action-detail-value {
  color: rgba(10,10,10,0.7);
  word-break: break-all;
}

.action-detail-value.mono {
  font-family: var(--font-mono);
  font-size: 10px;
}

.action-detail-value.text-green { color: #43C165; font-weight: 700; }
.action-detail-value.text-orange { color: #FF6B1A; font-weight: 700; }

.reasoning-text {
  font-size: 11px;
  line-height: 1.5;
  color: rgba(10,10,10,0.6);
  font-style: italic;
}

.actions-empty {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.35);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 16px 0;
}

.episodes-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.episode-tag {
  display: inline-block;
  padding: 6px 10px;
  background: var(--color-gray);
  border: 2px solid rgba(10,10,10,0.08);
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.5);
  word-break: break-all;
}

/* Edge relation header */
.edge-relation-header {
  background: var(--color-gray);
  padding: 12px;
  border: 2px solid rgba(10,10,10,0.08);
  margin-bottom: 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  color: rgba(10,10,10,0.7);
  line-height: 1.5;
  word-break: break-word;
}

/* Building hint */
.graph-building-hint {
  position: absolute;
  bottom: 160px;
  left: 50%;
  transform: translateX(-50%);
  background: #0A0A0A;
  backdrop-filter: blur(8px);
  color: #FAFAFA;
  padding: 10px 20px;
  font-family: var(--font-mono);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 2px solid rgba(250,250,250,0.1);
  font-weight: 500;
  letter-spacing: 1px;
  text-transform: uppercase;
  z-index: 100;
}

.hint-close {
  cursor: pointer;
  font-size: 16px;
  opacity: 0.6;
  margin-left: 4px;
  line-height: 1;
}

.hint-close:hover {
  opacity: 1;
}

.memory-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  animation: breathe 2s ease-in-out infinite;
}

.memory-icon {
  width: 18px;
  height: 18px;
  color: #43C165;
}

@keyframes breathe {
  0%, 100% { opacity: 0.7; transform: scale(1); filter: drop-shadow(0 0 2px rgba(67, 193, 101, 0.3)); }
  50% { opacity: 1; transform: scale(1.15); filter: drop-shadow(0 0 8px rgba(67, 193, 101, 0.6)); }
}

/* Post-simulation hint styles */
.graph-building-hint.finished-hint {
  background: #0A0A0A;
  border: 2px solid rgba(250,250,250,0.1);
}

.finished-hint .hint-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
}

.finished-hint .hint-icon {
  width: 18px;
  height: 18px;
  color: #FF6B1A;
}

.finished-hint .hint-text {
  flex: 1;
  white-space: nowrap;
}

.hint-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: rgba(250, 250, 250, 0.2);
  border: none;
  cursor: pointer;
  color: #FAFAFA;
  transition: all 0.2s;
  margin-left: 8px;
  flex-shrink: 0;
}

.hint-close-btn:hover {
  background: rgba(250, 250, 250, 0.35);
}

/* Loading spinner */
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(250,250,250,0.12);
  border-top-color: #FF6B1A;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

/* Self-loop styles */
.self-loop-header {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(67, 193, 101, 0.08);
  border: 2px solid rgba(67, 193, 101, 0.2);
}

.self-loop-count {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.5);
  background: rgba(250,250,250,0.8);
  padding: 2px 8px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.self-loop-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.self-loop-item {
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
}

.self-loop-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--color-gray);
  cursor: pointer;
  transition: background 0.2s;
}

.self-loop-item-header:hover {
  background: rgba(10,10,10,0.06);
}

.self-loop-item.expanded .self-loop-item-header {
  background: rgba(10,10,10,0.08);
}

.self-loop-index {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  background: rgba(10,10,10,0.12);
  padding: 2px 6px;
}

.self-loop-name {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  color: rgba(10,10,10,0.7);
  flex: 1;
}

.self-loop-toggle {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  background: rgba(10,10,10,0.12);
  transition: all 0.2s;
}

.self-loop-item.expanded .self-loop-toggle {
  background: rgba(10,10,10,0.15);
  color: rgba(10,10,10,0.5);
}

.self-loop-item-content {
  padding: 12px;
  border-top: 2px solid rgba(10,10,10,0.08);
}

.self-loop-item-content .detail-row {
  margin-bottom: 8px;
}

.self-loop-item-content .detail-label {
  font-size: 10px;
  min-width: 60px;
}

.self-loop-item-content .detail-value {
  font-size: 12px;
}

.self-loop-episodes {
  margin-top: 8px;
}

.episodes-list.compact {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 4px;
}

.episode-tag.small {
  padding: 3px 6px;
  font-size: 9px;
}
</style>
