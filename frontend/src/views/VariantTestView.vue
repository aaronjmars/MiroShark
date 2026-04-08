<template>
  <div class="variant-test-page">
    <header class="vt-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">PROSPECT-SIM</div>
      </div>
      <div class="header-center">
        <span class="page-tag">Email Variant Test</span>
      </div>
      <div class="header-right">
        <button v-if="results" class="download-btn" @click="downloadResults">
          ↓ Export JSON
        </button>
      </div>
    </header>

    <!-- Setup Form (shown before run) -->
    <div v-if="!results && !loading" class="setup-panel">
      <h2 class="setup-title">Test Cold Email Variants</h2>
      <p class="setup-desc">
        Run email copy variants against synthetic B2B decision-maker personas before touching real leads.
      </p>

      <!-- Project selector -->
      <div class="form-row">
        <label class="form-label">ICP Project (graph already built)</label>
        <select class="form-select" v-model="form.projectId">
          <option value="">Select project…</option>
          <option v-for="p in projects" :key="p.project_id" :value="p.project_id">
            {{ p.name }} — {{ p.status }}
          </option>
        </select>
      </div>

      <!-- Simulation requirement -->
      <div class="form-row">
        <label class="form-label">Simulation Goal (optional)</label>
        <textarea
          class="form-textarea"
          v-model="form.simulationRequirement"
          placeholder="Describe what you're testing. E.g.: Test timeline vs. problem hook for HR Directors at Spanish scale-ups with 15+ open roles."
          rows="3"
        />
      </div>

      <!-- Run mode -->
      <div class="form-row form-row-inline">
        <label class="form-label">Run Mode</label>
        <div class="toggle-group">
          <button
            class="toggle-btn"
            :class="{ active: !form.parallel }"
            @click="form.parallel = false"
          >Sequential</button>
          <button
            class="toggle-btn"
            :class="{ active: form.parallel }"
            @click="form.parallel = true"
          >Parallel</button>
        </div>
        <span class="mode-hint">
          {{ form.parallel ? 'All variants run at once — faster, more LLM calls' : 'One at a time — slower, cheaper' }}
        </span>
      </div>

      <!-- Variants -->
      <div class="variants-section">
        <div class="variants-header">
          <span class="variants-title">Email Variants</span>
          <button class="add-variant-btn" @click="addVariant" :disabled="form.variants.length >= 6">
            + Add Variant
          </button>
        </div>

        <div
          v-for="(variant, idx) in form.variants"
          :key="idx"
          class="variant-card"
        >
          <div class="variant-card-header">
            <span class="variant-label">Variant {{ String.fromCharCode(65 + idx) }}</span>
            <select class="hook-select" v-model="variant.hook_type">
              <option value="problem">Problem Hook</option>
              <option value="timeline">Timeline Hook</option>
              <option value="numbers">Numbers Hook</option>
              <option value="social_proof">Social Proof Hook</option>
              <option value="curiosity">Curiosity Hook</option>
            </select>
            <button
              v-if="form.variants.length > 2"
              class="remove-btn"
              @click="removeVariant(idx)"
            >✕</button>
          </div>
          <input
            class="subject-input"
            v-model="variant.subject_line"
            placeholder="Subject line (max 60 chars)"
            maxlength="80"
          />
          <textarea
            class="body-textarea"
            v-model="variant.body"
            placeholder="Email body (≤150 words recommended)"
            rows="5"
          />
          <div class="word-count" :class="{ warn: wordCount(variant.body) > 150 }">
            {{ wordCount(variant.body) }} words
          </div>
        </div>
      </div>

      <!-- Run button -->
      <button
        class="run-btn"
        :disabled="!canRun"
        @click="runVariantTest"
      >
        Run Variant Test
      </button>
      <div v-if="error" class="vt-error">{{ error }}</div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="vt-loading">
      <div class="loading-ring"></div>
      <div class="loading-text">Running variant test…</div>
      <div class="loading-sub">{{ loadingStatus }}</div>
    </div>

    <!-- Results -->
    <div v-if="results && !loading" class="results-panel">
      <!-- Summary header -->
      <div class="results-header">
        <h2 class="results-title">Variant Test Results</h2>
        <div class="results-meta">
          {{ results.total_variants }} variants · {{ results.run_mode }} · {{ results.num_rounds }} rounds
        </div>
      </div>

      <!-- Variant ranking table -->
      <div class="ranking-section">
        <h3 class="section-title">Variant Rankings</h3>
        <table class="ranking-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Variant</th>
              <th>Hook Type</th>
              <th>Sim ID</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(run, idx) in results.variant_run_ids"
              :key="run.variant_id"
              :class="{ 'row-winner': idx === 0 }"
            >
              <td class="rank-num">{{ idx + 1 }}</td>
              <td class="variant-name">
                <span v-if="idx === 0" class="winner-badge">★</span>
                {{ run.variant_label }}
              </td>
              <td>{{ getHookType(run.variant_id) }}</td>
              <td class="sim-id-cell">{{ shortId(run.simulation_id) }}</td>
              <td>
                <span class="status-badge" :class="run.status">{{ run.status }}</span>
              </td>
              <td>
                <button
                  class="view-btn"
                  @click="viewSimulation(run.simulation_id)"
                >View →</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Restart button -->
      <div class="results-actions">
        <button class="restart-btn" @click="resetForm">Run Another Test</button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getSimulationList } from '../api/simulation.js'

