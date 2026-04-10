<template>
  <div class="home-container">
    <!-- Top Navigation Bar -->
    <nav class="navbar">
      <div class="nav-brand">MIROSHARK</div>
      <div class="nav-links">
        <button class="variant-test-btn" @click="router.push('/variant-test')" title="B2B Email Copy Testing">
          ✉ Variant Test
        </button>
        <a href="https://github.com/aaronjmars/MiroShark" target="_blank" class="github-link">
          GitHub <span class="arrow">↗</span>
        </a>
        <button class="settings-btn" @click="settingsOpen = true" title="Settings">
          ⚙
        </button>
      </div>
    </nav>

    <SettingsPanel :open="settingsOpen" @close="settingsOpen = false" />

    <div class="main-content">
      <!-- Upper Section: Hero Area -->
      <section class="hero-section">
        <div class="tag-row">
          <span class="orange-tag">A Concise & Universal Swarm Intelligence Engine</span>
        </div>

        <h1 class="main-title">
          <span class="gradient-text">Simulate the Future Instantly</span>
        </h1>

        <div class="hero-desc">
          <p>
            Upload any document. <span class="highlight-bold">MiroShark</span> extracts the key players, generates <span class="highlight-orange">hundreds of AI agents</span> with unique personas, and simulates how they'd react on Twitter, Reddit, and Polymarket. Watch opinions form, arguments spread, and markets move.
          </p>
          <p class="slogan-text">
            Don't predict the future. Simulate it<span class="blinking-cursor">_</span>
          </p>
        </div>

        <div class="decoration-square"></div>

        <button class="scroll-down-btn" @click="scrollToBottom">
          ↓
        </button>
      </section>

      <!-- Lower Section: Two-Column Layout -->
      <section class="dashboard-section">
        <!-- Left Column: Status & Steps -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> System Status
          </div>
          
          <h2 class="section-title">Ready</h2>
          <p class="section-desc">
            Prediction engine on standby. Upload documents to initialize the simulation sequence.
          </p>
          

          <!-- Simulation Steps Overview (New Section) -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon">◇</span> Workflow Sequence
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">Graph Construction</div>
                  <div class="step-desc">Reality seed extraction & Individual/group memory injection & GraphRAG construction</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">Agent Setup</div>
                  <div class="step-desc">Entity-relation extraction & Persona generation & Environment config Agent injects simulation parameters</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">Start Simulation</div>
                  <div class="step-desc">Dual-platform parallel simulation & Automatic prediction requirement parsing & Dynamic temporal memory updates</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">Report Generation</div>
                  <div class="step-desc">ReportAgent has a rich toolset for in-depth interaction with the post-simulation environment</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">Deep Interaction</div>
                  <div class="step-desc">Chat with any agent in the simulated world & Converse with the ReportAgent</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Column: Interactive Console -->
        <div class="right-panel">
          <div class="console-box">
            <!-- Upload Area -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">01 / Reality Seeds</span>
                <span class="console-meta">Supported formats: PDF, MD, TXT</span>
              </div>
              
              <div 
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />
                
                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">Drop Files to Upload</div>
                  <div class="upload-hint">or click to browse the file system</div>
                </div>
                
                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- URL Input Section -->
            <div class="console-section url-section">
              <div class="console-header">
                <span class="console-label">01b / URL Import</span>
                <span class="console-meta">Paste article or report URL</span>
              </div>
              <div class="url-input-row">
                <input
                  v-model="urlInput"
                  class="url-input"
                  type="url"
                  placeholder="https://example.com/article"
                  :disabled="loading || urlFetching"
                  @keydown.enter.prevent="fetchUrlDoc"
                />
                <button
                  class="url-fetch-btn"
                  @click="fetchUrlDoc"
                  :disabled="!urlInput.trim() || loading || urlFetching"
                >
                  <span v-if="urlFetching">...</span>
                  <span v-else>Fetch →</span>
                </button>
              </div>
              <div v-if="urlError" class="url-error">{{ urlError }}</div>
              <div v-if="urlDocs.length > 0" class="url-doc-list">
                <div v-for="(doc, index) in urlDocs" :key="index" class="url-doc-item">
                  <span class="url-doc-icon">◈</span>
                  <div class="url-doc-info">
                    <div class="url-doc-title">{{ doc.title }}</div>
                    <div class="url-doc-meta">{{ doc.char_count.toLocaleString() }} chars · {{ doc.url }}</div>
                  </div>
                  <button @click.stop="removeUrlDoc(index)" class="remove-btn">×</button>
                </div>
              </div>
            </div>

            <!-- Divider -->
            <div class="console-divider">
              <span>Input Parameters</span>
            </div>

            <!-- Input Area -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 02 / Simulation Prompt</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  placeholder="// Enter your simulation or prediction requirements in natural language (e.g., If a university announces the revocation of a disciplinary action against a student, what public opinion trends will emerge?)"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">Engine: MiroShark-V1.0</div>
              </div>
            </div>

            <!-- Start Button -->
            <div class="console-section btn-section">
              <button 
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">Launch Simulation</span>
                <span v-else>Initializing...</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Quick Start Templates -->
      <TemplateGallery />

      <!-- History Project Database -->
      <HistoryDatabase />

    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import TemplateGallery from '../components/TemplateGallery.vue'
