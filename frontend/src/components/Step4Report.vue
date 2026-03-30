<template>
  <div class="report-panel">
    <!-- Main Split Layout -->
    <div class="main-split-layout">
      <!-- LEFT PANEL: Report Style -->
      <div class="left-panel report-style" ref="leftPanel">
        <div v-if="reportOutline" class="report-content-wrapper">
          <!-- Report Header -->
          <div class="report-header-block">
            <div class="report-meta">
              <span class="report-tag">Prediction Report</span>
              <span class="report-id copyable" @click="copyReportId">ID: {{ reportId || 'REF-2024-X92' }}</span>
            </div>
            <h1 class="main-title">{{ reportOutline.title }}</h1>
            <p class="sub-title">{{ reportOutline.summary }}</p>
            <div class="header-divider"></div>
          </div>

          <!-- Sections List -->
          <div class="sections-list">
            <div 
              v-for="(section, idx) in reportOutline.sections" 
              :key="idx"
              class="report-section-item"
              :class="{ 
                'is-active': currentSectionIndex === idx + 1,
                'is-completed': isSectionCompleted(idx + 1),
                'is-pending': !isSectionCompleted(idx + 1) && currentSectionIndex !== idx + 1
              }"
            >
              <div class="section-header-row" @click="toggleSectionCollapse(idx)" :class="{ 'clickable': isSectionCompleted(idx + 1) }">
                <span class="section-number">{{ String(idx + 1).padStart(2, '0') }}</span>
                <h3 class="section-title">{{ section.title }}</h3>
                <svg 
                  v-if="isSectionCompleted(idx + 1)" 
                  class="collapse-icon" 
                  :class="{ 'is-collapsed': collapsedSections.has(idx) }"
                  viewBox="0 0 24 24" 
                  width="20" 
                  height="20" 
                  fill="none" 
                  stroke="currentColor" 
                  stroke-width="2"
                >
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </div>
              
              <div class="section-body" v-show="!collapsedSections.has(idx)">
                <!-- Completed Content -->
                <div v-if="generatedSections[idx + 1]" class="generated-content" v-html="renderMarkdown(generatedSections[idx + 1])"></div>
                
                <!-- Loading State -->
                <div v-else-if="currentSectionIndex === idx + 1" class="loading-state">
                  <div class="loading-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <circle cx="12" cy="12" r="10" stroke-width="4" stroke="#E5E7EB"></circle>
                      <path d="M12 2a10 10 0 0 1 10 10" stroke-width="4" stroke="#4B5563" stroke-linecap="round"></path>
                    </svg>
                  </div>
                  <span class="loading-text">Generating {{ section.title }}...</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Waiting State -->
        <div v-if="!reportOutline" class="waiting-placeholder">
          <div class="waiting-animation">
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
            <div class="waiting-ring"></div>
          </div>
          <span class="waiting-text">Waiting for Report Agent...</span>
        </div>
      </div>

      <!-- RIGHT PANEL: Workflow Timeline -->
      <div class="right-panel" ref="rightPanel">
        <div class="panel-header" :class="`panel-header--${activeStep.status}`" v-if="!isComplete">
          <span class="header-dot" v-if="activeStep.status === 'active'"></span>
          <span class="header-index mono">{{ activeStep.noLabel }}</span>
          <span class="header-title">{{ activeStep.title }}</span>
          <span class="header-meta mono" v-if="activeStep.meta">{{ activeStep.meta }}</span>
        </div>

        <!-- Workflow Overview (flat, status-based palette) -->
        <div class="workflow-overview" v-if="agentLogs.length > 0 || reportOutline">
          <div class="workflow-metrics">
            <div class="metric">
              <span class="metric-label">Sections</span>
              <span class="metric-value mono">{{ completedSections }}/{{ totalSections }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Elapsed</span>
              <span class="metric-value mono">{{ formatElapsedTime }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Tools</span>
              <span class="metric-value mono">{{ totalToolCalls }}</span>
            </div>
            <div class="metric metric-right">
              <span class="metric-pill" :class="`pill--${statusClass}`">{{ statusText }}</span>
            </div>
          </div>

          <div class="workflow-steps" v-if="workflowSteps.length > 0">
            <div
              v-for="(step, sidx) in workflowSteps"
              :key="step.key"
              class="wf-step"
              :class="`wf-step--${step.status}`"
            >
              <div class="wf-step-connector">
                <div class="wf-step-dot"></div>
                <div class="wf-step-line" v-if="sidx < workflowSteps.length - 1"></div>
              </div>

              <div class="wf-step-content">
                <div class="wf-step-title-row">
                  <span class="wf-step-index mono">{{ step.noLabel }}</span>
                  <span class="wf-step-title">{{ step.title }}</span>
                  <span class="wf-step-meta mono" v-if="step.meta">{{ step.meta }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Next Step Button - shown after completion -->
          <button v-if="isComplete" class="next-step-btn" @click="goToInteraction">
            <span>Enter Deep Interaction</span>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </button>

          <!-- Export Buttons - shown after completion -->
          <div v-if="isComplete" class="export-buttons">
            <button class="export-btn" @click="downloadExport('json')" :disabled="isExporting">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              <span>{{ isExporting === 'json' ? 'Exporting...' : 'Export JSON' }}</span>
            </button>
            <button class="export-btn" @click="downloadExport('csv')" :disabled="isExporting">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              <span>{{ isExporting === 'csv' ? 'Exporting...' : 'Export CSV' }}</span>
            </button>
          </div>

          <div class="workflow-divider"></div>
        </div>

        <div class="workflow-timeline">
          <TransitionGroup name="timeline-item">
            <div 
              v-for="(log, idx) in displayLogs" 
              :key="log.timestamp + '-' + idx"
              class="timeline-item"
              :class="getTimelineItemClass(log, idx, displayLogs.length)"
            >
              <!-- Timeline Connector -->
              <div class="timeline-connector">
                <div class="connector-dot" :class="getConnectorClass(log, idx, displayLogs.length)"></div>
                <div class="connector-line" v-if="idx < displayLogs.length - 1"></div>
              </div>
              
              <!-- Timeline Content -->
              <div class="timeline-content">
                <div class="timeline-header">
                  <span class="action-label">{{ getActionLabel(log.action) }}</span>
                  <span class="action-time">{{ formatTime(log.timestamp) }}</span>
                </div>
                
                <!-- Action Body - Different for each type -->
                <div class="timeline-body" :class="{ 'collapsed': isLogCollapsed(log) }" @click="toggleLogExpand(log)">
                  
                  <!-- Report Start -->
                  <template v-if="log.action === 'report_start'">
                    <div class="info-row">
                      <span class="info-key">Simulation</span>
                      <span class="info-val mono">{{ log.details?.simulation_id }}</span>
                    </div>
                    <div class="info-row" v-if="log.details?.simulation_requirement">
                      <span class="info-key">Requirement</span>
                      <span class="info-val">{{ log.details.simulation_requirement }}</span>
                    </div>
                  </template>

                  <!-- Planning -->
                  <template v-if="log.action === 'planning_start'">
                    <div class="status-message planning">{{ log.details?.message }}</div>
                  </template>
                  <template v-if="log.action === 'planning_complete'">
                    <div class="status-message success">{{ log.details?.message }}</div>
                    <div class="outline-badge" v-if="log.details?.outline">
                      {{ log.details.outline.sections?.length || 0 }} sections planned
                    </div>
                  </template>

                  <!-- Section Start -->
                  <template v-if="log.action === 'section_start'">
                    <div class="section-tag">
                      <span class="tag-num">#{{ log.section_index }}</span>
                      <span class="tag-title">{{ log.section_title }}</span>
                    </div>
                  </template>
                  
                  <!-- Section Content Generated (Content generated, but the entire section may not be complete) -->
                  <template v-if="log.action === 'section_content'">
                    <div class="section-tag content-ready">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 20h9"></path>
                        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                      </svg>
                      <span class="tag-title">{{ log.section_title }}</span>
                    </div>
                  </template>

                  <!-- Section Complete (Section generation complete) -->
                  <template v-if="log.action === 'section_complete'">
                    <div class="section-tag completed">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                      <span class="tag-title">{{ log.section_title }}</span>
                    </div>
                  </template>

                  <!-- Tool Call -->
                  <template v-if="log.action === 'tool_call'">
                    <div class="tool-badge" :class="'tool-' + getToolColor(log.details?.tool_name)">
                      <!-- Deep Insight - Lightbulb -->
                      <svg v-if="getToolIcon(log.details?.tool_name) === 'lightbulb'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12.5V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.5A7 7 0 0 0 12 2z"></path>
                      </svg>
                      <!-- Panorama Search - Globe -->
                      <svg v-else-if="getToolIcon(log.details?.tool_name) === 'globe'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                      </svg>
                      <!-- Agent Interview - Users -->
                      <svg v-else-if="getToolIcon(log.details?.tool_name) === 'users'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                        <circle cx="9" cy="7" r="4"></circle>
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"></path>
                      </svg>
                      <!-- Quick Search - Zap -->
                      <svg v-else-if="getToolIcon(log.details?.tool_name) === 'zap'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                      </svg>
                      <!-- Graph Stats - Chart -->
                      <svg v-else-if="getToolIcon(log.details?.tool_name) === 'chart'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="20" x2="18" y2="10"></line>
                        <line x1="12" y1="20" x2="12" y2="4"></line>
                        <line x1="6" y1="20" x2="6" y2="14"></line>
                      </svg>
                      <!-- Entity Query - Database -->
                      <svg v-else-if="getToolIcon(log.details?.tool_name) === 'database'" class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                      </svg>
                      <!-- Default - Tool -->
                      <svg v-else class="tool-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
                      </svg>
                      {{ getToolDisplayName(log.details?.tool_name) }}
                    </div>
                    <div v-if="log.details?.parameters && expandedLogs.has(log.timestamp)" class="tool-params">
                      <pre>{{ formatParams(log.details.parameters) }}</pre>
                    </div>
                  </template>

                  <!-- Tool Result -->
                  <template v-if="log.action === 'tool_result'">
                    <div class="result-wrapper" :class="'result-' + log.details?.tool_name">
                      <!-- Hide result-meta for tools that show stats in their own header -->
                      <div v-if="!['interview_agents', 'insight_forge', 'panorama_search', 'quick_search'].includes(log.details?.tool_name)" class="result-meta">
                        <span class="result-tool">{{ getToolDisplayName(log.details?.tool_name) }}</span>
                        <span class="result-size">{{ formatResultSize(log.details?.result_length) }}</span>
                      </div>
                      
                      <!-- Structured Result Display -->
                      <div v-if="!showRawResult[log.timestamp]" class="result-structured">
                        <!-- Interview Agents - Special Display -->
                        <template v-if="log.details?.tool_name === 'interview_agents'">
                          <InterviewDisplay :result="parseInterview(log.details.result)" :result-length="log.details?.result_length" />
                        </template>
                        
                        <!-- Insight Forge -->
                        <template v-else-if="log.details?.tool_name === 'insight_forge'">
                          <InsightDisplay :result="parseInsightForge(log.details.result)" :result-length="log.details?.result_length" />
                        </template>
                        
                        <!-- Panorama Search -->
                        <template v-else-if="log.details?.tool_name === 'panorama_search'">
                          <PanoramaDisplay :result="parsePanorama(log.details.result)" :result-length="log.details?.result_length" />
                        </template>
                        
                        <!-- Quick Search -->
                        <template v-else-if="log.details?.tool_name === 'quick_search'">
                          <QuickSearchDisplay :result="parseQuickSearch(log.details.result)" :result-length="log.details?.result_length" />
                        </template>
                        
                        <!-- Default -->
                        <template v-else>
                          <pre class="raw-preview">{{ truncateText(log.details?.result, 300) }}</pre>
                        </template>
                      </div>
                      
                      <!-- Raw Result -->
                      <div v-else class="result-raw">
                        <pre>{{ log.details?.result }}</pre>
                      </div>
                    </div>
                  </template>

                  <!-- LLM Response -->
                  <template v-if="log.action === 'llm_response'">
                    <div class="llm-meta">
                      <span class="meta-tag">Iteration {{ log.details?.iteration }}</span>
                      <span class="meta-tag" :class="{ active: log.details?.has_tool_calls }">
                        Tools: {{ log.details?.has_tool_calls ? 'Yes' : 'No' }}
                      </span>
                      <span class="meta-tag" :class="{ active: log.details?.has_final_answer, 'final-answer': log.details?.has_final_answer }">
                        Final: {{ log.details?.has_final_answer ? 'Yes' : 'No' }}
                      </span>
                    </div>
                    <!-- Show special hint when this is the final answer -->
                    <div v-if="log.details?.has_final_answer" class="final-answer-hint">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                      <span>Section "{{ log.section_title }}" content generated</span>
                    </div>
                    <div v-if="expandedLogs.has(log.timestamp) && log.details?.response" class="llm-content">
                      <pre>{{ log.details.response }}</pre>
                    </div>
                  </template>

                  <!-- Report Complete -->
                  <template v-if="log.action === 'report_complete'">
                    <div class="complete-banner">
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                      </svg>
                      <span>Report Generation Complete</span>
                    </div>
                  </template>
                </div>

                <!-- Footer: Elapsed Time + Action Buttons -->
                <div class="timeline-footer" v-if="log.elapsed_seconds || (log.action === 'tool_call' && log.details?.parameters) || log.action === 'tool_result' || (log.action === 'llm_response' && log.details?.response)">
                  <span v-if="log.elapsed_seconds" class="elapsed-badge">+{{ log.elapsed_seconds.toFixed(1) }}s</span>
                  <span v-else class="elapsed-placeholder"></span>
                  
                  <div class="footer-actions">
                    <!-- Tool Call: Show/Hide Params -->
                    <button v-if="log.action === 'tool_call' && log.details?.parameters" class="action-btn" @click.stop="toggleLogExpand(log)">
                      {{ expandedLogs.has(log.timestamp) ? 'Hide Params' : 'Show Params' }}
                    </button>
                    
                    <!-- Tool Result: Raw/Structured View -->
                    <button v-if="log.action === 'tool_result'" class="action-btn" @click.stop="toggleRawResult(log.timestamp, $event)">
                      {{ showRawResult[log.timestamp] ? 'Structured View' : 'Raw Output' }}
                    </button>
                    
                    <!-- LLM Response: Show/Hide Response -->
                    <button v-if="log.action === 'llm_response' && log.details?.response" class="action-btn" @click.stop="toggleLogExpand(log)">
                      {{ expandedLogs.has(log.timestamp) ? 'Hide Response' : 'Show Response' }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </TransitionGroup>

          <!-- Empty State -->
          <div v-if="agentLogs.length === 0 && !isComplete" class="workflow-empty">
            <div class="empty-pulse"></div>
            <span>Waiting for agent activity...</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Console Logs -->
    <div class="console-logs" :class="{ collapsed: consoleCollapsed }">
      <div class="log-header" @click="consoleCollapsed = !consoleCollapsed">
        <span class="log-title">CONSOLE OUTPUT <span class="log-toggle">{{ consoleCollapsed ? '▲' : '▼' }}</span></span>
        <span class="log-id">{{ reportId || 'NO_REPORT' }}</span>
      </div>
      <div v-show="!consoleCollapsed" class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in consoleLogs" :key="idx">
          <span class="log-msg" :class="getLogLevelClass(log)">{{ log }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, h, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { getAgentLog, getConsoleLog } from '../api/report'
import { exportSimulationData } from '../api/simulation'

const router = useRouter()

const props = defineProps({
  reportId: String,
  simulationId: String,
  systemLogs: Array
})

const emit = defineEmits(['add-log', 'update-status'])

const consoleCollapsed = ref(false)

const copyReportId = () => {
  if (props.reportId) navigator.clipboard.writeText(props.reportId)
}

// Navigation
const goToInteraction = () => {
  if (props.reportId) {
    router.push({ name: 'Interaction', params: { reportId: props.reportId } })
  }
}

// State
const agentLogs = ref([])
const consoleLogs = ref([])
const agentLogLine = ref(0)
const consoleLogLine = ref(0)
const reportOutline = ref(null)
const currentSectionIndex = ref(null)
const generatedSections = ref({})
const expandedContent = ref(new Set())
const expandedLogs = ref(new Set())
const collapsedSections = ref(new Set())
const isComplete = ref(false)
const isExporting = ref(false)

// Export simulation data as JSON or CSV
const downloadExport = async (format) => {
  if (!props.simulationId || isExporting.value) return
  isExporting.value = format
  try {
    const response = await exportSimulationData(props.simulationId, format)
    const blob = new Blob([response], { type: format === 'json' ? 'application/json' : 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `miroshark_export_${props.simulationId.slice(0, 12)}.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (err) {
    console.error('Export failed:', err)
  } finally {
    isExporting.value = false
  }
}
const startTime = ref(null)
const leftPanel = ref(null)
const rightPanel = ref(null)
const logContent = ref(null)
const showRawResult = reactive({})

// Toggle functions
const toggleRawResult = (timestamp, event) => {
  // Save button position relative to viewport
  const button = event?.target
  const buttonRect = button?.getBoundingClientRect()
  const buttonTopBeforeToggle = buttonRect?.top
  
  // Toggle state
  showRawResult[timestamp] = !showRawResult[timestamp]
  
  // After waiting for DOM update, adjust scroll position to keep button in same position
  if (button && buttonTopBeforeToggle !== undefined && rightPanel.value) {
    nextTick(() => {
      const newButtonRect = button.getBoundingClientRect()
      const buttonTopAfterToggle = newButtonRect.top
      const scrollDelta = buttonTopAfterToggle - buttonTopBeforeToggle
      
      // Adjust scroll position
      rightPanel.value.scrollTop += scrollDelta
    })
  }
}

const toggleSectionContent = (idx) => {
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(expandedContent.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  expandedContent.value = newSet
}

const toggleSectionCollapse = (idx) => {
  // Only completed sections can be collapsed
  if (!generatedSections.value[idx + 1]) return
  const newSet = new Set(collapsedSections.value)
  if (newSet.has(idx)) {
    newSet.delete(idx)
  } else {
    newSet.add(idx)
  }
  collapsedSections.value = newSet
}

const toggleLogExpand = (log) => {
  const newSet = new Set(expandedLogs.value)
  if (newSet.has(log.timestamp)) {
    newSet.delete(log.timestamp)
  } else {
    newSet.add(log.timestamp)
  }
  expandedLogs.value = newSet
}

const isLogCollapsed = (log) => {
  if (['tool_call', 'tool_result', 'llm_response'].includes(log.action)) {
    return !expandedLogs.value.has(log.timestamp)
  }
  return false
}

// Tool configurations with display names and colors
const toolConfig = {
  'insight_forge': {
    name: 'Deep Insight',
    color: 'purple',
    icon: 'lightbulb' // Lightbulb icon - represents insight
  },
  'panorama_search': {
    name: 'Panorama Search',
    color: 'blue',
    icon: 'globe' // Globe icon - represents panoramic search
  },
  'interview_agents': {
    name: 'Agent Interview',
    color: 'green',
    icon: 'users' // Users icon - represents conversation
  },
  'quick_search': {
    name: 'Quick Search',
    color: 'orange',
    icon: 'zap' // Lightning icon - represents speed
  },
  'get_graph_statistics': {
    name: 'Graph Stats',
    color: 'cyan',
    icon: 'chart' // Chart icon - represents statistics
  },
  'get_entities_by_type': {
    name: 'Entity Query',
    color: 'pink',
    icon: 'database' // Database icon - represents entities
  }
}

const getToolDisplayName = (toolName) => {
  return toolConfig[toolName]?.name || toolName
}

const getToolColor = (toolName) => {
  return toolConfig[toolName]?.color || 'gray'
}

const getToolIcon = (toolName) => {
  return toolConfig[toolName]?.icon || 'tool'
}

// Parse functions
const parseInsightForge = (text) => {
  const result = {
    query: '',
    simulationRequirement: '',
    stats: { facts: 0, entities: 0, relationships: 0 },
    subQueries: [],
    facts: [],
    entities: [],
    relations: []
  }
  
  try {
    // Extract analysis question (match both formats)
    const queryMatch = text.match(/Analysis\s*(?:question|Query):\s*(.+?)(?:\n|$)/i)
    if (queryMatch) result.query = queryMatch[1].trim()

    // Extract prediction scenario
    const reqMatch = text.match(/Prediction\s*(?:scenario|Scenario):\s*(.+?)(?:\n|$)/i)
    if (reqMatch) result.simulationRequirement = reqMatch[1].trim()

    // Extract statistics (match both formats)
    const factMatch = text.match(/(?:Relevant|Related)\s*(?:prediction\s*)?Facts?:\s*(\d+)/i)
    const entityMatch = text.match(/(?:Entities?\s*involved|Involved\s*Entities?):\s*(\d+)/i)
    const relMatch = text.match(/Relationship\s*(?:chains?|Chains?):\s*(\d+)/i)
    if (factMatch) result.stats.facts = parseInt(factMatch[1])
    if (entityMatch) result.stats.entities = parseInt(entityMatch[1])
    if (relMatch) result.stats.relationships = parseInt(relMatch[1])

    // Extract sub-questions
    const subQSection = text.match(/###\s*(?:Analyzed|Analysis)\s*Sub-Questions\n([\s\S]*?)(?=\n###|$)/)
    if (subQSection) {
      const lines = subQSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.subQueries = lines.map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean)
    }

    // Extract key facts
    const factsSection = text.match(/###\s*(?:\[Key Facts\]|Key Facts[^\n]*)\n([\s\S]*?)(?=\n###|$)/)
    if (factsSection) {
      const lines = factsSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.facts = lines.map(l => {
        const match = l.match(/^\d+\.\s*"?(.+?)"?\s*$/)
        return match ? match[1].replace(/^"|"$/g, '').trim() : l.replace(/^\d+\.\s*/, '').trim()
      }).filter(Boolean)
    }

    // Extract core entities
    const entitySection = text.match(/###\s*(?:\[Core Entities\]|Core Entities)\n([\s\S]*?)(?=\n###|$)/)
    if (entitySection) {
      const entityText = entitySection[1]
      // Split entity blocks by "- **"
      const entityBlocks = entityText.split(/\n(?=- \*\*)/).filter(b => b.trim().startsWith('- **'))
      result.entities = entityBlocks.map(block => {
        const nameMatch = block.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        const summaryMatch = block.match(/Summary:\s*"?(.+?)"?(?:\n|$)/)
        const relatedMatch = block.match(/Related facts:\s*(\d+)/)
        return {
          name: nameMatch ? nameMatch[1].trim() : '',
          type: nameMatch ? nameMatch[2].trim() : '',
          summary: summaryMatch ? summaryMatch[1].trim() : '',
          relatedFactsCount: relatedMatch ? parseInt(relatedMatch[1]) : 0
        }
      }).filter(e => e.name)
    }
    
    // Extract relationship chains - extract all, no limit
    const relSection = text.match(/###\s*(?:\[Relationship Chains\]|Relationship Chains)\n([\s\S]*?)(?=\n###|$)/)
    if (relSection) {
      const lines = relSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.relations = lines.map(l => {
        const match = l.match(/^-\s*(.+?)\s*--\[(.+?)\]-->\s*(.+)$/)
        if (match) {
          return { source: match[1].trim(), relation: match[2].trim(), target: match[3].trim() }
        }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    console.warn('Parse insight_forge failed:', e)
  }
  
  return result
}

const parsePanorama = (text) => {
  const result = {
    query: '',
    stats: { nodes: 0, edges: 0, activeFacts: 0, historicalFacts: 0 },
    activeFacts: [],
    historicalFacts: [],
    entities: []
  }
  
  try {
    // Extract query
    const queryMatch = text.match(/Query:\s*(.+?)(?:\n|$)/)
    if (queryMatch) result.query = queryMatch[1].trim()

    // Extract statistics (case-insensitive to match backend output)
    const nodesMatch = text.match(/Total\s*Nodes?:\s*(\d+)/i)
    const edgesMatch = text.match(/Total\s*Edges?:\s*(\d+)/i)
    const activeMatch = text.match(/(?:Current(?:ly)?|Valid)\s*(?:Valid\s*)?Facts?:\s*(\d+)/i)
    const histMatch = text.match(/Historical.*?Facts?:\s*(\d+)/i)
    if (nodesMatch) result.stats.nodes = parseInt(nodesMatch[1])
    if (edgesMatch) result.stats.edges = parseInt(edgesMatch[1])
    if (activeMatch) result.stats.activeFacts = parseInt(activeMatch[1])
    if (histMatch) result.stats.historicalFacts = parseInt(histMatch[1])

    // Extract current valid facts - match both old and new header formats
    const activeSection = text.match(/###\s*(?:\[Currently Active Facts\]|Current Valid Facts[^\n]*)\n([\s\S]*?)(?=\n###|$)/)
    if (activeSection) {
      const lines = activeSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.activeFacts = lines.map(l => {
        const factText = l.replace(/^\d+\.\s*/, '').replace(/^"|"$/g, '').trim()
        return factText
      }).filter(Boolean)
    }

    // Extract historical/expired facts
    const histSection = text.match(/###\s*(?:\[Historical\/Expired Facts\]|Historical\/Expired Facts[^\n]*)\n([\s\S]*?)(?=\n###|$)/)
    if (histSection) {
      const lines = histSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.historicalFacts = lines.map(l => {
        const factText = l.replace(/^\d+\.\s*/, '').replace(/^"|"$/g, '').trim()
        return factText
      }).filter(Boolean)
    }

    // Extract involved entities
    const entitySection = text.match(/###\s*(?:\[Involved Entities\]|Involved Entities)\n([\s\S]*?)(?=\n###|$)/)
    if (entitySection) {
      const lines = entitySection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.entities = lines.map(l => {
        const match = l.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        if (match) return { name: match[1].trim(), type: match[2].trim() }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    console.warn('Parse panorama failed:', e)
  }
  
  return result
}

const parseInterview = (text) => {
  const result = {
    topic: '',
    agentCount: '',
    successCount: 0,
    totalCount: 0,
    selectionReason: '',
    interviews: [],
    summary: ''
  }
  
  try {
    // Extract interview topic
    const topicMatch = text.match(/\*\*Interview Topic:\*\*\s*(.+?)(?:\n|$)/)
    if (topicMatch) result.topic = topicMatch[1].trim()

    // Extract number of interviewees (e.g. "5 / 9 simulated Agents")
    const countMatch = text.match(/\*\*Interviewees:\*\*\s*(\d+)\s*\/\s*(\d+)/)
    if (countMatch) {
      result.successCount = parseInt(countMatch[1])
      result.totalCount = parseInt(countMatch[2])
      result.agentCount = `${countMatch[1]} / ${countMatch[2]}`
    }
    
    // Extract interviewee selection reasons
    const reasonMatch = text.match(/### Interviewee Selection Reasoning\n([\s\S]*?)(?=\n---\n|\n### Interview Transcripts)/)
    if (reasonMatch) {
      result.selectionReason = reasonMatch[1].trim()
    }
    
    // Parse individual selection reasons
    const parseIndividualReasons = (reasonText) => {
      const reasons = {}
      if (!reasonText) return reasons
      
      const lines = reasonText.split(/\n+/)
      let currentName = null
      let currentReason = []
      
      for (const line of lines) {
        let headerMatch = null
        let name = null
        let reasonStart = null
        
        // Format 1: number. **name (index=X)**: reason
        // Example: 1. **alumni_345 (index=1)**: As a university alumnus...
        headerMatch = line.match(/^\d+\.\s*\*\*([^*（(]+)(?:[（(]index\s*=?\s*\d+[)）])?\*\*[：:]\s*(.*)/)
        if (headerMatch) {
          name = headerMatch[1].trim()
          reasonStart = headerMatch[2]
        }
        
        // Format 2: - Select name (index X): reason
        // Example: - Select parent_601 (index 0): As a parent group representative...
        if (!headerMatch) {
          headerMatch = line.match(/^-\s*(?:Select(?:ed)?)\s+([^（(]+)(?:[（(]index\s*=?\s*\d+[)）])?[：:]\s*(.*)/)
          if (headerMatch) {
            name = headerMatch[1].trim()
            reasonStart = headerMatch[2]
          }
        }
        
        // Format 3: - **name (index X)**: reason
        // Example: - **parent_601 (index 0)**: As a parent group representative...
        if (!headerMatch) {
          headerMatch = line.match(/^-\s*\*\*([^*（(]+)(?:[（(]index\s*=?\s*\d+[)）])?\*\*[：:]\s*(.*)/)
          if (headerMatch) {
            name = headerMatch[1].trim()
            reasonStart = headerMatch[2]
          }
        }
        
        if (name) {
          // Save previous person's reason
          if (currentName && currentReason.length > 0) {
            reasons[currentName] = currentReason.join(' ').trim()
          }
          // Start new person
          currentName = name
          currentReason = reasonStart ? [reasonStart.trim()] : []
        } else if (currentName && line.trim() && !line.match(/^Not selected|^In summary|^Final selection/)) {
          // Continuation of reason (exclude closing summary paragraphs)
          currentReason.push(line.trim())
        }
      }
      
      // Save last person's reason
      if (currentName && currentReason.length > 0) {
        reasons[currentName] = currentReason.join(' ').trim()
      }
      
      return reasons
    }
    
    const individualReasons = parseIndividualReasons(result.selectionReason)
    
    // Extract each interview record
    const interviewBlocks = text.split(/#### Interview #\d+:/).slice(1)
    
    interviewBlocks.forEach((block, index) => {
      const interview = {
        num: index + 1,
        title: '',
        name: '',
        role: '',
        bio: '',
        selectionReason: '',
        questions: [],
        twitterAnswer: '',
        redditAnswer: '',
        quotes: []
      }
      
      // Extract title (e.g. "Student", "Educator", etc.)
      const titleMatch = block.match(/^(.+?)\n/)
      if (titleMatch) interview.title = titleMatch[1].trim()
      
      // Extract name and role
      const nameRoleMatch = block.match(/\*\*(.+?)\*\*\s*\((.+?)\)/)
      if (nameRoleMatch) {
        interview.name = nameRoleMatch[1].trim()
        interview.role = nameRoleMatch[2].trim()
        // Set this person's selection reason
        interview.selectionReason = individualReasons[interview.name] || ''
      }
      
      // Extract bio
      const bioMatch = block.match(/_Bio:\s*([\s\S]*?)_\n/)
      if (bioMatch) {
        interview.bio = bioMatch[1].trim().replace(/\.\.\.$/, '...')
      }
      
      // Extract question list
      const qMatch = block.match(/\*\*Q:\*\*\s*([\s\S]*?)(?=\n\n\*\*A:\*\*|\*\*A:\*\*)/)
      if (qMatch) {
        const qText = qMatch[1].trim()
        // Split questions by number
        const questions = qText.split(/\n\d+\.\s+/).filter(q => q.trim())
        if (questions.length > 0) {
          // If the first question has "1." prefix, handle specially
          const firstQ = qText.match(/^1\.\s+(.+)/)
          if (firstQ) {
            interview.questions = [firstQ[1].trim(), ...questions.slice(1).map(q => q.trim())]
          } else {
            interview.questions = questions.map(q => q.trim())
          }
        }
      }
      
      // Extract answers - split by Twitter and Reddit
      const answerMatch = block.match(/\*\*A:\*\*\s*([\s\S]*?)(?=\*\*Key Quotes|$)/)
      if (answerMatch) {
        const answerText = answerMatch[1].trim()
        
        // Separate Twitter and Reddit answers
        const twitterMatch = answerText.match(/\[Twitter Platform Response\]\n?([\s\S]*?)(?=\[Reddit Platform Response\]|$)/)
        const redditMatch = answerText.match(/\[Reddit Platform Response\]\n?([\s\S]*?)$/)
        
        if (twitterMatch) {
          interview.twitterAnswer = twitterMatch[1].trim()
        }
        if (redditMatch) {
          interview.redditAnswer = redditMatch[1].trim()
        }
        
        // Platform fallback logic (backwards compatible with old format: only one platform marker)
        if (!twitterMatch && redditMatch) {
          // Only Reddit answer, copy as default display only when not placeholder text
          if (interview.redditAnswer && interview.redditAnswer !== '(No response from this platform)') {
            interview.twitterAnswer = interview.redditAnswer
          }
        } else if (twitterMatch && !redditMatch) {
          if (interview.twitterAnswer && interview.twitterAnswer !== '(No response from this platform)') {
            interview.redditAnswer = interview.twitterAnswer
          }
        } else if (!twitterMatch && !redditMatch) {
          // No platform markers (very old format), use entire text as answer
          interview.twitterAnswer = answerText
        }
      }
      
      // Extract key quotes (compatible with multiple quote formats)
      const quotesMatch = block.match(/\*\*Key Quotes:\*\*\n([\s\S]*?)(?=\n---|\n####|$)/)
      if (quotesMatch) {
        const quotesText = quotesMatch[1]
        // Prefer matching > "text" format
        let quoteMatches = quotesText.match(/> "([^"]+)"/g)
        // Fallback: match > "text" or > \u201Ctext\u201D (Chinese quotes)
        if (!quoteMatches) {
          quoteMatches = quotesText.match(/> [\u201C""]([^\u201D""]+)[\u201D""]/g)
        }
        if (quoteMatches) {
          interview.quotes = quoteMatches
            .map(q => q.replace(/^> [\u201C""]|[\u201D""]$/g, '').trim())
            .filter(q => q)
        }
      }
      
      if (interview.name || interview.title) {
        result.interviews.push(interview)
      }
    })
    
    // Extract interview summary
    const summaryMatch = text.match(/### Interview Summary and Key Insights\n([\s\S]*?)$/)
    if (summaryMatch) {
      result.summary = summaryMatch[1].trim()
    }
  } catch (e) {
    console.warn('Parse interview failed:', e)
  }
  
  return result
}

const parseQuickSearch = (text) => {
  const result = {
    query: '',
    count: 0,
    facts: [],
    edges: [],
    nodes: []
  }
  
  try {
    // Extract search query
    const queryMatch = text.match(/Search\s*Query:\s*(.+?)(?:\n|$)/i)
    if (queryMatch) result.query = queryMatch[1].trim()

    // Extract result count
    const countMatch = text.match(/Found\s*(\d+)\s*(?:relevant|related)/i)
    if (countMatch) result.count = parseInt(countMatch[1])

    // Extract related facts - extract all, no limit
    const factsSection = text.match(/###\s*(?:Relevant|Related)\s*[Ff]acts:?\n([\s\S]*)$/)
    if (factsSection) {
      const lines = factsSection[1].split('\n').filter(l => l.match(/^\d+\./))
      result.facts = lines.map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean)
    }
    
    // Try to extract edge information (if available)
    const edgesSection = text.match(/### Related edges:\n([\s\S]*?)(?=\n###|$)/)
    if (edgesSection) {
      const lines = edgesSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.edges = lines.map(l => {
        const match = l.match(/^-\s*(.+?)\s*--\[(.+?)\]-->\s*(.+)$/)
        if (match) {
          return { source: match[1].trim(), relation: match[2].trim(), target: match[3].trim() }
        }
        return null
      }).filter(Boolean)
    }
    
    // Try to extract node information (if available)
    const nodesSection = text.match(/### Related nodes:\n([\s\S]*?)(?=\n###|$)/)
    if (nodesSection) {
      const lines = nodesSection[1].split('\n').filter(l => l.trim().startsWith('-'))
      result.nodes = lines.map(l => {
        const match = l.match(/^-\s*\*\*(.+?)\*\*\s*\((.+?)\)/)
        if (match) return { name: match[1].trim(), type: match[2].trim() }
        const simpleMatch = l.match(/^-\s*(.+)$/)
        if (simpleMatch) return { name: simpleMatch[1].trim(), type: '' }
        return null
      }).filter(Boolean)
    }
  } catch (e) {
    console.warn('Parse quick_search failed:', e)
  }
  
  return result
}

// ========== Sub Components ==========

// Insight Display Component - Enhanced with full data rendering (Interview-like style)
const InsightDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const activeTab = ref('facts') // 'facts', 'entities', 'relations', 'subqueries'
    const expandedFacts = ref(false)
    const expandedEntities = ref(false)
    const expandedRelations = ref(false)
    const INITIAL_SHOW_COUNT = 5
    
    // Format result size for display
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}k chars`
      }
      return `${length} chars`
    }
    
    return () => h('div', { class: 'insight-display' }, [
      // Header Section - like interview header
      h('div', { class: 'insight-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, 'Deep Insight'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.facts || props.result.facts.length),
              h('span', { class: 'stat-label' }, 'Facts')
            ]),
            h('span', { class: 'stat-divider' }, '/'),
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.entities || props.result.entities.length),
              h('span', { class: 'stat-label' }, 'Entities')
            ]),
            h('span', { class: 'stat-divider' }, '/'),
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.relationships || props.result.relations.length),
              h('span', { class: 'stat-label' }, 'Relations')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.query && h('div', { class: 'header-topic' }, props.result.query),
        props.result.simulationRequirement && h('div', { class: 'header-scenario' }, [
          h('span', { class: 'scenario-label' }, 'Prediction Scenario: '),
          h('span', { class: 'scenario-text' }, props.result.simulationRequirement)
        ])
      ]),
      
      // Tab Navigation
      h('div', { class: 'insight-tabs' }, [
        h('button', {
          class: ['insight-tab', { active: activeTab.value === 'facts' }],
          onClick: () => { activeTab.value = 'facts' }
        }, [
          h('span', { class: 'tab-label' }, `Current Key Memories (${props.result.facts.length})`)
        ]),
        h('button', {
          class: ['insight-tab', { active: activeTab.value === 'entities' }],
          onClick: () => { activeTab.value = 'entities' }
        }, [
          h('span', { class: 'tab-label' }, `Core Entities (${props.result.entities.length})`)
        ]),
        h('button', {
          class: ['insight-tab', { active: activeTab.value === 'relations' }],
          onClick: () => { activeTab.value = 'relations' }
        }, [
          h('span', { class: 'tab-label' }, `Relationship Chains (${props.result.relations.length})`)
        ]),
        props.result.subQueries.length > 0 && h('button', {
          class: ['insight-tab', { active: activeTab.value === 'subqueries' }],
          onClick: () => { activeTab.value = 'subqueries' }
        }, [
          h('span', { class: 'tab-label' }, `Sub-questions (${props.result.subQueries.length})`)
        ])
      ]),
      
      // Tab Content
      h('div', { class: 'insight-content' }, [
        // Facts Tab
        activeTab.value === 'facts' && props.result.facts.length > 0 && h('div', { class: 'facts-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, 'Latest key facts associated with temporal memory'),
            h('span', { class: 'panel-count' }, `${props.result.facts.length} items`)
          ]),
          h('div', { class: 'facts-list' },
            (expandedFacts.value ? props.result.facts : props.result.facts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) => 
              h('div', { class: 'fact-item', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, fact)
              ])
            )
          ),
          props.result.facts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedFacts.value = !expandedFacts.value }
          }, expandedFacts.value ? `Collapse ▲` : `Expand All ${props.result.facts.length} items ▼`)
        ]),

        // Entities Tab
        activeTab.value === 'entities' && props.result.entities.length > 0 && h('div', { class: 'entities-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, 'Core Entities'),
            h('span', { class: 'panel-count' }, `${props.result.entities.length} entities`)
          ]),
          h('div', { class: 'entities-grid' },
            (expandedEntities.value ? props.result.entities : props.result.entities.slice(0, 12)).map((entity, i) =>
              h('div', { class: 'entity-tag', key: i, title: entity.summary || '' }, [
                h('span', { class: 'entity-name' }, entity.name),
                h('span', { class: 'entity-type' }, entity.type),
                entity.relatedFactsCount > 0 && h('span', { class: 'entity-fact-count' }, `${entity.relatedFactsCount} facts`)
              ])
            )
          ),
          props.result.entities.length > 12 && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedEntities.value = !expandedEntities.value }
          }, expandedEntities.value ? `Collapse ▲` : `Expand All ${props.result.entities.length} entities ▼`)
        ]),

        // Relations Tab
        activeTab.value === 'relations' && props.result.relations.length > 0 && h('div', { class: 'relations-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, 'Relationship Chains'),
            h('span', { class: 'panel-count' }, `${props.result.relations.length} items`)
          ]),
          h('div', { class: 'relations-list' },
            (expandedRelations.value ? props.result.relations : props.result.relations.slice(0, INITIAL_SHOW_COUNT)).map((rel, i) => 
              h('div', { class: 'relation-item', key: i }, [
                h('span', { class: 'rel-source' }, rel.source),
                h('span', { class: 'rel-arrow' }, [
                  h('span', { class: 'rel-line' }),
                  h('span', { class: 'rel-label' }, rel.relation),
                  h('span', { class: 'rel-line' })
                ]),
                h('span', { class: 'rel-target' }, rel.target)
              ])
            )
          ),
          props.result.relations.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedRelations.value = !expandedRelations.value }
          }, expandedRelations.value ? `Collapse ▲` : `Expand All ${props.result.relations.length} items ▼`)
        ]),
        
        // Sub-queries Tab
        activeTab.value === 'subqueries' && props.result.subQueries.length > 0 && h('div', { class: 'subqueries-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, 'Drift query generated analysis sub-questions'),
            h('span', { class: 'panel-count' }, `${props.result.subQueries.length} questions`)
          ]),
          h('div', { class: 'subqueries-list' },
            props.result.subQueries.map((sq, i) => 
              h('div', { class: 'subquery-item', key: i }, [
                h('span', { class: 'subquery-number' }, `Q${i + 1}`),
                h('div', { class: 'subquery-text' }, sq)
              ])
            )
          )
        ]),
        
        // Empty state
        activeTab.value === 'facts' && props.result.facts.length === 0 && h('div', { class: 'empty-state' }, 'No current key memories'),
        activeTab.value === 'entities' && props.result.entities.length === 0 && h('div', { class: 'empty-state' }, 'No core entities'),
        activeTab.value === 'relations' && props.result.relations.length === 0 && h('div', { class: 'empty-state' }, 'No relationship chains')
      ])
    ])
  }
}