export default {
  name: 'VariantTestView',

  setup() {
    const router = useRouter()
    const projects = ref([])
    const loading = ref(false)
    const loadingStatus = ref('')
    const error = ref('')
    const results = ref(null)

    // Default form: 2 variants, problem vs timeline hook
    const form = ref({
      projectId: '',
      simulationRequirement: '',
      parallel: false,
      variants: [
        {
          id: 1,
          label: 'Variant A',
          hook_type: 'problem',
          subject_line: '',
          body: '',
        },
        {
          id: 2,
          label: 'Variant B',
          hook_type: 'timeline',
          subject_line: '',
          body: '',
        },
      ],
    })

    const canRun = computed(() => {
      if (!form.value.projectId) return false
      return form.value.variants.every(
        (v) => v.subject_line.trim() && v.body.trim()
      )
    })

    function wordCount(text) {
      return text.trim().split(/\s+/).filter(Boolean).length
    }

    function addVariant() {
      const next = form.value.variants.length + 1
      form.value.variants.push({
        id: next,
        label: `Variant ${String.fromCharCode(64 + next)}`,
        hook_type: 'curiosity',
        subject_line: '',
        body: '',
      })
    }

    function removeVariant(idx) {
      form.value.variants.splice(idx, 1)
      // Re-number ids and labels
      form.value.variants.forEach((v, i) => {
        v.id = i + 1
        v.label = `Variant ${String.fromCharCode(65 + i)}`
      })
    }

    function getHookType(variantId) {
      const v = form.value.variants.find((x) => x.id === variantId)
      return v ? v.hook_type : '—'
    }

    function shortId(id) {
      return id ? id.slice(-8) : '—'
    }

    async function loadProjects() {
      try {
        // Reuse simulation list endpoint to get projects with built graphs
        const resp = await fetch('/api/simulation/list')
        const data = await resp.json()
        if (data.success && data.simulations) {
          // Extract unique projects from simulations (fallback)
          const seen = new Set()
          projects.value = data.simulations
            .filter((s) => s.graph_id && !seen.has(s.project_id) && seen.add(s.project_id))
            .map((s) => ({
              project_id: s.project_id || s.simulation_id,
              name: s.name || s.simulation_id,
              status: s.status,
            }))
        }
      } catch (e) {
        // Non-fatal — user can still type project ID manually
        console.warn('Could not load projects:', e)
      }
    }

    async function runVariantTest() {
      if (!canRun.value) return

      loading.value = true
      error.value = ''
      results.value = null
      loadingStatus.value = 'Submitting variant test…'

      try {
        const payload = {
          project_id: form.value.projectId,
          variants: form.value.variants,
          simulation_requirement: form.value.simulationRequirement,
          parallel: form.value.parallel,
          num_rounds: 8,
        }

        const resp = await fetch('/api/simulation/run-variant-test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })

        const data = await resp.json()

        if (!data.success) {
          throw new Error(data.error || 'Variant test failed')
        }

        results.value = data
        loadingStatus.value = 'Done'
      } catch (e) {
        error.value = e.message || 'Unexpected error'
      } finally {
        loading.value = false
      }
    }

    function viewSimulation(simulationId) {
      router.push(`/simulation/${simulationId}`)
    }

    function downloadResults() {
      if (!results.value) return
      const blob = new Blob([JSON.stringify(results.value, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `variant-test-${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
    }

    function resetForm() {
      results.value = null
      error.value = ''
    }

    onMounted(() => {
      loadProjects()
    })

    return {
      router,
      projects,
      loading,
      loadingStatus,
      error,
      results,
      form,
      canRun,
      wordCount,
      addVariant,
      removeVariant,
      getHookType,
      shortId,
      runVariantTest,
      viewSimulation,
      downloadResults,
      resetForm,
    }
  },
}
</script>

<style scoped>
.variant-test-page {
  min-height: 100vh;
  background: #0a0a0f;
  color: #e4e4e9;
  font-family: 'Inter', 'SF Pro', system-ui, sans-serif;
}

.vt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  height: 56px;
  border-bottom: 1px solid #1e1e2e;
  background: #0d0d14;
}

.brand {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.12em;
  cursor: pointer;
  color: #a78bfa;
}

.page-tag {
  font-size: 11px;
  background: #1e1e2e;
  color: #a78bfa;
  padding: 3px 10px;
  border-radius: 4px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.download-btn {
  background: #1e1e2e;
  border: 1px solid #2e2e42;
  color: #a0a0b4;
  padding: 6px 14px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

/* Setup panel */
.setup-panel {
  max-width: 800px;
  margin: 40px auto;
  padding: 0 24px;
}

.setup-title {
  font-size: 22px;
  font-weight: 600;
  margin-bottom: 8px;
}

.setup-desc {
  color: #6b6b82;
  font-size: 14px;
  margin-bottom: 32px;
}

.form-row {
  margin-bottom: 20px;
}

.form-row-inline {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.form-label {
  display: block;
  font-size: 12px;
  color: #6b6b82;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}

.form-select,
.form-textarea {
  width: 100%;
  background: #111118;
  border: 1px solid #1e1e2e;
  color: #e4e4e9;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 14px;
  resize: vertical;
}

.toggle-group {
  display: flex;
  gap: 4px;
}

.toggle-btn {
  background: #111118;
  border: 1px solid #1e1e2e;
  color: #6b6b82;
  padding: 6px 14px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.toggle-btn.active {
  background: #1e1e36;
  border-color: #a78bfa;
  color: #a78bfa;
}

.mode-hint {
  font-size: 12px;
  color: #4b4b60;
}

/* Variants */
.variants-section {
  margin-bottom: 28px;
}

.variants-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.variants-title {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #8b8ba0;
}

.add-variant-btn {
  background: transparent;
  border: 1px dashed #2e2e42;
  color: #6b6b82;
  padding: 5px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.add-variant-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.variant-card {
  background: #0d0d14;
  border: 1px solid #1e1e2e;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.variant-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.variant-label {
  font-size: 13px;
  font-weight: 600;
  color: #a78bfa;
  min-width: 80px;
}

.hook-select {
  background: #111118;
  border: 1px solid #1e1e2e;
  color: #a0a0b4;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  flex: 1;
}

.remove-btn {
  background: transparent;
  border: none;
  color: #4b4b60;
  cursor: pointer;
  font-size: 14px;
  padding: 4px;
  margin-left: auto;
}

.subject-input {
  width: 100%;
  background: #111118;
  border: 1px solid #1e1e2e;
  color: #e4e4e9;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 14px;
  margin-bottom: 8px;
  box-sizing: border-box;
}

.body-textarea {
  width: 100%;
  background: #111118;
  border: 1px solid #1e1e2e;
  color: #e4e4e9;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
  box-sizing: border-box;
}

.word-count {
  font-size: 11px;
  color: #4b4b60;
  text-align: right;
  margin-top: 4px;
}

.word-count.warn {
  color: #f59e0b;
}

.run-btn {
  width: 100%;
  background: #a78bfa;
  color: #0a0a0f;
  border: none;
  padding: 14px;
  border-radius: 6px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: 0.04em;
}

.run-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.vt-error {
  margin-top: 12px;
  color: #f87171;
  font-size: 13px;
  padding: 10px;
  background: #1a0a0a;
  border-radius: 4px;
}

/* Loading */
.vt-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  gap: 16px;
}

.loading-ring {
  width: 40px;
  height: 40px;
  border: 3px solid #1e1e2e;
  border-top-color: #a78bfa;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.loading-text {
  font-size: 16px;
  color: #a0a0b4;
}

.loading-sub {
  font-size: 13px;
  color: #4b4b60;
}

/* Results */
.results-panel {
  max-width: 900px;
  margin: 40px auto;
  padding: 0 24px;
}

.results-header {
  margin-bottom: 32px;
}

.results-title {
  font-size: 22px;
  font-weight: 600;
}

.results-meta {
  font-size: 13px;
  color: #6b6b82;
  margin-top: 4px;
}

.ranking-section {
  background: #0d0d14;
  border: 1px solid #1e1e2e;
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 24px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6b6b82;
  margin-bottom: 16px;
}

.ranking-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.ranking-table th {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid #1e1e2e;
  color: #6b6b82;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.ranking-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #111118;
}

.row-winner td {
  background: #0f0f1a;
}

.rank-num {
  color: #4b4b60;
  width: 32px;
}

.winner-badge {
  color: #f59e0b;
  margin-right: 6px;
}

.variant-name {
  font-weight: 500;
}

.sim-id-cell {
  font-family: monospace;
  color: #6b6b82;
  font-size: 12px;
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  background: #1e1e2e;
  color: #6b6b82;
}

.status-badge.created { color: #a78bfa; background: #1a1a2e; }
.status-badge.running { color: #34d399; background: #0a1a12; }
.status-badge.completed { color: #34d399; background: #0a1a12; }
.status-badge.failed { color: #f87171; background: #1a0a0a; }

.view-btn {
  background: transparent;
  border: 1px solid #1e1e2e;
  color: #a78bfa;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.results-actions {
  display: flex;
  justify-content: flex-end;
}

.restart-btn {
  background: #111118;
  border: 1px solid #1e1e2e;
  color: #a0a0b4;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
</style>