import SettingsPanel from '../components/SettingsPanel.vue'
import { fetchUrl } from '../api/graph'

const settingsOpen = ref(false)

const router = useRouter()

// Form data
const formData = ref({
  simulationRequirement: ''
})

// File list
const files = ref([])

// URL import state
const urlInput = ref('')
const urlDocs = ref([])   // [{title, url, text, char_count}]
const urlFetching = ref(false)
const urlError = ref('')

// State
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// File input ref
const fileInput = ref(null)

// Computed: whether the form can be submitted
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' &&
    (files.value.length > 0 || urlDocs.value.length > 0)
})

// Trigger file selection
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// Handle file selection
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// Handle drag-related events
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// Add files
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

// Remove file
const removeFile = (index) => {
  files.value.splice(index, 1)
}

// Scroll to bottom
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// Fetch a URL and add it to urlDocs
const fetchUrlDoc = async () => {
  const url = urlInput.value.trim()
  if (!url || urlFetching.value) return

  // Prevent duplicate URLs
  if (urlDocs.value.some(d => d.url === url)) {
    urlError.value = 'This URL has already been added.'
    return
  }

  urlFetching.value = true
  urlError.value = ''
  try {
    const res = await fetchUrl(url)
    if (res.success) {
      urlDocs.value.push(res.data)
      urlInput.value = ''
    } else {
      urlError.value = res.error || 'Failed to fetch URL.'
    }
  } catch (err) {
    urlError.value = err.message || 'Failed to fetch URL.'
  } finally {
    urlFetching.value = false
  }
}

// Remove a URL document from the list
const removeUrlDoc = (index) => {
  urlDocs.value.splice(index, 1)
}

// Start simulation - navigate immediately, API calls happen on the Process page
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return

  // Store data pending upload
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement, urlDocs.value)

    // Navigate immediately to Process page (using special identifier for new project)
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════
   HOME — Hyperstitions Design System applied
   ═══════════════════════════════════════════════════════════ */

.home-container {
  min-height: 100vh;
  background: var(--background);
  font-family: var(--font-display);
  color: var(--foreground);
}

/* ── Top Navigation ── */
.navbar {
  height: var(--space-xl);
  background: var(--color-black);
  color: var(--color-white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-lg);
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 3px;
  font-size: 14px;
  text-transform: uppercase;
}

.nav-links {
  display: flex;
  align-items: center;
}

/* ── Variant Test nav button ── */
.variant-test-btn {
  background: none;
  border: 1px solid rgba(167, 139, 250, 0.4);
  color: rgba(167, 139, 250, 0.8);
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 1px;
  cursor: pointer;
  padding: 4px 10px;
  margin-right: var(--space-md);
  transition: var(--transition-fast);
}