// Panorama Display Component - Enhanced with Active/Historical tabs
const PanoramaDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const activeTab = ref('active') // 'active', 'historical', 'entities'
    const expandedActive = ref(false)
    const expandedHistorical = ref(false)
    const expandedEntities = ref(false)
    const INITIAL_SHOW_COUNT = 5
    
    // Format result size for display
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}k chars`
      }
      return `${length} chars`
    }
    
    return () => h('div', { class: 'panorama-display' }, [
      // Header Section
      h('div', { class: 'panorama-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, 'Panorama Search'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.nodes),
              h('span', { class: 'stat-label' }, 'Nodes')
            ]),
            h('span', { class: 'stat-divider' }, '/'),
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.stats.edges),
              h('span', { class: 'stat-label' }, 'Edges')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.query && h('div', { class: 'header-topic' }, props.result.query)
      ]),
      
      // Tab Navigation
      h('div', { class: 'panorama-tabs' }, [
        h('button', {
          class: ['panorama-tab', { active: activeTab.value === 'active' }],
          onClick: () => { activeTab.value = 'active' }
        }, [
          h('span', { class: 'tab-label' }, `Current Valid Memories (${props.result.activeFacts.length})`)
        ]),
        h('button', {
          class: ['panorama-tab', { active: activeTab.value === 'historical' }],
          onClick: () => { activeTab.value = 'historical' }
        }, [
          h('span', { class: 'tab-label' }, `Historical Memories (${props.result.historicalFacts.length})`)
        ]),
        h('button', {
          class: ['panorama-tab', { active: activeTab.value === 'entities' }],
          onClick: () => { activeTab.value = 'entities' }
        }, [
          h('span', { class: 'tab-label' }, `Involved Entities (${props.result.entities.length})`)
        ])
      ]),
      
      // Tab Content
      h('div', { class: 'panorama-content' }, [
        // Active Facts Tab
        activeTab.value === 'active' && h('div', { class: 'facts-panel active-facts' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, 'Current Valid Memories'),
            h('span', { class: 'panel-count' }, `${props.result.activeFacts.length} items`)
          ]),
          props.result.activeFacts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedActive.value ? props.result.activeFacts : props.result.activeFacts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) => 
              h('div', { class: 'fact-item active', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, fact)
              ])
            )
          ) : h('div', { class: 'empty-state' }, 'No current valid memories'),
          props.result.activeFacts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedActive.value = !expandedActive.value }
          }, expandedActive.value ? `Collapse ▲` : `Expand All ${props.result.activeFacts.length} items ▼`)
        ]),
        
        // Historical Facts Tab
        activeTab.value === 'historical' && h('div', { class: 'facts-panel historical-facts' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, 'Historical Memories'),
            h('span', { class: 'panel-count' }, `${props.result.historicalFacts.length} items`)
          ]),
          props.result.historicalFacts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedHistorical.value ? props.result.historicalFacts : props.result.historicalFacts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) => 
              h('div', { class: 'fact-item historical', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, [
                  // Try to extract time information [time - time]
                  (() => {
                    const timeMatch = fact.match(/^\[(.+?)\]\s*(.*)$/)
                    if (timeMatch) {
                      return [
                        h('span', { class: 'fact-time' }, timeMatch[1]),
                        h('span', { class: 'fact-text' }, timeMatch[2])
                      ]
                    }
                    return h('span', { class: 'fact-text' }, fact)
                  })()
                ])
              ])
            )
          ) : h('div', { class: 'empty-state' }, 'No historical memories'),
          props.result.historicalFacts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedHistorical.value = !expandedHistorical.value }
          }, expandedHistorical.value ? `Collapse ▲` : `Expand All ${props.result.historicalFacts.length} items ▼`)
        ]),
        
        // Entities Tab
        activeTab.value === 'entities' && h('div', { class: 'entities-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, 'Involved Entities'),
            h('span', { class: 'panel-count' }, `${props.result.entities.length} entities`)
          ]),
          props.result.entities.length > 0 ? h('div', { class: 'entities-grid' },
            (expandedEntities.value ? props.result.entities : props.result.entities.slice(0, 8)).map((entity, i) => 
              h('div', { class: 'entity-tag', key: i }, [
                h('span', { class: 'entity-name' }, entity.name),
                entity.type && h('span', { class: 'entity-type' }, entity.type)
              ])
            )
          ) : h('div', { class: 'empty-state' }, 'No involved entities'),
          props.result.entities.length > 8 && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedEntities.value = !expandedEntities.value }
          }, expandedEntities.value ? `Collapse ▲` : `Expand All ${props.result.entities.length} entities ▼`)
        ])
      ])
    ])
  }
}

// Interview Display Component - Conversation Style (Q&A Format)
const InterviewDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    // Format result size for display
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}k chars`
      }
      return `${length} chars`
    }
    
    // Clean quote text - remove leading list numbers to avoid double numbering
    const cleanQuoteText = (text) => {
      if (!text) return ''
      // Remove leading patterns like "1. ", "2. ", "1、", "（1）", "(1)" etc.
      return text.replace(/^\s*\d+[\.\、\)）]\s*/, '').trim()
    }
    
    const activeIndex = ref(0)
    const expandedAnswers = ref(new Set())
    // Maintain independent platform selection state for each question-answer pair
    const platformTabs = reactive({}) // { 'agentIdx-qIdx': 'twitter' | 'reddit' }
    
    // Get current platform selection for a question
    const getPlatformTab = (agentIdx, qIdx) => {
      const key = `${agentIdx}-${qIdx}`
      return platformTabs[key] || 'twitter'
    }
    
    // Set platform selection for a question
    const setPlatformTab = (agentIdx, qIdx, platform) => {
      const key = `${agentIdx}-${qIdx}`
      platformTabs[key] = platform
    }
    
    const toggleAnswer = (key) => {
      const newSet = new Set(expandedAnswers.value)
      if (newSet.has(key)) {
        newSet.delete(key)
      } else {
        newSet.add(key)
      }
      expandedAnswers.value = newSet
    }
    
    const formatAnswer = (text, expanded) => {
      if (!text) return ''
      if (expanded || text.length <= 400) return text
      return text.substring(0, 400) + '...'
    }
    
    // Check if text is platform placeholder text
    const isPlaceholderText = (text) => {
      if (!text) return true
      const t = text.trim()
      return t === '(No response from this platform)' || t === '[No response]'
    }

    // Try to split answers by question number
    const splitAnswerByQuestions = (answerText, questionCount) => {
      if (!answerText || questionCount <= 0) return [answerText]
      if (isPlaceholderText(answerText)) return ['']

      // Support two numbering formats:
      // 1. "QuestionX:" format (backend format)
      // 2. "1. " or "\n1. " (number+dot, legacy format compatible)
      let matches = []
      let match

      // Try "QuestionX:" format first
      const cnPattern = /(?:^|[\r\n]+)Question\s*(\d+)[：:]\s*/g
      while ((match = cnPattern.exec(answerText)) !== null) {
        matches.push({
          num: parseInt(match[1]),
          index: match.index,
          fullMatch: match[0]
        })
      }

      // If no match, fall back to "number." format
      if (matches.length === 0) {
        const numPattern = /(?:^|[\r\n]+)(\d+)\.\s+/g
        while ((match = numPattern.exec(answerText)) !== null) {
          matches.push({
            num: parseInt(match[1]),
            index: match.index,
            fullMatch: match[0]
          })
        }
      }

      // If no numbering found or only one found, return as whole
      if (matches.length <= 1) {
        const cleaned = answerText
          .replace(/^Question\s*\d+[：:]\s*/, '')
          .replace(/^\d+\.\s+/, '')
          .trim()
        return [cleaned || answerText]
      }

      // Extract parts by number
      const parts = []
      for (let i = 0; i < matches.length; i++) {
        const current = matches[i]
        const next = matches[i + 1]

        const startIdx = current.index + current.fullMatch.length
        const endIdx = next ? next.index : answerText.length

        let part = answerText.substring(startIdx, endIdx).trim()
        part = part.replace(/[\r\n]+$/, '').trim()
        parts.push(part)
      }

      if (parts.length > 0 && parts.some(p => p)) {
        return parts
      }

      return [answerText]
    }
    
    // Get answer for a specific question
    const getAnswerForQuestion = (interview, qIdx, platform) => {
      const answer = platform === 'twitter' ? interview.twitterAnswer : (interview.redditAnswer || interview.twitterAnswer)
      if (!answer || isPlaceholderText(answer)) return answer || ''

      const questionCount = interview.questions?.length || 1
      const answers = splitAnswerByQuestions(answer, questionCount)

      // Split successful and index valid
      if (answers.length > 1 && qIdx < answers.length) {
        return answers[qIdx] || ''
      }

      // Split failed: first question returns full answer, rest return empty
      return qIdx === 0 ? answer : ''
    }
    
    // Check if a question has dual platform answers (filtering placeholder text)
    const hasMultiplePlatforms = (interview, qIdx) => {
      if (!interview.twitterAnswer || !interview.redditAnswer) return false
      const twitterAnswer = getAnswerForQuestion(interview, qIdx, 'twitter')
      const redditAnswer = getAnswerForQuestion(interview, qIdx, 'reddit')
      // Both platforms have real answers (not placeholder) and content differs
      return !isPlaceholderText(twitterAnswer) && !isPlaceholderText(redditAnswer) && twitterAnswer !== redditAnswer
    }
    
    return () => h('div', { class: 'interview-display' }, [
      // Header Section
      h('div', { class: 'interview-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, 'Agent Interview'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.successCount || props.result.interviews.length),
              h('span', { class: 'stat-label' }, 'Interviewed')
            ]),
            props.result.totalCount > 0 && h('span', { class: 'stat-divider' }, '/'),
            props.result.totalCount > 0 && h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.totalCount),
              h('span', { class: 'stat-label' }, 'Total')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.topic && h('div', { class: 'header-topic' }, props.result.topic)
      ]),
      
      // Agent Selector Tabs
      props.result.interviews.length > 0 && h('div', { class: 'agent-tabs' }, 
        props.result.interviews.map((interview, i) => h('button', {
          class: ['agent-tab', { active: activeIndex.value === i }],
          key: i,
          onClick: () => { activeIndex.value = i }
        }, [
          h('span', { class: 'tab-avatar' }, interview.name ? interview.name.charAt(0) : (i + 1)),
          h('span', { class: 'tab-name' }, interview.title || interview.name || `Agent ${i + 1}`)
        ]))
      ),
      
      // Active Interview Detail
      props.result.interviews.length > 0 && h('div', { class: 'interview-detail' }, [
        // Agent Profile Card
        h('div', { class: 'agent-profile' }, [
          h('div', { class: 'profile-avatar' }, props.result.interviews[activeIndex.value]?.name?.charAt(0) || 'A'),
          h('div', { class: 'profile-info' }, [
            h('div', { class: 'profile-name' }, props.result.interviews[activeIndex.value]?.name || 'Agent'),
            h('div', { class: 'profile-role' }, props.result.interviews[activeIndex.value]?.role || ''),
            props.result.interviews[activeIndex.value]?.bio && h('div', { class: 'profile-bio' }, props.result.interviews[activeIndex.value].bio)
          ])
        ]),
        
        // Selection Reason
        props.result.interviews[activeIndex.value]?.selectionReason && h('div', { class: 'selection-reason' }, [
          h('div', { class: 'reason-label' }, 'Selection Reason'),
          h('div', { class: 'reason-content' }, props.result.interviews[activeIndex.value].selectionReason)
        ]),
        
        // Q&A Conversation Thread
        h('div', { class: 'qa-thread' }, 
          (props.result.interviews[activeIndex.value]?.questions?.length > 0 
            ? props.result.interviews[activeIndex.value].questions 
            : [props.result.interviews[activeIndex.value]?.question || 'No question available']
          ).map((question, qIdx) => {
            const interview = props.result.interviews[activeIndex.value]
            const currentPlatform = getPlatformTab(activeIndex.value, qIdx)
            const answerText = getAnswerForQuestion(interview, qIdx, currentPlatform)
            const hasDualPlatform = hasMultiplePlatforms(interview, qIdx)
            const expandKey = `${activeIndex.value}-${qIdx}`
            const isExpanded = expandedAnswers.value.has(expandKey)
            const isPlaceholder = isPlaceholderText(answerText)

            return h('div', { class: 'qa-pair', key: qIdx }, [
              // Question Block
              h('div', { class: 'qa-question' }, [
                h('div', { class: 'qa-badge q-badge' }, `Q${qIdx + 1}`),
                h('div', { class: 'qa-content' }, [
                  h('div', { class: 'qa-sender' }, 'Interviewer'),
                  h('div', { class: 'qa-text' }, question)
                ])
              ]),

              // Answer Block
              answerText && h('div', { class: ['qa-answer', { 'answer-placeholder': isPlaceholder }] }, [
                h('div', { class: 'qa-badge a-badge' }, `A${qIdx + 1}`),
                h('div', { class: 'qa-content' }, [
                  h('div', { class: 'qa-answer-header' }, [
                    h('div', { class: 'qa-sender' }, interview?.name || 'Agent'),
                    // Dual platform toggle buttons (only shown when both platforms have real answers)
                    hasDualPlatform && h('div', { class: 'platform-switch' }, [
                      h('button', {
                        class: ['platform-btn', { active: currentPlatform === 'twitter' }],
                        onClick: (e) => { e.stopPropagation(); setPlatformTab(activeIndex.value, qIdx, 'twitter') }
                      }, [
                        h('svg', { class: 'platform-icon', viewBox: '0 0 24 24', width: 12, height: 12, fill: 'none', stroke: 'currentColor', 'stroke-width': 2 }, [
                          h('circle', { cx: '12', cy: '12', r: '10' }),
                          h('line', { x1: '2', y1: '12', x2: '22', y2: '12' }),
                          h('path', { d: 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z' })
                        ]),
                        h('span', {}, 'World 1')
                      ]),
                      h('button', {
                        class: ['platform-btn', { active: currentPlatform === 'reddit' }],
                        onClick: (e) => { e.stopPropagation(); setPlatformTab(activeIndex.value, qIdx, 'reddit') }
                      }, [
                        h('svg', { class: 'platform-icon', viewBox: '0 0 24 24', width: 12, height: 12, fill: 'none', stroke: 'currentColor', 'stroke-width': 2 }, [
                          h('path', { d: 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z' })
                        ]),
                        h('span', {}, 'World 2')
                      ])
                    ])
                  ]),
                  h('div', {
                    class: ['qa-text', 'answer-text', { 'placeholder-text': isPlaceholder }],
                    innerHTML: isPlaceholder
                      ? answerText
                      : formatAnswer(answerText, isExpanded)
                          .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                          .replace(/\n/g, '<br>')
                  }),
                  // Expand/Collapse Button (not shown for placeholder text)
                  !isPlaceholder && answerText.length > 400 && h('button', {
                    class: 'expand-answer-btn',
                    onClick: () => toggleAnswer(expandKey)
                  }, isExpanded ? 'Show Less' : 'Show More')
                ])
              ])
            ])
          })
        ),
        
        // Key Quotes Section
        props.result.interviews[activeIndex.value]?.quotes?.length > 0 && h('div', { class: 'quotes-section' }, [
          h('div', { class: 'quotes-header' }, 'Key Quotes'),
          h('div', { class: 'quotes-list' },
            props.result.interviews[activeIndex.value].quotes.slice(0, 3).map((quote, qi) => {
              const cleanedQuote = cleanQuoteText(quote)
              const displayQuote = cleanedQuote.length > 200 ? cleanedQuote.substring(0, 200) + '...' : cleanedQuote
              return h('blockquote', { 
                key: qi, 
                class: 'quote-item',
                innerHTML: renderMarkdown(displayQuote)
              })
            })
          )
        ])
      ]),

      // Summary Section (Collapsible)
      props.result.summary && h('div', { class: 'summary-section' }, [
        h('div', { class: 'summary-header' }, 'Interview Summary'),
        h('div', { 
          class: 'summary-content',
          innerHTML: renderMarkdown(props.result.summary.length > 500 ? props.result.summary.substring(0, 500) + '...' : props.result.summary)
        })
      ])
    ])
  }
}