.variant-test-btn:hover {
  border-color: rgba(167, 139, 250, 0.9);
  color: #a78bfa;
}

.github-link {
  color: var(--color-white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  transition: var(--transition-fast);
  opacity: 0.6;
}

.github-link:hover { opacity: 1; }

.arrow { font-family: sans-serif; }

.settings-btn {
  background: none;
  border: none;
  color: rgba(250,250,250,0.5);
  font-size: 18px;
  cursor: pointer;
  padding: 0 0 0 var(--space-md);
  line-height: 1;
  transition: var(--transition-fast);
}

.settings-btn:hover { color: var(--color-orange); }

/* ── Main Content ── */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--space-2xl) var(--space-lg);
}

/* ── Hero Section ── */
.hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-bottom: var(--space-2xl);
  position: relative;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-md);
  font-family: var(--font-mono);
  font-size: 13px;
}

.orange-tag {
  background: var(--color-orange);
  color: var(--color-white);
  padding: 4px var(--space-sm);
  font-weight: 700;
  letter-spacing: 3px;
  font-size: 11px;
  text-transform: uppercase;
  font-family: var(--font-mono);
}

.main-title {
  font-family: var(--font-display);
  font-size: 50px;
  line-height: 1.25;
  font-weight: 400;
  margin: 0 0 var(--space-lg) 0;
  letter-spacing: -1px;
  color: var(--foreground);
}

.gradient-text {
  color: var(--color-orange);
  -webkit-text-fill-color: var(--color-orange);
  display: inline;
}

.hero-desc {
  font-family: var(--font-display);
  font-size: 22px;
  line-height: 1.5;
  color: rgba(10,10,10,0.7);
  max-width: 640px;
  margin-bottom: var(--space-xl);
}

.hero-desc p { margin-bottom: var(--space-md); }

.highlight-bold {
  color: var(--foreground);
  font-weight: 400;
}

.highlight-orange {
  color: var(--color-orange);
  font-family: var(--font-mono);
  font-size: 0.85em;
}

.highlight-code {
  background: rgba(10,10,10,0.05);
  padding: 2px var(--space-xs);
  font-family: var(--font-mono);
  font-size: 0.85em;
  color: var(--foreground);
}

.slogan-text {
  font-family: var(--font-display);
  font-size: 25px;
  line-height: 1.5;
  color: var(--foreground);
  border-left: var(--border-orange);
  padding-left: var(--space-md);
  margin-top: var(--space-md);
}

.blinking-cursor {
  color: var(--color-green);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.decoration-square {
  width: var(--space-sm);
  height: var(--space-sm);
  background: var(--color-green);
  margin-top: var(--space-md);
}

.scroll-down-btn {
  margin-top: var(--space-md);
  width: var(--space-lg);
  height: var(--space-lg);
  border: var(--border-medium);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--color-orange);
  font-size: 1.2rem;
  transition: var(--transition-fast);
}

.scroll-down-btn:hover {
  border-color: var(--color-orange);
}

/* ── Warning Stripe Divider ── */
.dashboard-section::before {
  content: '';
  display: block;
  height: 7px;
  background: repeating-linear-gradient(
    -45deg,
    var(--color-orange),
    var(--color-orange) 11px,
    var(--background) 11px,
    var(--background) 22px
  );
  margin-bottom: var(--space-xl);
}

/* ── Dashboard Section ── */
.dashboard-section {
  display: flex;
  gap: var(--space-xl);
  padding-top: 0;
  align-items: flex-start;
}

.dashboard-section .left-panel,
.dashboard-section .right-panel {
  display: flex;
  flex-direction: column;
}

/* ── Left Panel ── */
.left-panel { flex: 0.8; }

.panel-header {
  font-family: var(--font-mono);
  font-size: 14px;
  color: rgba(10,10,10,0.4);
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  margin-bottom: var(--space-md);
  letter-spacing: 3px;
  text-transform: uppercase;
}

.status-dot {
  color: var(--color-green);
  font-size: 0.8rem;
}

.section-title {
  font-family: var(--font-display);
  font-size: 34px;
  font-weight: 400;
  margin: 0 0 var(--space-sm) 0;
}