// Quick Search Display Component - Enhanced with full data rendering
const QuickSearchDisplay = {
  props: ['result', 'resultLength'],
  setup(props) {
    const activeTab = ref('facts') // 'facts', 'edges', 'nodes'
    const expandedFacts = ref(false)
    const INITIAL_SHOW_COUNT = 5
    
    // Check if there are edges or nodes to show tabs
    const hasEdges = computed(() => props.result.edges && props.result.edges.length > 0)
    const hasNodes = computed(() => props.result.nodes && props.result.nodes.length > 0)
    const showTabs = computed(() => hasEdges.value || hasNodes.value)
    
    // Format result size for display
    const formatSize = (length) => {
      if (!length) return ''
      if (length >= 1000) {
        return `${(length / 1000).toFixed(1)}k chars`
      }
      return `${length} chars`
    }
    
    return () => h('div', { class: 'quick-search-display' }, [
      // Header Section
      h('div', { class: 'quicksearch-header' }, [
        h('div', { class: 'header-main' }, [
          h('div', { class: 'header-title' }, 'Quick Search'),
          h('div', { class: 'header-stats' }, [
            h('span', { class: 'stat-item' }, [
              h('span', { class: 'stat-value' }, props.result.count || props.result.facts.length),
              h('span', { class: 'stat-label' }, 'Results')
            ]),
            props.resultLength && h('span', { class: 'stat-divider' }, '·'),
            props.resultLength && h('span', { class: 'stat-size' }, formatSize(props.resultLength))
          ])
        ]),
        props.result.query && h('div', { class: 'header-query' }, [
          h('span', { class: 'query-label' }, 'Search: '),
          h('span', { class: 'query-text' }, props.result.query)
        ])
      ]),
      
      // Tab Navigation (only show if there are edges or nodes)
      showTabs.value && h('div', { class: 'quicksearch-tabs' }, [
        h('button', {
          class: ['quicksearch-tab', { active: activeTab.value === 'facts' }],
          onClick: () => { activeTab.value = 'facts' }
        }, [
          h('span', { class: 'tab-label' }, `Facts (${props.result.facts.length})`)
        ]),
        hasEdges.value && h('button', {
          class: ['quicksearch-tab', { active: activeTab.value === 'edges' }],
          onClick: () => { activeTab.value = 'edges' }
        }, [
          h('span', { class: 'tab-label' }, `Relationships (${props.result.edges.length})`)
        ]),
        hasNodes.value && h('button', {
          class: ['quicksearch-tab', { active: activeTab.value === 'nodes' }],
          onClick: () => { activeTab.value = 'nodes' }
        }, [
          h('span', { class: 'tab-label' }, `Nodes (${props.result.nodes.length})`)
        ])
      ]),
      
      // Content Area
      h('div', { class: ['quicksearch-content', { 'no-tabs': !showTabs.value }] }, [
        // Facts (always show if no tabs, or when facts tab is active)
        ((!showTabs.value) || activeTab.value === 'facts') && h('div', { class: 'facts-panel' }, [
          !showTabs.value && h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, 'Search Results'),
            h('span', { class: 'panel-count' }, `${props.result.facts.length} items`)
          ]),
          props.result.facts.length > 0 ? h('div', { class: 'facts-list' },
            (expandedFacts.value ? props.result.facts : props.result.facts.slice(0, INITIAL_SHOW_COUNT)).map((fact, i) => 
              h('div', { class: 'fact-item', key: i }, [
                h('span', { class: 'fact-number' }, i + 1),
                h('div', { class: 'fact-content' }, fact)
              ])
            )
          ) : h('div', { class: 'empty-state' }, 'No relevant results found'),
          props.result.facts.length > INITIAL_SHOW_COUNT && h('button', {
            class: 'expand-btn',
            onClick: () => { expandedFacts.value = !expandedFacts.value }
          }, expandedFacts.value ? `Collapse ▲` : `Expand All ${props.result.facts.length} items ▼`)
        ]),
        
        // Edges Tab
        activeTab.value === 'edges' && hasEdges.value && h('div', { class: 'edges-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, 'Related Relationships'),
            h('span', { class: 'panel-count' }, `${props.result.edges.length} items`)
          ]),
          h('div', { class: 'edges-list' },
            props.result.edges.map((edge, i) => 
              h('div', { class: 'edge-item', key: i }, [
                h('span', { class: 'edge-source' }, edge.source),
                h('span', { class: 'edge-arrow' }, [
                  h('span', { class: 'edge-line' }),
                  h('span', { class: 'edge-label' }, edge.relation),
                  h('span', { class: 'edge-line' })
                ]),
                h('span', { class: 'edge-target' }, edge.target)
              ])
            )
          )
        ]),
        
        // Nodes Tab
        activeTab.value === 'nodes' && hasNodes.value && h('div', { class: 'nodes-panel' }, [
          h('div', { class: 'panel-header' }, [
            h('span', { class: 'panel-title' }, 'Related Nodes'),
            h('span', { class: 'panel-count' }, `${props.result.nodes.length} nodes`)
          ]),
          h('div', { class: 'nodes-grid' },
            props.result.nodes.map((node, i) => 
              h('div', { class: 'node-tag', key: i }, [
                h('span', { class: 'node-name' }, node.name),
                node.type && h('span', { class: 'node-type' }, node.type)
              ])
            )
          )
        ])
      ])
    ])
  }
}

// Computed
const statusClass = computed(() => {
  if (isComplete.value) return 'completed'
  if (agentLogs.value.length > 0) return 'processing'
  return 'pending'
})

const statusText = computed(() => {
  if (isComplete.value) return 'Completed'
  if (agentLogs.value.length > 0) return 'Generating...'
  return 'Waiting'
})

const totalSections = computed(() => {
  return reportOutline.value?.sections?.length || 0
})

const completedSections = computed(() => {
  return Object.keys(generatedSections.value).length
})

const progressPercent = computed(() => {
  if (totalSections.value === 0) return 0
  return Math.round((completedSections.value / totalSections.value) * 100)
})

const totalToolCalls = computed(() => {
  return agentLogs.value.filter(l => l.action === 'tool_call').length
})

const formatElapsedTime = computed(() => {
  if (!startTime.value) return '0s'
  const lastLog = agentLogs.value[agentLogs.value.length - 1]
  const elapsed = lastLog?.elapsed_seconds || 0
  if (elapsed < 60) return `${Math.round(elapsed)}s`
  const mins = Math.floor(elapsed / 60)
  const secs = Math.round(elapsed % 60)
  return `${mins}m ${secs}s`
})

const displayLogs = computed(() => {
  return agentLogs.value
})

// Workflow steps overview (status-based, no nested cards)
const activeSectionIndex = computed(() => {
  if (isComplete.value) return null
  if (currentSectionIndex.value) return currentSectionIndex.value
  if (totalSections.value > 0 && completedSections.value < totalSections.value) return completedSections.value + 1
  return null
})