.section-desc {
  color: rgba(10,10,10,0.5);
  font-family: var(--font-display);
  font-size: 22px;
  margin-bottom: var(--space-md);
  line-height: 1.5;
}

/* ── Metric Cards ── */
.metrics-row {
  display: flex;
  gap: var(--space-md);
  margin-bottom: var(--space-md);
}

.metric-card {
  border: var(--border-light);
  padding: var(--space-md) var(--space-lg);
  min-width: 150px;
  transition: var(--transition-fast);
}

.metric-card:hover { border-color: var(--color-orange); }

.metric-value {
  font-family: var(--font-display);
  font-size: 31px;
  margin-bottom: var(--space-xs);
}

.metric-label {
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.4);
  letter-spacing: 1px;
}

/* ── Workflow Steps ── */
.steps-container {
  border: var(--border-light);
  padding: var(--space-lg);
  position: relative;
}

/* Corner markers */
.steps-container::before,
.steps-container::after {
  content: '';
  position: absolute;
  width: 20px;
  height: 20px;
  pointer-events: none;
}
.steps-container::before {
  top: 12px; left: 12px;
  border-top: 3px solid var(--color-orange);
  border-left: 3px solid var(--color-orange);
}
.steps-container::after {
  bottom: 12px; right: 12px;
  border-bottom: 3px solid var(--color-green);
  border-right: 3px solid var(--color-green);
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 14px;
  color: rgba(10,10,10,0.4);
  margin-bottom: var(--space-md);
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  letter-spacing: 3px;
  text-transform: uppercase;
}

.diamond-icon {
  color: var(--color-orange);
  font-size: 1.2rem;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 15px;
  color: var(--color-orange);
  opacity: 0.5;
}

.step-info { flex: 1; }

.step-title {
  font-family: var(--font-display);
  font-size: 22px;
  margin-bottom: 4px;
}

.step-desc {
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.4);
  line-height: 1.6;
}

/* ── Right Console ── */
.right-panel { flex: 1.2; }

.console-box {
  border: var(--border-medium);
  padding: var(--space-xs);
  position: relative;
}

/* Console corner markers */
.console-box::before,
.console-box::after {
  content: '';
  position: absolute;
  width: 20px;
  height: 20px;
  pointer-events: none;
}
.console-box::before {
  top: -2px; right: -2px;
  border-top: 3px solid var(--color-orange);
  border-right: 3px solid var(--color-orange);
}
.console-box::after {
  bottom: -2px; left: -2px;
  border-bottom: 3px solid var(--color-green);
  border-left: 3px solid var(--color-green);
}

.console-section { padding: var(--space-md); }
.console-section.btn-section { padding-top: 0; }

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--space-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.4);
  letter-spacing: 1px;
}

.console-label { text-transform: uppercase; }
.console-meta { font-size: 11px; }

/* ── Upload Zone ── */
.upload-zone {
  border: 2px dashed rgba(10,10,10,0.12);
  height: 200px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: var(--transition-medium);
  background: var(--color-gray);
}

.upload-zone.has-files { align-items: flex-start; }

.upload-zone:hover {
  border-color: var(--color-orange);
  background: var(--background);
}

.upload-zone.drag-over {
  border-color: var(--color-green);
  background: rgba(67,193,101,0.05);
}

.upload-placeholder { text-align: center; }

.upload-icon {
  width: var(--space-lg);
  height: var(--space-lg);
  border: var(--border-medium);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--space-sm);
  color: var(--color-orange);
  font-size: 1.2rem;
}

.upload-title {
  font-family: var(--font-display);
  font-size: 18px;
  margin-bottom: var(--space-xs);
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.35);
}

/* ── File List ── */
.file-list {
  width: 100%;
  padding: var(--space-sm);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--background);
  padding: var(--space-xs) var(--space-sm);
  border: var(--border-light);
  font-family: var(--font-mono);
  font-size: 14px;
}

.file-name { flex: 1; margin: 0 var(--space-sm); }

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: rgba(10,10,10,0.35);
  transition: var(--transition-fast);
}

.remove-btn:hover { color: var(--color-red); }

/* ── Console Divider ── */
.console-divider {
  display: flex;
  align-items: center;
  margin: var(--space-sm) 0;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(10,10,10,0.08);
}

.console-divider span {
  padding: 0 var(--space-sm);
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.25);
  letter-spacing: 3px;
  text-transform: uppercase;
}

/* ── Text Input ── */
.input-wrapper {
  position: relative;
  border: var(--border-light);
  background: var(--color-gray);
  transition: var(--transition-fast);
}

.input-wrapper:focus-within {
  border-color: var(--color-orange);
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: var(--space-md);
  font-family: var(--font-mono);
  font-size: 15px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 150px;
  color: var(--foreground);
}

.code-input::placeholder {
  color: rgba(10,10,10,0.35);
}

.model-badge {
  position: absolute;
  bottom: var(--space-xs);
  right: var(--space-sm);
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.25);
  letter-spacing: 1px;
}

/* ── Launch Button ── */
.start-engine-btn {
  width: 100%;
  background: var(--color-black);
  color: var(--color-white);
  border: 2px solid var(--color-black);
  padding: 20px var(--space-lg);
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.15s ease;
  letter-spacing: 3px;
  text-transform: uppercase;
  position: relative;
  overflow: hidden;
}

.start-engine-btn:not(:disabled) {
  animation: btn-pulse 2s ease-in-out infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--color-orange);
  border-color: var(--color-orange);
}

.start-engine-btn:active:not(:disabled) {
  opacity: 0.9;
}

.start-engine-btn:disabled {
  background: var(--color-gray);
  color: rgba(10,10,10,0.35);
  cursor: not-allowed;
  border-color: rgba(10,10,10,0.08);
}

@keyframes btn-pulse {
  0%, 100% { border-color: var(--color-black); }
  50% { border-color: var(--color-orange); }
}

/* ── URL Import Section ── */
.url-section {
  padding-top: 0;
}

.url-input-row {
  display: flex;
  gap: var(--space-xs);
}

.url-input {
  flex: 1;
  border: var(--border-light);
  background: var(--color-gray);
  padding: var(--space-xs) var(--space-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--foreground);
  outline: none;
  transition: var(--transition-fast);
  min-width: 0;
}

.url-input:focus {
  border-color: var(--color-orange);
  background: var(--background);
}

.url-input::placeholder {
  color: rgba(10,10,10,0.3);
}

.url-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.url-fetch-btn {
  background: var(--color-black);
  color: var(--color-white);
  border: 2px solid var(--color-black);
  padding: var(--space-xs) var(--space-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1px;
  cursor: pointer;
  transition: var(--transition-fast);
  white-space: nowrap;
}

.url-fetch-btn:hover:not(:disabled) {
  background: var(--color-orange);
  border-color: var(--color-orange);
}

.url-fetch-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.url-error {
  margin-top: var(--space-xs);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-red);
}

.url-doc-list {
  margin-top: var(--space-xs);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.url-doc-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-xs);
  background: var(--background);
  padding: var(--space-xs) var(--space-sm);
  border: var(--border-light);
  border-left: 3px solid var(--color-green);
}

.url-doc-icon {
  color: var(--color-green);
  font-size: 14px;
  margin-top: 1px;
  flex-shrink: 0;
}

.url-doc-info {
  flex: 1;
  min-width: 0;
}

.url-doc-title {
  font-family: var(--font-display);
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.url-doc-meta {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.35);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── Footer ── */
.attribution-footer {
  text-align: center;
  padding: var(--space-lg) 0;
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.25);
  letter-spacing: 1px;
}

.attribution-footer a {
  color: rgba(10,10,10,0.4);
  text-decoration: none;
}

.attribution-footer a:hover {
  color: var(--color-orange);
}

/* ── Responsive ── */
@media (max-width: 1024px) {
  .dashboard-section { flex-direction: column; }
  .main-title { font-size: 34px; }
}
</style>