const isPlanningDone = computed(() => {
  return !!reportOutline.value?.sections?.length || agentLogs.value.some(l => l.action === 'planning_complete')
})

const isPlanningStarted = computed(() => {
  return agentLogs.value.some(l => l.action === 'planning_start' || l.action === 'report_start')
})

const isFinalizing = computed(() => {
  return !isComplete.value && isPlanningDone.value && totalSections.value > 0 && completedSections.value >= totalSections.value
})

// Current active step (used for top display)
const activeStep = computed(() => {
  const steps = workflowSteps.value
  // Find the current active step
  const active = steps.find(s => s.status === 'active')
  if (active) return active
  
  // If no active step, return the last done step
  const doneSteps = steps.filter(s => s.status === 'done')
  if (doneSteps.length > 0) return doneSteps[doneSteps.length - 1]
  
  // Otherwise return the first step
  return steps[0] || { noLabel: '--', title: 'Waiting to Start', status: 'todo', meta: '' }
})

const workflowSteps = computed(() => {
  const steps = []

  // Planning / Outline
  const planningStatus = isPlanningDone.value ? 'done' : (isPlanningStarted.value ? 'active' : 'todo')
  steps.push({
    key: 'planning',
    noLabel: 'PL',
    title: 'Planning / Outline',
    status: planningStatus,
    meta: planningStatus === 'active' ? 'IN PROGRESS' : ''
  })

  // Sections (if outline exists)
  const sections = reportOutline.value?.sections || []
  sections.forEach((section, i) => {
    const idx = i + 1
    const status = (isComplete.value || !!generatedSections.value[idx])
      ? 'done'
      : (activeSectionIndex.value === idx ? 'active' : 'todo')

    steps.push({
      key: `section-${idx}`,
      noLabel: String(idx).padStart(2, '0'),
      title: section.title,
      status,
      meta: status === 'active' ? 'IN PROGRESS' : ''
    })
  })

  // Complete
  const completeStatus = isComplete.value ? 'done' : (isFinalizing.value ? 'active' : 'todo')
  steps.push({
    key: 'complete',
    noLabel: 'OK',
    title: 'Complete',
    status: completeStatus,
    meta: completeStatus === 'active' ? 'FINALIZING' : ''
  })

  return steps
})

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

const isSectionCompleted = (sectionIndex) => {
  return !!generatedSections.value[sectionIndex]
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    })
  } catch {
    return ''
  }
}

const formatParams = (params) => {
  if (!params) return ''
  try {
    return JSON.stringify(params, null, 2)
  } catch {
    return String(params)
  }
}

const formatResultSize = (length) => {
  if (!length) return ''
  if (length < 1000) return `${length} chars`
  return `${(length / 1000).toFixed(1)}k chars`
}

const truncateText = (text, maxLen) => {
  if (!text) return ''
  if (text.length <= maxLen) return text
  return text.substring(0, maxLen) + '...'
}

const renderMarkdown = (content) => {
  if (!content) return ''
  
  // Remove leading level-2 heading (## xxx), since section title is already displayed outside
  let processedContent = content.replace(/^##\s+.+\n+/, '')
  
  // Process code blocks
  let html = processedContent.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  
  // Process inline code
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  
  // Process headings
  html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  
  // Process blockquotes
  html = html.replace(/^> (.+)$/gm, '<blockquote class="md-quote">$1</blockquote>')
  
  // Process lists - support sub-lists
  html = html.replace(/^(\s*)- (.+)$/gm, (match, indent, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-li" data-level="${level}">${text}</li>`
  })
  html = html.replace(/^(\s*)(\d+)\. (.+)$/gm, (match, indent, num, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-oli" data-level="${level}">${text}</li>`
  })

  // Wrap unordered lists
  html = html.replace(/(<li class="md-li"[^>]*>.*?<\/li>\s*)+/g, '<ul class="md-ul">$&</ul>')
  // Wrap ordered lists
  html = html.replace(/(<li class="md-oli"[^>]*>.*?<\/li>\s*)+/g, '<ol class="md-ol">$&</ol>')

  // Clean up all whitespace between list items
  html = html.replace(/<\/li>\s+<li/g, '</li><li')
  // Clean up whitespace after list opening tags
  html = html.replace(/<ul class="md-ul">\s+/g, '<ul class="md-ul">')
  html = html.replace(/<ol class="md-ol">\s+/g, '<ol class="md-ol">')
  // Clean up whitespace before list closing tags
  html = html.replace(/\s+<\/ul>/g, '</ul>')
  html = html.replace(/\s+<\/ol>/g, '</ol>')
  
  // Process bold and italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')
  
  // Process horizontal rules
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  
  // Process line breaks - empty lines become paragraph breaks, single newlines become <br>
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br>')
  
  // Wrap in paragraphs
  html = '<p class="md-p">' + html + '</p>'
  
  // Clean up empty paragraphs
  html = html.replace(/<p class="md-p"><\/p>/g, '')
  html = html.replace(/<p class="md-p">(<h[2-5])/g, '$1')
  html = html.replace(/(<\/h[2-5]>)<\/p>/g, '$1')
  html = html.replace(/<p class="md-p">(<ul|<ol|<blockquote|<pre|<hr)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>|<\/pre>)<\/p>/g, '$1')
  // Clean up <br> tags before/after block-level elements
  html = html.replace(/<br>\s*(<ul|<ol|<blockquote)/g, '$1')
  html = html.replace(/(<\/ul>|<\/ol>|<\/blockquote>)\s*<br>/g, '$1')
  // Clean up <p><br> followed by block-level elements (caused by extra blank lines)
  html = html.replace(/<p class="md-p">(<br>\s*)+(<ul|<ol|<blockquote|<pre|<hr)/g, '$2')
  // Clean up consecutive <br> tags
  html = html.replace(/(<br>\s*){2,}/g, '<br>')
  // Clean up <br> between block-level element closing tags and paragraph opening tags
  html = html.replace(/(<\/ol>|<\/ul>|<\/blockquote>)<br>(<p|<div)/g, '$1$2')

  // Fix numbering for non-consecutive ordered lists: when single-item <ol> blocks are separated by paragraph content, keep numbering incremental
  const tokens = html.split(/(<ol class="md-ol">(?:<li class="md-oli"[^>]*>[\s\S]*?<\/li>)+<\/ol>)/g)
  let olCounter = 0
  let inSequence = false
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].startsWith('<ol class="md-ol">')) {
      const liCount = (tokens[i].match(/<li class="md-oli"/g) || []).length
      if (liCount === 1) {
        olCounter++
        if (olCounter > 1) {
          tokens[i] = tokens[i].replace('<ol class="md-ol">', `<ol class="md-ol" start="${olCounter}">`)
        }
        inSequence = true
      } else {
        olCounter = 0
        inSequence = false
      }
    } else if (inSequence) {
      if (/<h[2-5]/.test(tokens[i])) {
        olCounter = 0
        inSequence = false
      }
    }
  }
  html = tokens.join('')

  return html
}

const getTimelineItemClass = (log, idx, total) => {
  const isLatest = idx === total - 1 && !isComplete.value
  const isMilestone = log.action === 'section_complete' || log.action === 'report_complete'
  return {
    'node--active': isLatest,
    'node--done': !isLatest && isMilestone,
    'node--muted': !isLatest && !isMilestone,
    'node--tool': log.action === 'tool_call' || log.action === 'tool_result'
  }
}

const getConnectorClass = (log, idx, total) => {
  const isLatest = idx === total - 1 && !isComplete.value
  if (isLatest) return 'dot-active'
  if (log.action === 'section_complete' || log.action === 'report_complete') return 'dot-done'
  return 'dot-muted'
}

const getActionLabel = (action) => {
  const labels = {
    'report_start': 'Report Started',
    'planning_start': 'Planning',
    'planning_complete': 'Plan Complete',
    'section_start': 'Section Start',
    'section_content': 'Content Ready',
    'section_complete': 'Section Done',
    'tool_call': 'Tool Call',
    'tool_result': 'Tool Result',
    'llm_response': 'LLM Response',
    'report_complete': 'Complete'
  }
  return labels[action] || action
}

const getLogLevelClass = (log) => {
  if (log.includes('ERROR')) return 'error'
  if (log.includes('WARNING')) return 'warning'
  // INFO uses default color, not marked as success
  return ''
}

// Polling
let agentLogTimer = null
let consoleLogTimer = null

const fetchAgentLog = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getAgentLog(props.reportId, agentLogLine.value)
    
    if (res.success && res.data) {
      const newLogs = res.data.logs || []
      
      if (newLogs.length > 0) {
        newLogs.forEach(log => {
          agentLogs.value.push(log)
          
          if (log.action === 'planning_complete' && log.details?.outline) {
            reportOutline.value = log.details.outline
          }
          
          if (log.action === 'section_start') {
            currentSectionIndex.value = log.section_index
          }

          // section_complete - Section generation complete
          if (log.action === 'section_complete') {
            if (log.details?.content) {
              generatedSections.value[log.section_index] = log.details.content
              // Auto-expand newly generated section
              expandedContent.value.add(log.section_index - 1)
              currentSectionIndex.value = null
            }
          }
          
          if (log.action === 'report_complete') {
            isComplete.value = true
            currentSectionIndex.value = null  // Ensure loading state is cleared
            emit('update-status', 'completed')
            stopPolling()
            // Scroll logic is handled in nextTick after loop ends
          }
          
          if (log.action === 'report_start') {
            startTime.value = new Date(log.timestamp)
          }
        })
        
        agentLogLine.value = res.data.from_line + newLogs.length
        
        nextTick(() => {
          if (rightPanel.value) {
            // If task is completed, scroll to top; otherwise scroll to bottom to follow latest logs
            if (isComplete.value) {
              rightPanel.value.scrollTop = 0
            } else {
              rightPanel.value.scrollTop = rightPanel.value.scrollHeight
            }
          }
        })
      }
    }
  } catch (err) {
    console.warn('Failed to fetch agent log:', err)
  }
}

// Extract final answer content - extract section content from LLM response
const extractFinalContent = (response) => {
  if (!response) return null
  
  // Try to extract content within <final_answer> tags
  const finalAnswerTagMatch = response.match(/<final_answer>([\s\S]*?)<\/final_answer>/)
  if (finalAnswerTagMatch) {
    return finalAnswerTagMatch[1].trim()
  }
  
  // Try to find content after Final Answer: (supports multiple formats)
  // Format 1: Final Answer:\n\ncontent
  // Format 2: Final Answer: content
  const finalAnswerMatch = response.match(/Final\s*Answer:\s*\n*([\s\S]*)$/i)
  if (finalAnswerMatch) {
    return finalAnswerMatch[1].trim()
  }
  
  // Try to find content after "Final Answer:" in various formats
  const chineseFinalMatch = response.match(/Final Answer[:：]\s*\n*([\s\S]*)$/i)
  if (chineseFinalMatch) {
    return chineseFinalMatch[1].trim()
  }
  
  // If it starts with ## or # or >, it may be direct markdown content
  const trimmedResponse = response.trim()
  if (trimmedResponse.match(/^[#>]/)) {
    return trimmedResponse
  }
  
  // If content is long and contains markdown formatting, try removing thinking process and return
  if (response.length > 300 && (response.includes('**') || response.includes('>'))) {
    // Remove Thought: prefix thinking process
    const thoughtMatch = response.match(/^Thought:[\s\S]*?(?=\n\n[^T]|\n\n$)/i)
    if (thoughtMatch) {
      const afterThought = response.substring(thoughtMatch[0].length).trim()
      if (afterThought.length > 100) {
        return afterThought
      }
    }
  }
  
  return null
}

const fetchConsoleLog = async () => {
  if (!props.reportId) return
  
  try {
    const res = await getConsoleLog(props.reportId, consoleLogLine.value)
    
    if (res.success && res.data) {
      const newLogs = res.data.logs || []
      
      if (newLogs.length > 0) {
        consoleLogs.value.push(...newLogs)
        consoleLogLine.value = res.data.from_line + newLogs.length
        
        nextTick(() => {
          if (logContent.value) {
            logContent.value.scrollTop = logContent.value.scrollHeight
          }
        })
      }
    }
  } catch (err) {
    console.warn('Failed to fetch console log:', err)
  }
}

const startPolling = () => {
  if (agentLogTimer || consoleLogTimer) return
  
  fetchAgentLog()
  fetchConsoleLog()
  
  agentLogTimer = setInterval(fetchAgentLog, 2000)
  consoleLogTimer = setInterval(fetchConsoleLog, 1500)
}

const stopPolling = () => {
  if (agentLogTimer) {
    clearInterval(agentLogTimer)
    agentLogTimer = null
  }
  if (consoleLogTimer) {
    clearInterval(consoleLogTimer)
    consoleLogTimer = null
  }
}

// Lifecycle
onMounted(() => {
  if (props.reportId) {
    addLog(`Report Agent initialized: ${props.reportId}`)
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})

watch(() => props.reportId, (newId) => {
  if (newId) {
    agentLogs.value = []
    consoleLogs.value = []
    agentLogLine.value = 0
    consoleLogLine.value = 0
    reportOutline.value = null
    currentSectionIndex.value = null
    generatedSections.value = {}
    expandedContent.value = new Set()
    expandedLogs.value = new Set()
    collapsedSections.value = new Set()
    isComplete.value = false
    startTime.value = null
    
    startPolling()
  }
}, { immediate: true })
</script>

<style scoped>
.report-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-gray, #F5F5F5);
  font-family: var(--font-mono);
  overflow: hidden;
}

/* Main Split Layout */
.main-split-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Panel Headers */
.panel-header {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 22px;
  background: #FAFAFA;
  border-bottom: 2px solid rgba(10,10,10,0.12);
  font-size: 13px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.7);
  text-transform: uppercase;
  letter-spacing: 3px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #0A0A0A;
  border: 2px solid rgba(10,10,10,0.08);
  margin-right: 11px;
  flex-shrink: 0;
  animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% {
    border-color: rgba(10,10,10,0.08);
  }
  50% {
    border-color: rgba(10,10,10,0.2);
  }
}

.header-index {
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  margin-right: 11px;
  flex-shrink: 0;
}

.header-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(10,10,10,0.7);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-transform: none;
  letter-spacing: 0;
}

.header-meta {
  margin-left: auto;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.5);
  flex-shrink: 0;
}

/* Panel header status variants */
.panel-header--active {
  background: #FAFAFA;
  border-color: #FF6B1A;
}

.panel-header--active .header-index {
  color: #FF6B1A;
}

.panel-header--active .header-title {
  color: #0A0A0A;
}

.panel-header--active .header-meta {
  color: #0A0A0A;
}

.panel-header--done {
  background: #FAFAFA;
}

.panel-header--done .header-index {
  color: #43C165;
}

.panel-header--todo .header-index,
.panel-header--todo .header-title {
  color: rgba(10,10,10,0.4);
}

/* Left Panel - Report Style */
.left-panel.report-style {
  width: 45%;
  min-width: 450px;
  background: #FAFAFA;
  border-right: 2px solid rgba(10,10,10,0.12);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  padding: 34px 56px 56px 56px;
}

.left-panel::-webkit-scrollbar {
  width: 6px;
}

.left-panel::-webkit-scrollbar-track {
  background: transparent;
}

.left-panel::-webkit-scrollbar-thumb {
  background: transparent;
  transition: background 0.3s ease;
}

.left-panel:hover::-webkit-scrollbar-thumb {
  background: rgba(10,10,10,0.15);
}

.left-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(10,10,10,0.25);
}

/* Report Header */
.report-content-wrapper {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}

.report-header-block {
  margin-bottom: 34px;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 22px;
}

.report-tag {
  background: #0A0A0A;
  color: #FAFAFA;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 6px 11px;
  letter-spacing: 3px;
  text-transform: uppercase;
}

.report-id {
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
  font-weight: 500;
  letter-spacing: 0.02em;
}

.report-id.copyable {
  cursor: pointer;
}

.report-id.copyable:hover {
  color: rgba(10,10,10,0.5);
  text-decoration: underline;
}

.report-id.copyable:active {
  color: #43C165;
}

.main-title {
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 700;
  color: #0A0A0A;
  line-height: 1.2;
  margin: 0 0 22px 0;
  letter-spacing: -0.02em;
}

.sub-title {
  font-family: var(--font-display);
  font-size: 16px;
  color: rgba(10,10,10,0.5);
  font-style: italic;
  line-height: 1.6;
  margin: 0 0 34px 0;
  font-weight: 400;
}

.header-divider {
  height: 2px;
  background: rgba(10,10,10,0.12);
  width: 100%;
}

/* Sections List */
.sections-list {
  display: flex;
  flex-direction: column;
  gap: 34px;
}

.report-section-item {
  display: flex;
  flex-direction: column;
  gap: 11px;
}

.section-header-row {
  display: flex;
  align-items: baseline;
  gap: 11px;
  transition: background-color 0.2s ease;
  padding: 6px 11px;
  margin: -6px -11px;
}

.section-header-row.clickable {
  cursor: pointer;
}

.section-header-row.clickable:hover {
  background-color: var(--color-gray, #F5F5F5);
}

.collapse-icon {
  margin-left: auto;
  color: rgba(10,10,10,0.4);
  transition: transform 0.3s ease;
  flex-shrink: 0;
  align-self: center;
}

.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
}

.section-number {
  font-family: var(--font-mono);
  font-size: 16px;
  color: rgba(10,10,10,0.4); /* Dark gray, does not change with state */
  font-weight: 500;
}

.section-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 600;
  color: #0A0A0A;
  margin: 0;
  transition: color 0.3s ease;
}

/* States */
.report-section-item.is-pending .section-title {
  color: rgba(10,10,10,0.2);
}

.report-section-item.is-active .section-title,
.report-section-item.is-completed .section-title {
  color: #0A0A0A;
}

.section-body {
  padding-left: 22px;
  overflow: hidden;
}

/* Generated Content */
.generated-content {
  font-family: var(--font-display);
  font-size: 14px;
  line-height: 1.8;
  color: rgba(10,10,10,0.7);
}

.generated-content :deep(p) {
  margin-bottom: 1em;
}

.generated-content :deep(.md-h2),
.generated-content :deep(.md-h3),
.generated-content :deep(.md-h4) {
  font-family: var(--font-display);
  color: #0A0A0A;
  margin-top: 1.5em;
  margin-bottom: 0.8em;
  font-weight: 700;
}

.generated-content :deep(.md-h2) { font-size: 20px; border-bottom: 2px solid rgba(10,10,10,0.08); padding-bottom: 6px; }
.generated-content :deep(.md-h3) { font-size: 18px; }
.generated-content :deep(.md-h4) { font-size: 16px; }

.generated-content :deep(.md-ul),
.generated-content :deep(.md-ol) {
  padding-left: 22px;
  margin: 11px 0;
}

.generated-content :deep(.md-li),
.generated-content :deep(.md-oli) {
  margin: 6px 0;
}

.generated-content :deep(.md-quote) {
  border-left: 3px solid rgba(10,10,10,0.12);
  padding-left: 22px;
  margin: 1.5em 0;
  color: rgba(10,10,10,0.5);
  font-style: italic;
  font-family: var(--font-display);
}

.generated-content :deep(.code-block) {
  background: var(--color-gray, #F5F5F5);
  padding: 11px;
  font-family: var(--font-mono);
  font-size: 12px;
  overflow-x: auto;
  margin: 1em 0;
  border: 2px solid rgba(10,10,10,0.08);
}

.generated-content :deep(strong) {
  font-weight: 600;
  color: #0A0A0A;
}

/* Loading State */
.loading-state {
  display: flex;
  align-items: center;
  gap: 11px;
  color: rgba(10,10,10,0.5);
  font-size: 14px;
  margin-top: 6px;
}

.loading-icon {
  width: 18px;
  height: 18px;
  animation: spin 1s linear infinite;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-text {
  font-family: var(--font-mono);
  font-size: 15px;
  color: rgba(10,10,10,0.5);
}

.cursor-blink {
  display: inline-block;
  width: 8px;
  height: 14px;
  background: #FF6B1A;
  opacity: 0.5;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 0; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Content Styles Override for this view */
.generated-content :deep(.md-h2) {
  font-family: var(--font-display);
  font-size: 18px;
  margin-top: 0;
}


/* Slide Content Transition */
.slide-content-enter-active {
  transition: opacity 0.3s ease-out;
}

.slide-content-leave-active {
  transition: opacity 0.2s ease-in;
}

.slide-content-enter-from,
.slide-content-leave-to {
  opacity: 0;
}

.slide-content-enter-to,
.slide-content-leave-from {
  opacity: 1;
}

/* Waiting Placeholder */
.waiting-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 22px;
  padding: 34px;
  color: rgba(10,10,10,0.4);
}

.waiting-animation {
  position: relative;
  width: 48px;
  height: 48px;
}

.waiting-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border: 2px solid rgba(10,10,10,0.12);
  border-radius: 50%;
  animation: ripple 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

.waiting-ring:nth-child(2) {
  animation-delay: 0.4s;
}

.waiting-ring:nth-child(3) {
  animation-delay: 0.8s;
}

@keyframes ripple {
  0% { transform: scale(0.5); opacity: 1; }
  100% { transform: scale(2); opacity: 0; }
}

.waiting-text {
  font-size: 14px;
  font-family: var(--font-mono);
}

/* Right Panel */
.right-panel {
  flex: 1;
  background: #FAFAFA;
  overflow-y: auto;
  display: flex;
  flex-direction: column;

  /* Functional palette (low saturation, status-based) */
  --wf-border: rgba(10,10,10,0.12);
  --wf-divider: rgba(10,10,10,0.08);

  --wf-active-bg: #FAFAFA;
  --wf-active-border: #FF6B1A;
  --wf-active-dot: #FF6B1A;
  --wf-active-text: #0A0A0A;

  --wf-done-bg: #FAFAFA;
  --wf-done-border: rgba(10,10,10,0.12);
  --wf-done-dot: #43C165;

  --wf-muted-dot: rgba(10,10,10,0.2);
  --wf-todo-text: rgba(10,10,10,0.4);
}

.right-panel::-webkit-scrollbar {
  width: 6px;
}

.right-panel::-webkit-scrollbar-track {
  background: transparent;
}

.right-panel::-webkit-scrollbar-thumb {
  background: transparent;
  transition: background 0.3s ease;
}

.right-panel:hover::-webkit-scrollbar-thumb {
  background: rgba(10,10,10,0.15);
}

.right-panel::-webkit-scrollbar-thumb:hover {
  background: rgba(10,10,10,0.25);
}

.mono {
  font-family: var(--font-mono);
}

/* Workflow Overview */
.workflow-overview {
  padding: 22px 22px 0 22px;
}

.workflow-metrics {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 11px;
  margin-bottom: 11px;
}

.metric {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}

.metric-right {
  margin-left: auto;
}

.metric-label {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
}

.metric-value {
  font-size: 12px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.7);
}

.metric-pill {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  padding: 6px 11px;
  border: 2px solid var(--wf-border);
  background: var(--color-gray, #F5F5F5);
  color: rgba(10,10,10,0.5);
}

.metric-pill.pill--processing {
  background: var(--wf-active-bg);
  border-color: var(--wf-active-border);
  color: var(--wf-active-text);
}

.metric-pill.pill--completed {
  background: rgba(67,193,101,0.1);
  border-color: #43C165;
  color: #43C165;
}

.metric-pill.pill--pending {
  background: transparent;
  border-style: dashed;
  color: rgba(10,10,10,0.5);
}

.workflow-steps {
  display: flex;
  flex-direction: column;
  gap: 11px;
  padding-bottom: 11px;
}

.wf-step {
  display: grid;
  grid-template-columns: 24px 1fr;
  gap: 11px;
  padding: 11px;
  border: 2px solid var(--wf-divider);
  background: #FAFAFA;
}

.wf-step--active {
  background: var(--wf-active-bg);
  border-color: var(--wf-active-border);
}

.wf-step--done {
  background: var(--wf-done-bg);
  border-color: var(--wf-done-border);
}

.wf-step--todo {
  background: transparent;
  border-color: var(--wf-border);
  border-style: dashed;
}

.wf-step-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 24px;
  flex-shrink: 0;
}

.wf-step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--wf-muted-dot);
  border: 2px solid #FAFAFA;
  z-index: 1;
}

.wf-step-line {
  width: 2px;
  flex: 1;
  background: var(--wf-divider);
  margin-top: -2px;
}

.wf-step--active .wf-step-dot {
  background: var(--wf-active-dot);
  border: 2px solid rgba(255,107,26,0.2);
}

.wf-step--done .wf-step-dot {
  background: var(--wf-done-dot);
}

.wf-step-title-row {
  display: flex;
  align-items: baseline;
  gap: 11px;
  min-width: 0;
}

.wf-step-index {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: rgba(10,10,10,0.4);
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

.wf-step-title {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: #0A0A0A;
  line-height: 1.35;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wf-step-meta {
  margin-left: auto;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--wf-active-text);
  text-transform: uppercase;
  letter-spacing: 3px;
  flex-shrink: 0;
}

.wf-step--todo .wf-step-title,
.wf-step--todo .wf-step-index {
  color: var(--wf-todo-text);
}

.workflow-divider {
  height: 2px;
  background: var(--wf-divider);
  margin: 11px 0 0 0;
}

/* Workflow Timeline */
.workflow-timeline {
  padding: 11px 22px 22px;
  flex: 1;
}

.timeline-item {
  display: grid;
  grid-template-columns: 24px 1fr;
  gap: 11px;
  padding: 11px;
  margin-bottom: 11px;
  border: 2px solid var(--wf-divider);
  background: #FAFAFA;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.timeline-item:hover {
  background: var(--color-gray, #F5F5F5);
  border-color: var(--wf-border);
}

.timeline-item.node--active {
  background: var(--wf-active-bg);
  border-color: var(--wf-active-border);
}

.timeline-item.node--active:hover {
  background: var(--wf-active-bg);
  border-color: var(--wf-active-border);
}

.timeline-item.node--done {
  background: var(--wf-done-bg);
  border-color: var(--wf-done-border);
}

.timeline-item.node--done:hover {
  background: var(--wf-done-bg);
  border-color: var(--wf-done-border);
}

.timeline-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 24px;
  flex-shrink: 0;
}

.connector-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--wf-muted-dot);
  border: 2px solid #FAFAFA;
  z-index: 1;
}

.connector-line {
  width: 2px;
  flex: 1;
  background: var(--wf-divider);
  margin-top: -2px;
}

/* Connector dot: status only */
.dot-active {
  background: var(--wf-active-dot);
  border: 2px solid rgba(255,107,26,0.2);
}

.dot-done {
  background: var(--wf-done-dot);
}

.dot-muted {
  background: var(--wf-muted-dot);
}

.timeline-content {
  min-width: 0;
  background: transparent;
  border: none;
  padding: 0;
  margin: 0;
  transition: none;
}

.timeline-content:hover {
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 11px;
}

.action-label {
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.7);
  text-transform: uppercase;
  letter-spacing: 3px;
}

.action-time {
  font-size: 11px;
  color: rgba(10,10,10,0.4);
  font-family: var(--font-mono);
}

.timeline-body {
  font-size: 13px;
  color: rgba(10,10,10,0.5);
}

.timeline-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 11px;
  padding-top: 11px;
  border-top: 2px solid rgba(10,10,10,0.08);
}

.elapsed-placeholder {
  flex-shrink: 0;
}

.footer-actions {
  display: flex;
  gap: 6px;
  margin-left: auto;
}

.elapsed-badge {
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  background: var(--color-gray, #F5F5F5);
  padding: 2px 6px;
  font-family: var(--font-mono);
}

/* Timeline Body Elements */
.info-row {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}

.info-key {
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
  min-width: 80px;
}

.info-val {
  color: rgba(10,10,10,0.7);
}

.status-message {
  padding: 6px 11px;
  font-size: 13px;
  border: 2px solid transparent;
}

.status-message.planning {
  background: var(--wf-active-bg);
  border-color: var(--wf-active-border);
  color: var(--wf-active-text);
}

.status-message.success {
  background: rgba(67,193,101,0.1);
  border-color: #43C165;
  color: #43C165;
}

.outline-badge {
  display: inline-block;
  margin-top: 6px;
  padding: 6px 11px;
  background: var(--color-gray, #F5F5F5);
  color: rgba(10,10,10,0.5);
  border: 2px solid rgba(10,10,10,0.12);
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
}

.section-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid var(--wf-border);
}

.section-tag.content-ready {
  background: var(--wf-active-bg);
  border: 2px dashed var(--wf-active-border);
}

.section-tag.content-ready svg {
  color: var(--wf-active-dot);
}


.section-tag.completed {
  background: rgba(67,193,101,0.1);
  border: 2px solid #43C165;
}

.section-tag.completed svg {
  color: #43C165;
}

.tag-num {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: rgba(10,10,10,0.5);
}

.section-tag.completed .tag-num {
  color: #43C165;
}

.tag-title {
  font-size: 13px;
  font-weight: 500;
  color: rgba(10,10,10,0.7);
}

.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 11px;
  background: var(--color-gray, #F5F5F5);
  color: rgba(10,10,10,0.7);
  border: 2px solid var(--wf-border);
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 600;
  transition: all 0.2s ease;
}

.tool-icon {
  flex-shrink: 0;
}

/* Tool Colors - Purple (Deep Insight) */
.tool-badge.tool-purple {
  background: rgba(139, 92, 246, 0.08);
  border-color: rgba(139, 92, 246, 0.3);
  color: #6D28D9;
}
.tool-badge.tool-purple .tool-icon {
  stroke: #7C3AED;
}

/* Tool Colors - Blue (Panorama Search) → Orange */
.tool-badge.tool-blue {
  background: rgba(255,107,26,0.1);
  border-color: rgba(255,107,26,0.3);
  color: #FF6B1A;
}
.tool-badge.tool-blue .tool-icon {
  stroke: #FF6B1A;
}

/* Tool Colors - Green (Agent Interview) */
.tool-badge.tool-green {
  background: rgba(67,193,101,0.1);
  border-color: rgba(67,193,101,0.3);
  color: #43C165;
}
.tool-badge.tool-green .tool-icon {
  stroke: #43C165;
}

/* Tool Colors - Orange (Quick Search) */
.tool-badge.tool-orange {
  background: rgba(255,107,26,0.1);
  border-color: rgba(255,107,26,0.3);
  color: #FF6B1A;
}
.tool-badge.tool-orange .tool-icon {
  stroke: #FF6B1A;
}

/* Tool Colors - Cyan (Graph Stats) */
.tool-badge.tool-cyan {
  background: rgba(14, 116, 144, 0.08);
  border-color: rgba(14, 116, 144, 0.3);
  color: #0E7490;
}
.tool-badge.tool-cyan .tool-icon {
  stroke: #0891B2;
}

/* Tool Colors - Pink (Entity Query) */
.tool-badge.tool-pink {
  background: rgba(190, 24, 93, 0.08);
  border-color: rgba(190, 24, 93, 0.3);
  color: #BE185D;
}
.tool-badge.tool-pink .tool-icon {
  stroke: #DB2777;
}

/* Tool Colors - Gray (Default) */
.tool-badge.tool-gray {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.2);
  color: rgba(10,10,10,0.7);
}
.tool-badge.tool-gray .tool-icon {
  stroke: rgba(10,10,10,0.5);
}

.tool-params {
  margin-top: 11px;
  background: transparent;
  padding: 11px 0 0 0;
  border-top: 1px dashed var(--wf-divider);
  overflow-x: auto;
}

.tool-params pre {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  padding: 11px;
}

/* Unified Action Buttons */
.action-btn {
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  padding: 6px 11px;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.5);
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.action-btn:hover {
  background: rgba(10,10,10,0.08);
  color: rgba(10,10,10,0.7);
  border-color: rgba(10,10,10,0.12);
}

/* Result Wrapper */
.result-wrapper {
  background: transparent;
  border: none;
  border-top: 2px solid var(--wf-divider);
  padding: 11px 0 0 0;
}

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 11px;
}

.result-tool {
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

.result-size {
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  font-family: var(--font-mono);
}

.result-raw {
  margin-top: 11px;
  max-height: 300px;
  overflow-y: auto;
}

.result-raw pre {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
  color: rgba(10,10,10,0.7);
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  padding: 11px;
}

.raw-preview {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
  color: rgba(10,10,10,0.5);
}

/* Legacy toggle-raw removed - using unified .action-btn */

/* LLM Response */
.llm-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.meta-tag {
  font-size: 11px;
  font-family: var(--font-mono);
  padding: 3px 6px;
  background: var(--color-gray, #F5F5F5);
  color: rgba(10,10,10,0.5);
}

.meta-tag.active {
  background: rgba(255,107,26,0.1);
  color: #FF6B1A;
}

.meta-tag.final-answer {
  background: rgba(67,193,101,0.1);
  color: #43C165;
  font-weight: 600;
}

.final-answer-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 11px;
  padding: 11px;
  background: rgba(67,193,101,0.1);
  border: 2px solid #43C165;
  color: #43C165;
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 500;
}

.final-answer-hint svg {
  flex-shrink: 0;
}

.llm-content {
  margin-top: 11px;
  max-height: 200px;
  overflow-y: auto;
}

.llm-content pre {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
  color: rgba(10,10,10,0.5);
  background: var(--color-gray, #F5F5F5);
  padding: 11px;
}

/* Complete Banner */
.complete-banner {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 22px;
  background: rgba(67,193,101,0.1);
  border: 2px solid #43C165;
  color: #43C165;
  font-weight: 600;
  font-family: var(--font-mono);
  font-size: 14px;
}

.next-step-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: calc(100% - 44px);
  margin: 6px 22px 0 22px;
  padding: 11px 22px;
  font-size: 14px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: #FAFAFA;
  background: #0A0A0A;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.next-step-btn:hover {
  background: rgba(10,10,10,0.7);
}

.next-step-btn svg {
  transition: transform 0.2s ease;
}

.next-step-btn:hover svg {
  transform: translateX(4px);
}

/* Export Buttons */
.export-buttons {
  display: flex;
  gap: 8px;
  margin: 8px 20px 0 20px;
}

.export-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex: 1;
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 500;
  color: #6B7280;
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.export-btn:hover:not(:disabled) {
  color: #374151;
  background: #F3F4F6;
  border-color: #D1D5DB;
}

.export-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Workflow Empty */
.workflow-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 56px 22px;
  color: rgba(10,10,10,0.4);
  font-size: 13px;
  font-family: var(--font-mono);
}

.empty-pulse {
  width: 24px;
  height: 24px;
  background: rgba(10,10,10,0.12);
  border-radius: 50%;
  margin-bottom: 22px;
  animation: pulse-ring 1.5s infinite;
}

@keyframes pulse-ring {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.5; }
}

/* Timeline Transitions */
.timeline-item-enter-active {
  transition: all 0.4s ease;
}

.timeline-item-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

/* ========== Structured Result Display Components ========== */

/* Common Styles - using :deep() for dynamic components */
:deep(.stat-row) {
  display: flex;
  gap: 6px;
  margin-bottom: 11px;
}

:deep(.stat-box) {
  flex: 1;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  padding: 11px 6px;
  text-align: center;
}

:deep(.stat-box .stat-num) {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #0A0A0A;
  font-family: var(--font-mono);
}

:deep(.stat-box .stat-label) {
  display: block;
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
  margin-top: 2px;
  text-transform: uppercase;
  letter-spacing: 3px;
}

:deep(.stat-box.highlight) {
  background: rgba(67,193,101,0.1);
  border-color: #43C165;
}

:deep(.stat-box.highlight .stat-num) {
  color: #43C165;
}

:deep(.stat-box.muted) {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.08);
}

:deep(.stat-box.muted .stat-num) {
  color: rgba(10,10,10,0.5);
}

:deep(.query-display) {
  background: var(--color-gray, #F5F5F5);
  padding: 11px;
  font-size: 12px;
  color: rgba(10,10,10,0.7);
  margin-bottom: 11px;
  border: 2px solid rgba(10,10,10,0.08);
  line-height: 1.5;
}

:deep(.expand-details) {
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  padding: 6px 11px;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.5);
  cursor: pointer;
  transition: all 0.15s ease;
  text-transform: uppercase;
  letter-spacing: 3px;
}

:deep(.expand-details:hover) {
  border-color: rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.7);
}

:deep(.detail-content) {
  margin-top: 11px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  padding: 11px;
}

:deep(.section-label) {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.5);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 11px;
  padding-bottom: 6px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

/* Facts Section */
:deep(.facts-section) {
  margin-bottom: 11px;
}

:deep(.fact-row) {
  display: flex;
  gap: 11px;
  padding: 6px 0;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

:deep(.fact-row:last-child) {
  border-bottom: none;
}

:deep(.fact-row.active) {
  background: rgba(67,193,101,0.1);
  margin: 0 -11px;
  padding: 6px 11px;
  border-bottom: none;
}

:deep(.fact-idx) {
  min-width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-gray, #F5F5F5);
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: rgba(10,10,10,0.5);
  flex-shrink: 0;
}

:deep(.fact-row.active .fact-idx) {
  background: #43C165;
  color: #FAFAFA;
}

:deep(.fact-text) {
  font-size: 12px;
  color: rgba(10,10,10,0.5);
  line-height: 1.6;
}

/* Entities Section */
:deep(.entities-section) {
  margin-bottom: 11px;
}

:deep(.entity-chips) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.entity-chip) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  padding: 6px 11px;
}

:deep(.chip-name) {
  font-size: 12px;
  font-weight: 500;
  color: #0A0A0A;
}

:deep(.chip-type) {
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
  background: rgba(10,10,10,0.08);
  padding: 1px 6px;
}

/* Relations Section */
:deep(.relations-section) {
  margin-bottom: 11px;
}

:deep(.relation-row) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 0;
  flex-wrap: wrap;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

:deep(.relation-row:last-child) {
  border-bottom: none;
}

:deep(.rel-node) {
  font-size: 12px;
  font-weight: 500;
  color: #0A0A0A;
  background: var(--color-gray, #F5F5F5);
  padding: 6px 11px;
}

:deep(.rel-edge) {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: #FAFAFA;
  background: #FF6B1A;
  padding: 3px 11px;
}

/* ========== Interview Display - Conversation Style ========== */
:deep(.interview-display) {
  padding: 0;
}

/* Header */
:deep(.interview-display .interview-header) {
  padding: 0;
  background: transparent;
  border-bottom: none;
  margin-bottom: 22px;
}

:deep(.interview-display .header-main) {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

:deep(.interview-display .header-title) {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: #0A0A0A;
  letter-spacing: -0.01em;
}

:deep(.interview-display .header-stats) {
  display: flex;
  align-items: center;
  gap: 6px;
}

:deep(.interview-display .stat-item) {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

:deep(.interview-display .stat-value) {
  font-size: 14px;
  font-weight: 600;
  color: #FF6B1A;
  font-family: var(--font-mono);
}

:deep(.interview-display .stat-label) {
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
  text-transform: lowercase;
}

:deep(.interview-display .stat-divider) {
  color: rgba(10,10,10,0.2);
  font-size: 12px;
}

:deep(.interview-display .stat-size) {
  font-size: 11px;
  color: rgba(10,10,10,0.4);
  font-family: var(--font-mono);
}

:deep(.interview-display .header-topic) {
  margin-top: 6px;
  font-size: 12px;
  color: rgba(10,10,10,0.5);
  line-height: 1.5;
}

/* Agent Tabs - Card Style */
:deep(.interview-display .agent-tabs) {
  display: flex;
  gap: 6px;
  padding: 0 0 11px 0;
  background: transparent;
  border-bottom: 2px solid rgba(10,10,10,0.08);
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
  scrollbar-color: rgba(10,10,10,0.12) transparent;
}

:deep(.interview-display .agent-tabs::-webkit-scrollbar) {
  height: 4px;
}

:deep(.interview-display .agent-tabs::-webkit-scrollbar-track) {
  background: transparent;
}

:deep(.interview-display .agent-tabs::-webkit-scrollbar-thumb) {
  background: rgba(10,10,10,0.12);
}

:deep(.interview-display .agent-tabs::-webkit-scrollbar-thumb:hover) {
  background: rgba(10,10,10,0.2);
}

:deep(.interview-display .agent-tab) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.5);
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

:deep(.interview-display .agent-tab:hover) {
  background: rgba(10,10,10,0.08);
  border-color: rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.7);
}

:deep(.interview-display .agent-tab.active) {
  background: rgba(255,107,26,0.1);
  border-color: #FF6B1A;
  color: #FF6B1A;
}

:deep(.interview-display .tab-avatar) {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.5);
  font-size: 10px;
  font-weight: 700;
  border-radius: 50%;
  flex-shrink: 0;
}

:deep(.interview-display .agent-tab:hover .tab-avatar) {
  background: rgba(10,10,10,0.2);
}

:deep(.interview-display .agent-tab.active .tab-avatar) {
  background: #FF6B1A;
  color: #FAFAFA;
}

:deep(.interview-display .tab-name) {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Interview Detail */
:deep(.interview-display .interview-detail) {
  padding: 11px 0;
  background: transparent;
}

/* Agent Profile - No card */
:deep(.interview-display .agent-profile) {
  display: flex;
  gap: 11px;
  padding: 0;
  background: transparent;
  border: none;
  margin-bottom: 22px;
}

:deep(.interview-display .profile-avatar) {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.5);
  font-size: 14px;
  font-weight: 600;
  border-radius: 50%;
  flex-shrink: 0;
}

:deep(.interview-display .profile-info) {
  flex: 1;
  min-width: 0;
}

:deep(.interview-display .profile-name) {
  font-size: 13px;
  font-weight: 600;
  color: #0A0A0A;
  margin-bottom: 2px;
}

:deep(.interview-display .profile-role) {
  font-size: 11px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.5);
  margin-bottom: 4px;
}

:deep(.interview-display .profile-bio) {
  font-size: 11px;
  color: rgba(10,10,10,0.4);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Selection Reason */
:deep(.interview-display .selection-reason) {
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  padding: 11px;
  margin-bottom: 22px;
}

:deep(.interview-display .reason-label) {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.5);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 6px;
}

:deep(.interview-display .reason-content) {
  font-size: 12px;
  color: rgba(10,10,10,0.5);
  line-height: 1.6;
}

/* Q&A Thread - Clean list */
:deep(.interview-display .qa-thread) {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

:deep(.interview-display .qa-pair) {
  display: flex;
  flex-direction: column;
  gap: 11px;
  padding: 0;
  background: transparent;
  border: none;
}

:deep(.interview-display .qa-question),
:deep(.interview-display .qa-answer) {
  display: flex;
  gap: 11px;
}

:deep(.interview-display .qa-badge) {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
}

:deep(.interview-display .q-badge) {
  background: transparent;
  color: rgba(10,10,10,0.4);
  border: 2px solid rgba(10,10,10,0.12);
}

:deep(.interview-display .a-badge) {
  background: #FF6B1A;
  color: #FAFAFA;
  border: 2px solid #FF6B1A;
}

:deep(.interview-display .qa-content) {
  flex: 1;
  min-width: 0;
}

:deep(.interview-display .qa-sender) {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 3px;
}

:deep(.interview-display .qa-text) {
  font-size: 13px;
  color: rgba(10,10,10,0.7);
  line-height: 1.6;
}

:deep(.interview-display .qa-answer) {
  background: transparent;
  padding: 0;
  border: none;
  margin-top: 0;
}

:deep(.interview-display .answer-placeholder) {
  opacity: 0.6;
}

:deep(.interview-display .placeholder-text) {
  font-style: italic;
  color: rgba(10,10,10,0.4);
}

:deep(.interview-display .qa-answer-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

/* Platform Switch */
:deep(.interview-display .platform-switch) {
  display: flex;
  gap: 2px;
  background: transparent;
  padding: 0;
}

:deep(.interview-display .platform-btn) {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  background: transparent;
  border: 2px solid transparent;
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.4);
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.interview-display .platform-btn:hover) {
  color: rgba(10,10,10,0.5);
}

:deep(.interview-display .platform-btn.active) {
  background: transparent;
  color: #FF6B1A;
  border-color: rgba(10,10,10,0.08);
}

:deep(.interview-display .platform-icon) {
  flex-shrink: 0;
}

:deep(.interview-display .answer-text) {
  font-size: 13px;
  color: #0A0A0A;
  line-height: 1.6;
}

:deep(.interview-display .answer-text strong) {
  color: #0A0A0A;
  font-weight: 600;
}

:deep(.interview-display .expand-answer-btn) {
  display: inline-block;
  margin-top: 6px;
  padding: 0;
  background: transparent;
  border: none;
  border-bottom: 1px dotted rgba(10,10,10,0.2);
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.4);
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.interview-display .expand-answer-btn:hover) {
  background: transparent;
  color: rgba(10,10,10,0.5);
  border-bottom-style: solid;
}

/* Quotes Section - Clean list */
:deep(.interview-display .quotes-section) {
  background: transparent;
  border: none;
  border-top: 2px solid rgba(10,10,10,0.08);
  padding: 22px 0 0 0;
  margin-top: 22px;
}

:deep(.interview-display .quotes-header) {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 11px;
}

:deep(.interview-display .quotes-list) {
  display: flex;
  flex-direction: column;
  gap: 11px;
}

:deep(.interview-display .quote-item) {
  margin: 0;
  padding: 11px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  font-size: 12px;
  font-style: italic;
  color: rgba(10,10,10,0.5);
  line-height: 1.5;
}

/* Summary Section */
:deep(.interview-display .summary-section) {
  margin-top: 22px;
  padding: 22px 0 0 0;
  background: transparent;
  border: none;
  border-top: 2px solid rgba(10,10,10,0.08);
}

:deep(.interview-display .summary-header) {
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 6px;
}

:deep(.interview-display .summary-content) {
  font-size: 13px;
  color: rgba(10,10,10,0.7);
  line-height: 1.6;
}

/* Markdown styles in summary */
:deep(.interview-display .summary-content h2),
:deep(.interview-display .summary-content h3),
:deep(.interview-display .summary-content h4),
:deep(.interview-display .summary-content h5) {
  margin: 11px 0 6px 0;
  font-weight: 600;
  color: #0A0A0A;
}

:deep(.interview-display .summary-content h2) {
  font-size: 15px;
}

:deep(.interview-display .summary-content h3) {
  font-size: 14px;
}

:deep(.interview-display .summary-content h4),
:deep(.interview-display .summary-content h5) {
  font-size: 13px;
}

:deep(.interview-display .summary-content p) {
  margin: 6px 0;
}

:deep(.interview-display .summary-content strong) {
  font-weight: 600;
  color: #0A0A0A;
}

:deep(.interview-display .summary-content em) {
  font-style: italic;
}

:deep(.interview-display .summary-content ul),
:deep(.interview-display .summary-content ol) {
  margin: 6px 0;
  padding-left: 22px;
}

:deep(.interview-display .summary-content li) {
  margin: 4px 0;
}

:deep(.interview-display .summary-content blockquote) {
  margin: 6px 0;
  padding-left: 11px;
  border-left: 3px solid rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.5);
  font-style: italic;
}

/* Markdown styles in quotes */
:deep(.interview-display .quote-item strong) {
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

:deep(.interview-display .quote-item em) {
  font-style: italic;
}

/* ========== Enhanced Insight Display Styles ========== */
:deep(.insight-display) {
  padding: 0;
}

:deep(.insight-header) {
  padding: 11px 22px;
  background: rgba(139, 92, 246, 0.08);
  border: 2px solid rgba(139, 92, 246, 0.3);
  border-bottom: none;
}

:deep(.insight-header .header-main) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

:deep(.insight-header .header-title) {
  font-size: 14px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: #6D28D9;
}

:deep(.insight-header .header-stats) {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

:deep(.insight-header .stat-item) {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

:deep(.insight-header .stat-value) {
  font-family: var(--font-mono);
  font-weight: 700;
  color: #7C3AED;
}

:deep(.insight-header .stat-label) {
  color: #8B5CF6;
  font-size: 10px;
  font-family: var(--font-mono);
}

:deep(.insight-header .stat-divider) {
  color: #C4B5FD;
  margin: 0 4px;
}

:deep(.insight-header .stat-size) {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
}

:deep(.insight-header .header-topic) {
  font-size: 13px;
  color: #5B21B6;
  line-height: 1.5;
}

:deep(.insight-header .header-scenario) {
  margin-top: 6px;
  font-size: 11px;
  color: #7C3AED;
}

:deep(.insight-header .scenario-label) {
  font-weight: 600;
}

:deep(.insight-tabs) {
  display: flex;
  gap: 2px;
  padding: 6px 11px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  border-top: none;
}

:deep(.insight-tab) {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 11px;
  background: transparent;
  border: 2px solid transparent;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.5);
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.insight-tab:hover) {
  background: rgba(10,10,10,0.08);
  color: rgba(10,10,10,0.7);
}

:deep(.insight-tab.active) {
  background: #FAFAFA;
  color: #7C3AED;
  border-color: #C4B5FD;
}


:deep(.insight-content) {
  padding: 11px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  border-top: none;
}

:deep(.insight-display .panel-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 11px;
  padding-bottom: 6px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

:deep(.insight-display .panel-title) {
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

:deep(.insight-display .panel-count) {
  font-size: 10px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
}

:deep(.insight-display .facts-list),
:deep(.insight-display .relations-list),
:deep(.insight-display .subqueries-list) {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

:deep(.insight-display .entities-grid) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.insight-display .fact-item) {
  display: flex;
  gap: 11px;
  padding: 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
}

:deep(.insight-display .fact-number) {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10,10,10,0.12);
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: rgba(10,10,10,0.5);
}

:deep(.insight-display .fact-content) {
  flex: 1;
  font-size: 12px;
  color: rgba(10,10,10,0.7);
  line-height: 1.6;
}

/* Entity Tag Styles - Compact multi-column layout */
:deep(.insight-display .entity-tag) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 6px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  cursor: default;
  transition: all 0.15s ease;
}

:deep(.insight-display .entity-tag:hover) {
  background: rgba(10,10,10,0.08);
  border-color: rgba(10,10,10,0.12);
}

:deep(.insight-display .entity-tag .entity-name) {
  font-size: 12px;
  font-weight: 500;
  color: #0A0A0A;
}

:deep(.insight-display .entity-tag .entity-type) {
  font-size: 9px;
  font-family: var(--font-mono);
  color: #7C3AED;
  background: rgba(139, 92, 246, 0.1);
  padding: 1px 4px;
}

:deep(.insight-display .entity-tag .entity-fact-count) {
  font-size: 9px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
  margin-left: 2px;
}

/* Legacy entity card styles for backwards compatibility */
:deep(.insight-display .entity-card) {
  padding: 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
}

:deep(.insight-display .entity-header) {
  display: flex;
  align-items: center;
  gap: 11px;
}

:deep(.insight-display .entity-info) {
  flex: 1;
}

:deep(.insight-display .entity-card .entity-name) {
  font-size: 13px;
  font-weight: 600;
  color: #0A0A0A;
}

:deep(.insight-display .entity-card .entity-type) {
  font-size: 10px;
  font-family: var(--font-mono);
  color: #7C3AED;
  background: rgba(139, 92, 246, 0.1);
  padding: 2px 6px;
  display: inline-block;
  margin-top: 2px;
}

:deep(.insight-display .entity-card .entity-fact-count) {
  font-size: 10px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
  background: var(--color-gray, #F5F5F5);
  padding: 2px 6px;
}

:deep(.insight-display .entity-summary) {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 2px solid rgba(10,10,10,0.08);
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  line-height: 1.5;
}

/* Relation Item Styles */
:deep(.insight-display .relation-item) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
}

:deep(.insight-display .rel-source),
:deep(.insight-display .rel-target) {
  padding: 6px 6px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.12);
  font-size: 11px;
  font-weight: 500;
  color: rgba(10,10,10,0.7);
}

:deep(.insight-display .rel-arrow) {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

:deep(.insight-display .rel-line) {
  flex: 1;
  height: 1px;
  background: rgba(10,10,10,0.2);
}

:deep(.insight-display .rel-label) {
  padding: 2px 6px;
  background: rgba(139, 92, 246, 0.1);
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: #7C3AED;
  white-space: nowrap;
}

/* Sub-query Styles */
:deep(.insight-display .subquery-item) {
  display: flex;
  gap: 11px;
  padding: 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
}

:deep(.insight-display .subquery-number) {
  flex-shrink: 0;
  padding: 2px 6px;
  background: #7C3AED;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: #FAFAFA;
}

:deep(.insight-display .subquery-text) {
  font-size: 12px;
  color: rgba(10,10,10,0.7);
  line-height: 1.5;
}

/* Expand Button */
:deep(.insight-display .expand-btn),
:deep(.panorama-display .expand-btn),
:deep(.quick-search-display .expand-btn) {
  display: block;
  width: 100%;
  margin-top: 11px;
  padding: 6px 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.5);
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 3px;
}

:deep(.insight-display .expand-btn:hover),
:deep(.panorama-display .expand-btn:hover),
:deep(.quick-search-display .expand-btn:hover) {
  background: rgba(10,10,10,0.08);
  color: rgba(10,10,10,0.7);
  border-color: rgba(10,10,10,0.12);
}

/* Empty State */
:deep(.insight-display .empty-state),
:deep(.panorama-display .empty-state),
:deep(.quick-search-display .empty-state) {
  padding: 22px;
  text-align: center;
  font-size: 12px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
}

/* ========== Enhanced Panorama Display Styles ========== */
:deep(.panorama-display) {
  padding: 0;
}

:deep(.panorama-header) {
  padding: 11px 22px;
  background: rgba(255,107,26,0.1);
  border: 2px solid rgba(255,107,26,0.3);
  border-bottom: none;
}

:deep(.panorama-header .header-main) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

:deep(.panorama-header .header-title) {
  font-size: 14px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: #FF6B1A;
}

:deep(.panorama-header .header-stats) {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

:deep(.panorama-header .stat-item) {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

:deep(.panorama-header .stat-value) {
  font-family: var(--font-mono);
  font-weight: 700;
  color: #FF6B1A;
}

:deep(.panorama-header .stat-label) {
  color: rgba(255,107,26,0.6);
  font-size: 10px;
  font-family: var(--font-mono);
}

:deep(.panorama-header .stat-divider) {
  color: rgba(255,107,26,0.3);
  margin: 0 4px;
}

:deep(.panorama-header .stat-size) {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
}

:deep(.panorama-header .header-topic) {
  font-size: 13px;
  color: #FF6B1A;
  line-height: 1.5;
}

:deep(.panorama-tabs) {
  display: flex;
  gap: 2px;
  padding: 6px 11px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  border-top: none;
}

:deep(.panorama-tab) {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 11px;
  background: transparent;
  border: 2px solid transparent;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.5);
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.panorama-tab:hover) {
  background: rgba(10,10,10,0.08);
  color: rgba(10,10,10,0.7);
}

:deep(.panorama-tab.active) {
  background: #FAFAFA;
  color: #FF6B1A;
  border-color: rgba(255,107,26,0.3);
}


:deep(.panorama-content) {
  padding: 11px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  border-top: none;
}

:deep(.panorama-display .panel-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 11px;
  padding-bottom: 6px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

:deep(.panorama-display .panel-title) {
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

:deep(.panorama-display .panel-count) {
  font-size: 10px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
}

:deep(.panorama-display .facts-list) {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

:deep(.panorama-display .fact-item) {
  display: flex;
  gap: 11px;
  padding: 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
}

:deep(.panorama-display .fact-item.active) {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.08);
}

:deep(.panorama-display .fact-item.historical) {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.08);
}

:deep(.panorama-display .fact-number) {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10,10,10,0.12);
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: rgba(10,10,10,0.5);
}

:deep(.panorama-display .fact-item.active .fact-number) {
  background: rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.5);
}

:deep(.panorama-display .fact-item.historical .fact-number) {
  background: rgba(10,10,10,0.4);
  color: #FAFAFA;
}

:deep(.panorama-display .fact-content) {
  flex: 1;
  font-size: 12px;
  color: rgba(10,10,10,0.7);
  line-height: 1.6;
}

:deep(.panorama-display .fact-time) {
  display: block;
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  margin-bottom: 4px;
  font-family: var(--font-mono);
}

:deep(.panorama-display .fact-text) {
  display: block;
}

/* Entities Grid */
:deep(.panorama-display .entities-grid) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.panorama-display .entity-tag) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
}

:deep(.panorama-display .entity-name) {
  font-size: 12px;
  font-weight: 500;
  color: rgba(10,10,10,0.7);
}

:deep(.panorama-display .entity-type) {
  font-size: 10px;
  font-family: var(--font-mono);
  color: #FF6B1A;
  background: rgba(255,107,26,0.1);
  padding: 2px 6px;
}

/* ========== Enhanced Quick Search Display Styles ========== */
:deep(.quick-search-display) {
  padding: 0;
}

:deep(.quicksearch-header) {
  padding: 11px 22px;
  background: rgba(255,107,26,0.1);
  border: 2px solid rgba(255,107,26,0.3);
  border-bottom: none;
}

:deep(.quicksearch-header .header-main) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

:deep(.quicksearch-header .header-title) {
  font-size: 14px;
  font-family: var(--font-mono);
  font-weight: 700;
  color: #FF6B1A;
}

:deep(.quicksearch-header .header-stats) {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

:deep(.quicksearch-header .stat-item) {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

:deep(.quicksearch-header .stat-value) {
  font-family: var(--font-mono);
  font-weight: 700;
  color: #FF6B1A;
}

:deep(.quicksearch-header .stat-label) {
  color: rgba(255,107,26,0.6);
  font-size: 10px;
  font-family: var(--font-mono);
}

:deep(.quicksearch-header .stat-divider) {
  color: rgba(255,107,26,0.3);
  margin: 0 4px;
}

:deep(.quicksearch-header .stat-size) {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
}

:deep(.quicksearch-header .header-query) {
  font-size: 13px;
  color: #FF6B1A;
  line-height: 1.5;
}

:deep(.quicksearch-header .query-label) {
  font-weight: 600;
}

:deep(.quicksearch-tabs) {
  display: flex;
  gap: 2px;
  padding: 6px 11px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  border-top: none;
}

:deep(.quicksearch-tab) {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 11px;
  background: transparent;
  border: 2px solid transparent;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: rgba(10,10,10,0.5);
  cursor: pointer;
  transition: all 0.15s ease;
}

:deep(.quicksearch-tab:hover) {
  background: rgba(10,10,10,0.08);
  color: rgba(10,10,10,0.7);
}

:deep(.quicksearch-tab.active) {
  background: #FAFAFA;
  color: #FF6B1A;
  border-color: rgba(255,107,26,0.3);
}


:deep(.quicksearch-content) {
  padding: 11px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  border-top: none;
}

/* When there are no tabs, content connects directly to header */
:deep(.quicksearch-content.no-tabs) {
  border-top: none;
}

:deep(.quick-search-display .panel-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 11px;
  padding-bottom: 6px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

:deep(.quick-search-display .panel-title) {
  font-size: 12px;
  font-family: var(--font-mono);
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

:deep(.quick-search-display .panel-count) {
  font-size: 10px;
  font-family: var(--font-mono);
  color: rgba(10,10,10,0.4);
}

:deep(.quick-search-display .facts-list) {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

:deep(.quick-search-display .fact-item) {
  display: flex;
  gap: 11px;
  padding: 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
}

:deep(.quick-search-display .fact-item.active) {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.08);
}

:deep(.quick-search-display .fact-number) {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10,10,10,0.12);
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  color: rgba(10,10,10,0.5);
}

:deep(.quick-search-display .fact-item.active .fact-number) {
  background: rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.5);
}

:deep(.quick-search-display .fact-content) {
  flex: 1;
  font-size: 12px;
  color: rgba(10,10,10,0.7);
  line-height: 1.6;
}

/* Edges Panel */
:deep(.quick-search-display .edges-list) {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

:deep(.quick-search-display .edge-item) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
}

:deep(.quick-search-display .edge-source),
:deep(.quick-search-display .edge-target) {
  padding: 6px 6px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.12);
  font-size: 11px;
  font-weight: 500;
  color: rgba(10,10,10,0.7);
}

:deep(.quick-search-display .edge-arrow) {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

:deep(.quick-search-display .edge-line) {
  flex: 1;
  height: 1px;
  background: rgba(10,10,10,0.2);
}

:deep(.quick-search-display .edge-label) {
  padding: 2px 6px;
  background: rgba(255,107,26,0.1);
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 500;
  color: #FF6B1A;
  white-space: nowrap;
}

/* Nodes Grid */
:deep(.quick-search-display .nodes-grid) {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

:deep(.quick-search-display .node-tag) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 11px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
}

:deep(.quick-search-display .node-name) {
  font-size: 12px;
  font-weight: 500;
  color: rgba(10,10,10,0.7);
}

:deep(.quick-search-display .node-type) {
  font-size: 10px;
  font-family: var(--font-mono);
  color: #FF6B1A;
  background: rgba(255,107,26,0.1);
  padding: 2px 6px;
}

/* Console Logs - consistent with Step3Simulation.vue */
.console-logs {
  background: #0A0A0A;
  color: rgba(10,10,10,0.2);
  padding: 22px;
  font-family: var(--font-mono);
  border-top: 2px solid rgba(10,10,10,0.7);
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 2px solid rgba(255,255,255,0.1);
  padding-bottom: 6px;
  margin-bottom: 6px;
  font-size: 10px;
  color: rgba(255,255,255,0.3);
  cursor: pointer;
  user-select: none;
}

.console-logs.collapsed .log-header {
  border-bottom: none;
  padding-bottom: 0;
  margin-bottom: 0;
}

.log-toggle {
  font-size: 8px;
  opacity: 0.5;
  margin-left: 4px;
}

.log-title {
  text-transform: uppercase;
  letter-spacing: 3px;
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100px;
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar { width: 4px; }
.log-content::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); }

.log-line {
  font-size: 11px;
  line-height: 1.5;
}

.log-msg {
  color: rgba(255,255,255,0.6);
  word-break: break-all;
}

.log-msg.error { color: #FF4444; }
.log-msg.warning { color: #FFB347; }
.log-msg.success { color: #43C165; }
</style>
