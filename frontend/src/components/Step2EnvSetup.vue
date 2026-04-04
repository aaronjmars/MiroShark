<template>
  <div class="env-setup-panel">
    <div class="scroll-container">
      <!-- Step 01: Simulation Instance -->
      <div class="step-card" :class="{ 'active': phase === 0, 'completed': phase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">Simulation Instance Initialization</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 0" class="badge success">Completed</span>
            <span v-else class="badge processing">Initializing</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/simulation/create</p>
          <p class="description">
            Create a new simulation instance and fetch simulation world parameter templates
          </p>

          <div v-if="simulationId" class="info-card">
            <div class="info-row" @click="copyValue(projectData?.project_id)">
              <span class="info-label">Project ID</span>
              <span class="info-value mono copyable">{{ projectData?.project_id }}</span>
            </div>
            <div class="info-row" @click="copyValue(projectData?.graph_id)">
              <span class="info-label">Graph ID</span>
              <span class="info-value mono copyable">{{ projectData?.graph_id }}</span>
            </div>
            <div class="info-row" @click="copyValue(simulationId)">
              <span class="info-label">Simulation ID</span>
              <span class="info-value mono copyable">{{ simulationId }}</span>
            </div>
            <div class="info-row" @click="copyValue(taskId)">
              <span class="info-label">Task ID</span>
              <span class="info-value mono copyable">{{ taskId || 'Async task completed' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 02: Generate Agent Profiles -->
      <div class="step-card" :class="{ 'active': phase === 1, 'completed': phase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">Generate Agent Profiles</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 1" class="badge success">Completed</span>
            <span v-else-if="phase === 1" class="badge processing">{{ prepareProgress }}%</span>
            <span v-else class="badge pending">Waiting</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            Combines context to automatically invoke tools, organize entities and relationships from the knowledge graph, initialize simulated individuals, and assign them unique behaviors and memories based on reality seeds
          </p>

          <!-- Profiles Stats -->
          <div v-if="profiles.length > 0" class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ profiles.length }}</span>
              <span class="stat-label">Current Agents</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ expectedTotal || '-' }}</span>
              <span class="stat-label">Expected Total Agents</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ totalTopicsCount }}</span>
              <span class="stat-label">Reality Seed Related Topics</span>
            </div>
          </div>

          <!-- Profiles List Preview -->
          <div v-if="profiles.length > 0" class="profiles-preview">
            <div class="preview-header">
              <span class="preview-title">Generated Agent Profiles</span>
            </div>
            <div class="profiles-list">
              <div 
                v-for="(profile, idx) in profiles" 
                :key="idx" 
                class="profile-card"
                @click="selectProfile(profile)"
              >
                <div class="profile-header">
                  <span class="profile-realname">{{ profile.username || 'Unknown' }}</span>
                  <span class="profile-username">@{{ profile.name || `agent_${idx}` }}</span>
                </div>
                <div class="profile-meta">
                  <span class="profile-profession">{{ profile.profession || 'Unknown Profession' }}</span>
                </div>
                <p class="profile-bio">{{ profile.bio || 'No bio available' }}</p>
                <div v-if="profile.interested_topics?.length" class="profile-topics">
                  <span 
                    v-for="topic in profile.interested_topics.slice(0, 3)" 
                    :key="topic" 
                    class="topic-tag"
                  >{{ topic }}</span>
                  <span v-if="profile.interested_topics.length > 3" class="topic-more">
                    +{{ profile.interested_topics.length - 3 }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 03: Generate Simulation Config -->
      <div class="step-card" :class="{ 'active': phase === 2, 'completed': phase > 2, 'error': configError }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">Generate Simulation Config</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 2" class="badge success">Completed</span>
            <span v-else-if="configError" class="badge error">Failed</span>
            <span v-else-if="phase === 2" class="badge processing">Generating</span>
            <span v-else class="badge pending">Waiting</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            LLM intelligently configures world time flow, recommendation algorithms, each individual's active time periods, posting frequency, event triggers, and other parameters based on simulation requirements and reality seeds
          </p>

          <!-- Config Error Panel -->
          <div v-if="configError" class="config-error-panel">
            <div class="config-error-title">Config Generation Failed</div>
            <div class="config-error-msg">{{ configError }}</div>
            <div class="config-error-hint">
              Common causes: OpenRouter API key invalid or quota exceeded, model name not found, network timeout.
              Check your <code>.env</code> values for <code>OPENROUTER_API_KEY</code> and <code>OPENROUTER_MODEL</code>.
            </div>
            <button
              class="retry-config-btn"
              :disabled="isConfigRetrying"
              @click="handleConfigRetry"
            >
              <span v-if="isConfigRetrying" class="loading-spinner-small"></span>
              {{ isConfigRetrying ? 'Retrying...' : 'Retry Config Generation' }}
            </button>
          </div>

          <!-- Config Preview -->
          <div v-if="simulationConfig" class="config-detail-panel">
            <!-- Time Configuration -->
            <div class="config-block">
              <div class="config-grid">
                <div class="config-item">
                  <span class="config-item-label">Simulation Duration</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.total_simulation_hours || '-' }} hours</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">Duration Per Round</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.minutes_per_round || '-' }} min</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">Total Rounds</span>
                  <span class="config-item-value">{{ Math.floor((simulationConfig.time_config?.total_simulation_hours * 60 / simulationConfig.time_config?.minutes_per_round)) || '-' }} rounds</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">Active Per Hour</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.agents_per_hour_min }}-{{ simulationConfig.time_config?.agents_per_hour_max }}</span>
                </div>
              </div>
              <div class="time-periods">
                <div class="period-item">
                  <span class="period-label">Peak Hours</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.peak_hours?.join(':00, ') }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.peak_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">Working Hours</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.work_hours?.[0] }}:00-{{ simulationConfig.time_config?.work_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.work_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">Morning Hours</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.morning_hours?.[0] }}:00-{{ simulationConfig.time_config?.morning_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.morning_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">Off-Peak Hours</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.off_peak_hours?.[0] }}:00-{{ simulationConfig.time_config?.off_peak_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.off_peak_activity_multiplier }}</span>
                </div>
              </div>
            </div>

            <!-- Agent Configuration -->
            <div class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">Agent Configuration</span>
                <span class="config-block-badge">{{ simulationConfig.agent_configs?.length || 0 }}</span>
              </div>
              <div class="agents-cards">
                <div 
                  v-for="agent in simulationConfig.agent_configs" 
                  :key="agent.agent_id" 
                  class="agent-card"
                >
                  <!-- Card Header -->
                  <div class="agent-card-header">
                    <div class="agent-identity">
                      <span class="agent-id">Agent {{ agent.agent_id }}</span>
                      <span class="agent-name">{{ agent.entity_name }}</span>
                    </div>
                    <div class="agent-tags">
                      <span class="agent-type">{{ agent.entity_type }}</span>
                      <span class="agent-stance" :class="'stance-' + agent.stance">{{ agent.stance }}</span>
                    </div>
                  </div>
                  
                  <!-- Profile Info (from generated profiles) -->
                  <div v-if="getAgentProfile(agent.agent_id)" class="agent-profile-info">
                    <span class="profile-profession-tag">{{ getAgentProfile(agent.agent_id).profession || 'Unknown' }}</span>
                    <span v-if="getAgentProfile(agent.agent_id).country" class="profile-country-tag">{{ getAgentProfile(agent.agent_id).country }}</span>
                    <span v-if="getAgentProfile(agent.agent_id).mbti" class="profile-mbti-tag">{{ getAgentProfile(agent.agent_id).mbti }}</span>
                    <p class="profile-bio-snippet">{{ (getAgentProfile(agent.agent_id).bio || '').slice(0, 120) }}{{ (getAgentProfile(agent.agent_id).bio || '').length > 120 ? '...' : '' }}</p>
                  </div>

                  <!-- Active Timeline -->
                  <div class="agent-timeline">
                    <span class="timeline-label">Active Hours</span>
                    <div class="mini-timeline">
                      <div 
                        v-for="hour in 24" 
                        :key="hour - 1" 
                        class="timeline-hour"
                        :class="{ 'active': agent.active_hours?.includes(hour - 1) }"
                        :title="`${hour - 1}:00`"
                      ></div>
                    </div>
                    <div class="timeline-marks">
                      <span>0</span>
                      <span>6</span>
                      <span>12</span>
                      <span>18</span>
                      <span>24</span>
                    </div>
                  </div>

                  <!-- Behavioral Parameters -->
                  <div class="agent-params">
                    <div class="param-group">
                      <div class="param-item">
                        <span class="param-label">Posts/hr</span>
                        <span class="param-value">{{ agent.posts_per_hour }}</span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">Comments/hr</span>
                        <span class="param-value">{{ agent.comments_per_hour }}</span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">Response Delay</span>
                        <span class="param-value">{{ agent.response_delay_min }}-{{ agent.response_delay_max }}min</span>
                      </div>
                    </div>
                    <div class="param-group">
                      <div class="param-item">
                        <span class="param-label">Activity Level</span>
                        <span class="param-value with-bar">
                          <span class="mini-bar" :style="{ width: (agent.activity_level * 100) + '%' }"></span>
                          {{ (agent.activity_level * 100).toFixed(0) }}%
                        </span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">Sentiment Tendency</span>
                        <span class="param-value" :class="agent.sentiment_bias > 0 ? 'positive' : agent.sentiment_bias < 0 ? 'negative' : 'neutral'">
                          {{ agent.sentiment_bias > 0 ? '+' : '' }}{{ agent.sentiment_bias?.toFixed(1) }}
                        </span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">Influence</span>
                        <span class="param-value highlight">{{ agent.influence_weight?.toFixed(1) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Platform Configuration -->
            <div class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">Recommendation Algorithm Configuration</span>
              </div>
              <div class="platforms-grid">
                <div v-if="simulationConfig.twitter_config" class="platform-card">
                  <div class="platform-card-header">
                    <span class="platform-name">X (Twitter)</span>
                  </div>
                  <div class="platform-params">
                    <div class="param-row">
                      <span class="param-label">Timeliness Weight</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.recency_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Popularity Weight</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.popularity_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Relevance Weight</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.relevance_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Viral Threshold</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.viral_threshold }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Echo Chamber Intensity</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.echo_chamber_strength }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="simulationConfig.reddit_config" class="platform-card">
                  <div class="platform-card-header">
                    <span class="platform-name">Reddit</span>
                  </div>
                  <div class="platform-params">
                    <div class="param-row">
                      <span class="param-label">Timeliness Weight</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.recency_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Popularity Weight</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.popularity_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Relevance Weight</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.relevance_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Viral Threshold</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.viral_threshold }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Echo Chamber Intensity</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.echo_chamber_strength }}</span>
                    </div>
                  </div>
                </div>
                <div class="platform-card">
                  <div class="platform-card-header">
                    <span class="platform-name">Polymarket</span>
                  </div>
                  <div class="platform-params">
                    <div class="param-row">
                      <span class="param-label">Market Maker</span>
                      <span class="param-value">Constant-Product AMM</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Initial Liquidity</span>
                      <span class="param-value">$100 per outcome</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Trading Actions</span>
                      <span class="param-value">Buy/Sell YES & NO shares</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">Market-Media Bridge</span>
                      <span class="param-value">Enabled (prices feed social media)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- LLM Configuration Reasoning -->
            <div v-if="simulationConfig.generation_reasoning" class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">LLM Configuration Reasoning</span>
              </div>
              <div class="reasoning-content">
                <div 
                  v-for="(reason, idx) in simulationConfig.generation_reasoning.split('|').slice(0, 2)" 
                  :key="idx" 
                  class="reasoning-item"
                >
                  <p class="reasoning-text">{{ reason.trim() }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 04: Initial Activation Orchestration -->
      <div class="step-card" :class="{ 'active': phase === 3, 'completed': phase > 3 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">04</span>
            <span class="step-title">Initial Activation Orchestration</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 3" class="badge success">Completed</span>
            <span v-else-if="phase === 3" class="badge processing">Orchestrating</span>
            <span v-else class="badge pending">Waiting</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            Based on narrative direction, automatically generate initial activation events and hot topics to guide the initial state of the simulation world
          </p>

          <div v-if="simulationConfig?.event_config" class="orchestration-content">
            <!-- Narrative Direction -->
            <div class="narrative-box">
              <span class="box-label narrative-label">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="special-icon">
                  <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" stroke="url(#paint0_linear)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M16.24 7.76L14.12 14.12L7.76 16.24L9.88 9.88L16.24 7.76Z" fill="url(#paint0_linear)" stroke="url(#paint0_linear)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  <defs>
                    <linearGradient id="paint0_linear" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
                      <stop stop-color="#FF5722"/>
                      <stop offset="1" stop-color="#FF9800"/>
                    </linearGradient>
                  </defs>
                </svg>
                Narrative Guidance Direction
              </span>
              <p class="narrative-text">{{ simulationConfig.event_config.narrative_direction }}</p>
            </div>

            <!-- Hot Topics -->
            <div class="topics-section">
              <span class="box-label">Initial Hot Topics</span>
              <div class="hot-topics-grid">
                <span v-for="topic in simulationConfig.event_config.hot_topics" :key="topic" class="hot-topic-tag">
                  # {{ topic }}
                </span>
              </div>
            </div>

            <!-- Initial Posts Stream -->
            <div class="initial-posts-section">
              <span class="box-label">Initial Activation Sequence ({{ simulationConfig.event_config.initial_posts.length }})</span>
              <div class="posts-timeline">
                <div v-for="(post, idx) in simulationConfig.event_config.initial_posts" :key="idx" class="timeline-item">
                  <div class="timeline-marker"></div>
                  <div class="timeline-content">
                    <div class="post-header">
                      <span class="post-role">{{ post.poster_type }}</span>
                      <span class="post-agent-info">
                        <span class="post-id">Agent {{ post.poster_agent_id }}</span>
                        <span class="post-username">@{{ getAgentUsername(post.poster_agent_id) }}</span>
                      </span>
                    </div>
                    <p class="post-text">{{ post.content }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 05: Preparation Complete -->
      <div class="step-card" :class="{ 'active': phase === 4 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">05</span>
            <span class="step-title">Preparation Complete</span>
          </div>
          <div class="step-status">
            <span v-if="phase >= 4" class="badge processing">In Progress</span>
            <span v-else class="badge pending">Waiting</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/start</p>
          <p class="description">Simulation environment is ready, you can start running the simulation</p>
          
          <!-- Simulation rounds config - only shown after config generation and rounds calculation -->
          <div v-if="simulationConfig && autoGeneratedRounds" class="rounds-config-section">
            <div class="rounds-header">
              <div class="header-left">
                <span class="section-title">Simulation Round Settings</span>
                <span class="section-desc">MiroShark automatically plans to simulate <span class="desc-highlight">{{ simulationConfig?.time_config?.total_simulation_hours || '-' }}</span> hours of reality, each round represents <span class="desc-highlight">{{ simulationConfig?.time_config?.minutes_per_round || '-' }}</span> minutes of elapsed time</span>
              </div>
              <label class="switch-control">
                <input type="checkbox" v-model="useCustomRounds">
                <span class="switch-track"></span>
                <span class="switch-label">Custom</span>
              </label>
            </div>
            
            <Transition name="fade" mode="out-in">
              <div v-if="useCustomRounds" class="rounds-content custom" key="custom">
                <div class="slider-display">
                  <div class="slider-main-value">
                    <span class="val-num">{{ customMaxRounds }}</span>
                    <span class="val-unit">rounds</span>
                  </div>
                  <div class="slider-meta-info">
                    <span>For 100 agents: estimated duration ~{{ Math.round(customMaxRounds * 0.6) }} min</span>
                  </div>
                </div>

                <div class="range-wrapper">
                  <input 
                    type="range" 
                    v-model.number="customMaxRounds" 
                    min="10" 
                    :max="autoGeneratedRounds"
                    step="5"
                    class="minimal-slider"
                    :style="{ '--percent': ((customMaxRounds - 10) / (autoGeneratedRounds - 10)) * 100 + '%' }"
                  />
                  <div class="range-marks">
                    <span>10</span>
                    <span 
                      class="mark-recommend" 
                      :class="{ active: customMaxRounds === 40 }"
                      @click="customMaxRounds = 40"
                      :style="{ position: 'absolute', left: `calc(${(40 - 10) / (autoGeneratedRounds - 10) * 100}% - 30px)` }"
                    >40 (Recommended)</span>
                    <span>{{ autoGeneratedRounds }}</span>
                  </div>
                </div>
              </div>
              
              <div v-else class="rounds-content auto" key="auto">
                <div class="auto-info-card">
                  <div class="auto-value">
                    <span class="val-num">{{ autoGeneratedRounds }}</span>
                    <span class="val-unit">rounds</span>
                  </div>
                  <div class="auto-content">
                    <div class="auto-meta-row">
                      <span class="duration-badge">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <circle cx="12" cy="12" r="10"></circle>
                          <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        For 100 agents: estimated duration {{ Math.round(autoGeneratedRounds * 0.6) }} min
                      </span>
                    </div>
                    <div class="auto-desc">
                      <p class="highlight-tip" @click="useCustomRounds = true">For first-time runs, it is strongly recommended to switch to ‘Custom Mode’ to reduce simulation rounds for a quick preview and lower error risk ➝</p>
                    </div>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <div class="action-group dual">
            <button 
              class="action-btn secondary"
              @click="$emit('go-back')"
            >
              ← Back to Graph Building
            </button>
            <button 
              class="action-btn primary"
              :disabled="phase < 4"
              @click="handleStartSimulation"
            >
              {{ hasRunBefore ? 'Resume Simulation ➝' : 'Start Simulation ➝' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Profile Detail Modal -->
    <Transition name="modal">
      <div v-if="selectedProfile" class="profile-modal-overlay" @click.self="selectedProfile = null">
        <div class="profile-modal">
          <div class="modal-header">
          <div class="modal-header-info">
            <div class="modal-name-row">
              <span class="modal-realname">{{ selectedProfile.username }}</span>
              <span class="modal-username">@{{ selectedProfile.name }}</span>
            </div>
            <span class="modal-profession">{{ selectedProfile.profession }}</span>
          </div>
          <button class="close-btn" @click="selectedProfile = null">×</button>
        </div>
        
        <div class="modal-body">
          <!-- Basic Info -->
          <div class="modal-info-grid">
            <div class="info-item">
              <span class="info-label">Apparent Age</span>
              <span class="info-value">{{ selectedProfile.age || '-' }} years old</span>
            </div>
            <div class="info-item">
              <span class="info-label">Apparent Gender</span>
              <span class="info-value">{{ { male: 'Male', female: 'Female', other: 'Other' }[selectedProfile.gender] || selectedProfile.gender }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Country/Region</span>
              <span class="info-value">{{ selectedProfile.country || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Apparent MBTI</span>
              <span class="info-value mbti">{{ selectedProfile.mbti || '-' }}</span>
            </div>
          </div>

          <!-- Bio -->
          <div class="modal-section">
            <span class="section-label">Persona Summary</span>
            <p class="section-bio">{{ selectedProfile.bio || 'No bio available' }}</p>
          </div>

          <!-- Related Topics -->
          <div class="modal-section" v-if="selectedProfile.interested_topics?.length">
            <span class="section-label">Real-World Seed Related Topics</span>
            <div class="topics-grid">
              <span 
                v-for="topic in selectedProfile.interested_topics" 
                :key="topic" 
                class="topic-item"
              >{{ topic }}</span>
            </div>
          </div>

          <!-- Detailed Persona -->
          <div class="modal-section" v-if="selectedProfile.persona">
            <span class="section-label">Detailed Persona Background</span>
            
            <!-- Persona Dimension Overview -->
            <div class="persona-dimensions">
              <div class="dimension-card">
                <span class="dim-title">Full Event Experience</span>
                <span class="dim-desc">Complete behavioral trajectory in this event</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">Behavioral Pattern Profile</span>
                <span class="dim-desc">Experience summary and behavioral style preferences</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">Unique Memory Imprint</span>
                <span class="dim-desc">Memories formed from real-world seeds</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">Social Relationship Network</span>
                <span class="dim-desc">Individual connections and interaction graph</span>
              </div>
            </div>

            <div class="persona-content">
              <p class="section-persona">{{ selectedProfile.persona }}</p>
            </div>
          </div>
        </div>
      </div>
      </div>
    </Transition>

    <!-- Bottom Info / Logs -->
    <div class="system-logs" :class="{ collapsed: dashboardCollapsed }">
      <div class="log-header" @click="dashboardCollapsed = !dashboardCollapsed">
        <span class="log-title">SYSTEM DASHBOARD <span class="log-toggle">{{ dashboardCollapsed ? '▲' : '▼' }}</span></span>
        <span class="log-id">{{ simulationId || 'NO_SIMULATION' }}</span>
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
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import {
  prepareSimulation,
  getPrepareStatus,
  getSimulationProfilesRealtime,
  getSimulationConfig,
  getSimulationConfigRealtime,
  retrySimulationConfig,
  getRunStatus
} from '../api/simulation'

const props = defineProps({
  simulationId: String,  // passed from parent component
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

// State
const phase = ref(0) // 0: Initializing, 1: Generating Profiles, 2: Generating Config, 3: Complete
const taskId = ref(null)
const prepareProgress = ref(0)
const currentStage = ref('')
const progressMessage = ref('')
const profiles = ref([])
const entityTypes = ref([])
const expectedTotal = ref(null)
const simulationConfig = ref(null)
const selectedProfile = ref(null)
const showProfilesDetail = ref(true)
const configError = ref(null)       // Error message when config generation fails
const isConfigRetrying = ref(false) // True while retry is in progress

// Config polling timeout: stop after 90 seconds with no result
const CONFIG_POLL_TIMEOUT_MS = 90000
let configPollStartTime = null

// Log deduplication: track last logged key info
let lastLoggedMessage = ''
let lastLoggedProfileCount = 0
let lastLoggedConfigStage = ''

// Simulation rounds configuration
const useCustomRounds = ref(false) // default: use auto-configured rounds
const customMaxRounds = ref(40)   // default recommended: 40 rounds

// Watch stage to update phase
watch(currentStage, (newStage) => {
  if (newStage === 'Generating Agent Personas' || newStage === 'generating_profiles') {
    phase.value = 1
  } else if (newStage === 'Generating Simulation Config' || newStage === 'generating_config') {
    phase.value = 2
    // Entering config generation phase, start polling config
    if (!configTimer) {
      addLog('Starting to generate Dual-Platform Simulation Config...')
      startConfigPolling()
    }
  } else if (newStage === 'Preparing Simulation Scripts' || newStage === 'copying_scripts') {
    phase.value = 2 // still in config phase
  }
})

// Calculate auto-generated rounds from config (no hardcoded defaults)
const autoGeneratedRounds = computed(() => {
  if (!simulationConfig.value?.time_config) {
    return null // return null when config not yet generated
  }
  const totalHours = simulationConfig.value.time_config.total_simulation_hours
  const minutesPerRound = simulationConfig.value.time_config.minutes_per_round
  if (!totalHours || !minutesPerRound) {
    return null // return null when config data is incomplete
  }
  const calculatedRounds = Math.floor((totalHours * 60) / minutesPerRound)
  // Ensure max rounds is not less than 40 (recommended value) to avoid slider range issues
  return Math.max(calculatedRounds, 40)
})

// Polling timer
let pollTimer = null
let profilesTimer = null
let configTimer = null

// Computed
const displayProfiles = computed(() => {
  if (showProfilesDetail.value) {
    return profiles.value
  }
  return profiles.value.slice(0, 6)
})

// Get full profile by agent_id
const getAgentProfile = (agentId) => {
  if (profiles.value && profiles.value.length > agentId && agentId >= 0) {
    return profiles.value[agentId]
  }
  return null
}

// Get username by agent_id
const getAgentUsername = (agentId) => {
  if (profiles.value && profiles.value.length > agentId && agentId >= 0) {
    const profile = profiles.value[agentId]
    return profile?.username || `agent_${agentId}`
  }
  return `agent_${agentId}`
}

// Calculate total related topics across all personas
const totalTopicsCount = computed(() => {
  return profiles.value.reduce((sum, p) => {
    return sum + (p.interested_topics?.length || 0)
  }, 0)
})

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

// Handle start simulation button click
const handleStartSimulation = () => {
  // Build parameters to pass to parent component
  const params = {}

  if (useCustomRounds.value) {
    // User custom rounds, pass max_rounds parameter
    params.maxRounds = customMaxRounds.value
    addLog(`Starting simulation, custom rounds: ${customMaxRounds.value} rounds`)
  } else {
    // User chose to keep auto-generated rounds, no max_rounds parameter passed
    addLog(`Starting simulation, using auto-configured rounds: ${autoGeneratedRounds.value} rounds`)
  }
  
  emit('next-step', params)
}

const truncateBio = (bio) => {
  if (bio.length > 80) {
    return bio.substring(0, 80) + '...'
  }
  return bio
}

const selectProfile = (profile) => {
  selectedProfile.value = profile
}

// Automatically start simulation preparation
const startPrepareSimulation = async () => {
  if (!props.simulationId) {
    addLog('Error: missing simulationId')
    emit('update-status', 'error')
    return
  }
  
  // Mark first step complete, start second step
  phase.value = 1
  addLog(`Simulation instance created: ${props.simulationId}`)
  addLog('Preparing simulation environment...')
  emit('update-status', 'processing')
  
  try {
    const res = await prepareSimulation({
      simulation_id: props.simulationId,
      use_llm_for_profiles: true,
      parallel_profile_count: 5
    })
    
    if (res.success && res.data) {
      if (res.data.already_prepared) {
        addLog('Detected existing completed preparation, using directly')
        await loadPreparedData()
        return
      }
      
      taskId.value = res.data.task_id
      addLog(`Preparation task started`)
      addLog(`  └─ Task ID: ${res.data.task_id}`)
      
      // Set Expected Total Agents immediately (from prepare API response)
      if (res.data.expected_entities_count) {
        expectedTotal.value = res.data.expected_entities_count
        addLog(`Read ${res.data.expected_entities_count} entities from knowledge graph`)
        if (res.data.entity_types && res.data.entity_types.length > 0) {
          addLog(`  └─ Entity types: ${res.data.entity_types.join(', ')}`)
        }
      }
      
      addLog('Starting to poll preparation progress...')
      // Start polling progress
      startPolling()
      // Start fetching profiles in real-time
      startProfilesPolling()
    } else {
      addLog(`Preparation failed: ${res.error || 'Unknown error'}`)
      emit('update-status', 'error')
    }
  } catch (err) {
    addLog(`Preparation error: ${err.message}`)
    emit('update-status', 'error')
  }
}

const startPolling = () => {
  pollTimer = setInterval(pollPrepareStatus, 2000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const startProfilesPolling = () => {
  profilesTimer = setInterval(fetchProfilesRealtime, 3000)
}

const stopProfilesPolling = () => {
  if (profilesTimer) {
    clearInterval(profilesTimer)
    profilesTimer = null
  }
}

const pollPrepareStatus = async () => {
  if (!taskId.value && !props.simulationId) return
  
  try {
    const res = await getPrepareStatus({
      task_id: taskId.value,
      simulation_id: props.simulationId
    })
    
    if (res.success && res.data) {
      const data = res.data
      
      // Update progress
      prepareProgress.value = data.progress || 0
      progressMessage.value = data.message || ''
      
      // Parse stage info and output detailed logs
      if (data.progress_detail) {
        currentStage.value = data.progress_detail.current_stage_name || ''
        
        // Output detailed progress log (avoid duplicates)
        const detail = data.progress_detail
        const logKey = `${detail.current_stage}-${detail.current_item}-${detail.total_items}`
        if (logKey !== lastLoggedMessage && detail.item_description) {
          lastLoggedMessage = logKey
          const stageInfo = `[${detail.stage_index}/${detail.total_stages}]`
          if (detail.total_items > 0) {
            addLog(`${stageInfo} ${detail.current_stage_name}: ${detail.current_item}/${detail.total_items} - ${detail.item_description}`)
          } else {
            addLog(`${stageInfo} ${detail.current_stage_name}: ${detail.item_description}`)
          }
        }
      } else if (data.message) {
        // Extract stage from message
        const match = data.message.match(/\[(\d+)\/(\d+)\]\s*([^:]+)/)
        if (match) {
          currentStage.value = match[3].trim()
        }
        // Output message log (avoid duplicates)
        if (data.message !== lastLoggedMessage) {
          lastLoggedMessage = data.message
          addLog(data.message)
        }
      }
      
      // Check if completed
      if (data.status === 'completed' || data.status === 'ready' || data.already_prepared) {
        addLog('✓ Preparation completed')
        stopPolling()
        stopProfilesPolling()
        await loadPreparedData()
      } else if (data.status === 'failed') {
        addLog(`✗ Preparation failed: ${data.error || 'Unknown error'}`)
        stopPolling()
        stopProfilesPolling()
      }
    }
  } catch (err) {
    console.warn('Polling status failed:', err)
  }
}

const fetchProfilesRealtime = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getSimulationProfilesRealtime(props.simulationId, 'reddit')
    
    if (res.success && res.data) {
      const prevCount = profiles.value.length
      profiles.value = res.data.profiles || []
      // Only update when API returns valid value, avoid overwriting existing valid value
      if (res.data.total_expected) {
        expectedTotal.value = res.data.total_expected
      }
      
      // Extract entity types
      const types = new Set()
      profiles.value.forEach(p => {
        if (p.entity_type) types.add(p.entity_type)
      })
      entityTypes.value = Array.from(types)
      
      // Output profile generation progress log (only when count changes)
      const currentCount = profiles.value.length
      if (currentCount > 0 && currentCount !== lastLoggedProfileCount) {
        lastLoggedProfileCount = currentCount
        const total = expectedTotal.value || '?'
        const latestProfile = profiles.value[currentCount - 1]
        const profileName = latestProfile?.name || latestProfile?.username || `Agent_${currentCount}`
        if (currentCount === 1) {
          addLog(`Starting to generate agent personas...`)
        }
        addLog(`→ Agent persona ${currentCount}/${total}: ${profileName} (${latestProfile?.profession || 'Unknown Profession'})`)
        
        // If all generated
        if (expectedTotal.value && currentCount >= expectedTotal.value) {
          addLog(`✓ All ${currentCount} agent personas generated`)
        }
      }
    }
  } catch (err) {
    console.warn('Failed to get profiles:', err)
  }
}

// Config polling
const startConfigPolling = () => {
  configError.value = null
  configPollStartTime = Date.now()
  configTimer = setInterval(fetchConfigRealtime, 2000)
}

const stopConfigPolling = () => {
  if (configTimer) {
    clearInterval(configTimer)
    configTimer = null
  }
}

const fetchConfigRealtime = async () => {
  if (!props.simulationId) return

  // Client-side timeout: give up after CONFIG_POLL_TIMEOUT_MS
  if (configPollStartTime && Date.now() - configPollStartTime > CONFIG_POLL_TIMEOUT_MS) {
    stopConfigPolling()
    configError.value = 'Config generation timed out after 90 seconds. The LLM may be unresponsive or overloaded.'
    addLog('✗ Config generation timed out (90s). Use "Retry Config" to try again.')
    return
  }

  try {
    const res = await getSimulationConfigRealtime(props.simulationId)

    if (res.success && res.data) {
      const data = res.data

      // Backend reported a generation failure
      if (data.config_error || data.status === 'failed') {
        stopConfigPolling()
        const reason = data.config_error || 'Generation failed — check your OpenRouter API key and model name'
        configError.value = reason
        addLog(`✗ Config generation failed: ${reason}`)
        return
      }

      // Output config generation stage log (avoid duplicates)
      if (data.generation_stage && data.generation_stage !== lastLoggedConfigStage) {
        lastLoggedConfigStage = data.generation_stage
        if (data.generation_stage === 'generating_profiles') {
          addLog('Generating agent persona configuration...')
        } else if (data.generation_stage === 'generating_config') {
          addLog('Calling LLM to generate simulation configuration parameters...')
        }
      }

      // If config has been generated
      if (data.config_generated && data.config) {
        simulationConfig.value = data.config
        addLog('✓ Simulation configuration generated')

        // Show detailed config summary
        if (data.summary) {
          addLog(`  ├─ Agent count: ${data.summary.total_agents}`)
          addLog(`  ├─ Simulation duration: ${data.summary.simulation_hours} hours`)
          addLog(`  ├─ Initial posts: ${data.summary.initial_posts_count}`)
          addLog(`  ├─ Hot topics: ${data.summary.hot_topics_count}`)
          addLog(`  └─ Platform config: Twitter ${data.summary.has_twitter_config ? '✓' : '✗'}, Reddit ${data.summary.has_reddit_config ? '✓' : '✗'}`)
        }

        // Show time configuration details
        if (data.config.time_config) {
          const tc = data.config.time_config
          addLog(`Time config: ${tc.minutes_per_round} minutes per round, ${Math.floor((tc.total_simulation_hours * 60) / tc.minutes_per_round)} rounds total`)
        }

        // Show event configuration
        if (data.config.event_config?.narrative_direction) {
          const narrative = data.config.event_config.narrative_direction
          addLog(`Narrative direction: ${narrative.length > 50 ? narrative.substring(0, 50) + '...' : narrative}`)
        }

        stopConfigPolling()
        phase.value = 4
        addLog('✓ Environment setup complete, ready to start simulation')
        emit('update-status', 'completed')
      }
    }
  } catch (err) {
    console.warn('Failed to get config:', err)
  }
}

const handleConfigRetry = async () => {
  if (!props.simulationId || isConfigRetrying.value) return
  isConfigRetrying.value = true
  configError.value = null
  lastLoggedConfigStage = ''
  addLog('Retrying config generation...')

  try {
    const res = await retrySimulationConfig(props.simulationId)
    if (res.success) {
      addLog('Config retry started — waiting for LLM...')
      startConfigPolling()
    } else {
      configError.value = res.error || 'Retry failed — check backend logs'
      addLog(`✗ Retry failed: ${res.error || 'unknown error'}`)
    }
  } catch (err) {
    configError.value = err.message || 'Retry request failed'
    addLog(`✗ Retry error: ${err.message}`)
  } finally {
    isConfigRetrying.value = false
  }
}

const loadPreparedData = async () => {
  phase.value = 2
  addLog('Loading existing configuration data...')

  // Fetch profiles one last time
  await fetchProfilesRealtime()
  addLog(`Loaded ${profiles.value.length} agent personas`)

  // Get config (using real-time API)
  try {
    const res = await getSimulationConfigRealtime(props.simulationId)
    if (res.success && res.data) {
      if (res.data.config_generated && res.data.config) {
        simulationConfig.value = res.data.config
        addLog('✓ Simulation configuration loaded successfully')

        // Show detailed config summary
        if (res.data.summary) {
          addLog(`  ├─ Agent count: ${res.data.summary.total_agents}`)
          addLog(`  ├─ Simulation duration: ${res.data.summary.simulation_hours} hours`)
          addLog(`  └─ Initial posts: ${res.data.summary.initial_posts_count}`)
        }
        
        addLog('✓ Environment setup complete, ready to start simulation')
        phase.value = 4
        emit('update-status', 'completed')
      } else {
        // Config not yet generated, start polling
        addLog('Config generating, starting to poll...')
        startConfigPolling()
      }
    }
  } catch (err) {
    addLog(`Failed to load configuration: ${err.message}`)
    emit('update-status', 'error')
  }
}

// Scroll log to bottom
const logContent = ref(null)
const dashboardCollapsed = ref(true)
const hasRunBefore = ref(false)

const copyValue = (val) => {
  if (!val) return
  navigator.clipboard.writeText(val)
}
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

onMounted(async () => {
  if (props.simulationId) {
    // Check if this simulation has run before
    try {
      const res = await getRunStatus(props.simulationId)
      if (res.success && res.data && res.data.current_round > 0) {
        hasRunBefore.value = true
      }
    } catch (err) {
      // no run state — fresh simulation
    }

    addLog('Step 2 Agent Setup Initializing')
    startPrepareSimulation()
  }
})

onUnmounted(() => {
  stopPolling()
  stopProfilesPolling()
  stopConfigPolling()
})
</script>

<style scoped>
.env-setup-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #FAFAFA;
  font-family: var(--font-mono);
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

/* Step Card */
.step-card {
  background: #FAFAFA;
  padding: 22px;
  border: 2px solid rgba(10,10,10,0.08);
  transition: all 0.3s ease;
  position: relative;
}

.step-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 34px;
  height: 3px;
  background: #FF6B1A;
}

.step-card::after {
  content: '';
  position: absolute;
  bottom: 0;
  right: 0;
  width: 34px;
  height: 3px;
  background: #43C165;
}

.step-card.active {
  border-color: #FF6B1A;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
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
.badge.pending { background: var(--color-gray); color: rgba(10,10,10,0.4); }
.badge.accent { background: rgba(255,107,26,0.1); color: #FF6B1A; }
.badge.error { background: #FF4444; color: #FAFAFA; }

.step-card.error { border-color: rgba(255,68,68,0.3); }

.config-error-panel {
  border: 2px solid #FF4444;
  background: rgba(255,68,68,0.04);
  padding: 16px;
  margin-bottom: 16px;
}

.config-error-title {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 3px;
  color: #FF4444;
  margin-bottom: 8px;
}

.config-error-msg {
  font-size: 13px;
  color: rgba(10,10,10,0.7);
  margin-bottom: 8px;
  word-break: break-word;
}

.config-error-hint {
  font-size: 12px;
  color: rgba(10,10,10,0.5);
  margin-bottom: 14px;
  line-height: 1.6;
}

.config-error-hint code {
  font-family: var(--font-mono);
  background: rgba(10,10,10,0.06);
  padding: 1px 4px;
  font-size: 11px;
}

.retry-config-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  background: #FF4444;
  color: #FAFAFA;
  border: none;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  cursor: pointer;
  transition: background 0.2s;
}

.retry-config-btn:hover:not(:disabled) { background: #E03C3C; }
.retry-config-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.loading-spinner-small {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #FAFAFA;
  animation: spin 0.8s linear infinite;
}


.card-content {
  /* No extra padding - uses step-card's padding */
}

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
  margin-bottom: 16px;
}

/* Action Section */
.action-section {
  margin-top: 16px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn.primary {
  background: #0A0A0A;
  color: #FAFAFA;
}

.action-btn.primary:hover:not(:disabled) {
  opacity: 0.8;
}

.action-btn.secondary {
  background: var(--color-gray);
  color: rgba(10,10,10,0.7);
}

.action-btn.secondary:hover:not(:disabled) {
  background: rgba(10,10,10,0.08);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-group {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.action-group.dual {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.action-group.dual .action-btn {
  width: 100%;
}

/* Info Card */
.info-card {
  background: var(--color-gray);
  padding: 16px;
  margin-top: 16px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px dashed rgba(10,10,10,0.12);
  cursor: pointer;
  user-select: none;
}

.info-row:hover .info-value.copyable {
  color: #0A0A0A;
  text-decoration: underline;
}

.info-row:active .info-value.copyable {
  color: #43C165;
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  text-transform: uppercase;
  letter-spacing: 3px;
}

.info-value {
  font-size: 13px;
  font-weight: 500;
}

.info-value.mono {
  font-family: var(--font-mono);
  font-size: 12px;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 11px;
  background: var(--color-gray);
  padding: 16px;
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

/* Profiles Preview */
.profiles-preview {
  margin-top: 22px;
  border-top: 2px solid rgba(10,10,10,0.08);
  padding-top: 16px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.preview-title {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: rgba(10,10,10,0.5);
  text-transform: uppercase;
  letter-spacing: 3px;
}

.profiles-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}


.profile-card {
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 0;
  overflow: hidden;
}

.profile-card:hover {
  border-color: #FF6B1A;
  background: #FAFAFA;
}

.profile-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
  overflow: hidden;
}

.profile-header > * {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.profile-realname {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: #0A0A0A;
}

.profile-username {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.4);
}

.profile-meta {
  margin-bottom: 8px;
}

.profile-profession {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  background: var(--color-gray);
  padding: 2px 8px;
}

.profile-bio {
  font-size: 12px;
  color: rgba(10,10,10,0.5);
  line-height: 1.6;
  margin: 0 0 10px 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.profile-topics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topic-tag {
  font-family: var(--font-mono);
  font-size: 10px;
  color: #FF6B1A;
  background: rgba(255,107,26,0.1);
  padding: 2px 8px;
}

.topic-more {
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  padding: 2px 6px;
}

/* Config Preview */
/* Config Detail Panel */
.config-detail-panel {
  margin-top: 16px;
}

.config-block {
  margin-top: 16px;
  border-top: 2px solid rgba(10,10,10,0.08);
  padding-top: 12px;
}

.config-block:first-child {
  margin-top: 0;
  border-top: none;
  padding-top: 0;
}

.config-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.config-block-title {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: rgba(10,10,10,0.5);
  text-transform: uppercase;
  letter-spacing: 3px;
}

.config-block-badge {
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--color-gray);
  color: rgba(10,10,10,0.5);
  padding: 2px 8px;
}

/* Config Grid */
.config-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.config-item {
  background: var(--color-gray);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.config-item-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
}

.config-item-value {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 600;
  color: #0A0A0A;
}

/* Time Periods */
.time-periods {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.period-item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 8px 12px;
  background: var(--color-gray);
}

.period-label {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  color: rgba(10,10,10,0.5);
  min-width: 70px;
}

.period-hours {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  flex: 1;
}

.period-multiplier {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: #FF6B1A;
  background: rgba(255,107,26,0.1);
  padding: 2px 6px;
}

/* Agents Cards */
.agents-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}


.agent-card {
  background: var(--color-gray);
  border: 2px solid rgba(10,10,10,0.08);
  padding: 14px;
  transition: all 0.2s ease;
  min-width: 0;
  overflow: hidden;
}

.agent-card:hover {
  border-color: #FF6B1A;
  background: #FAFAFA;
}

/* Agent Card Header */
.agent-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

.agent-identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-id {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
}

.agent-name {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: #0A0A0A;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-tags {
  display: flex;
  gap: 6px;
}

.agent-type {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.5);
  background: var(--color-gray);
  padding: 2px 8px;
}

.agent-stance {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 3px;
  padding: 2px 8px;
}

.stance-neutral {
  background: var(--color-gray);
  color: rgba(10,10,10,0.5);
}

.stance-supportive {
  background: rgba(67,193,101,0.1);
  color: #43C165;
}

.stance-opposing {
  background: rgba(255,68,68,0.1);
  color: #FF4444;
}

.stance-observer {
  background: rgba(255,179,71,0.1);
  color: #FFB347;
}

/* Agent Profile Info */
.agent-profile-info {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: flex-start;
}

.profile-profession-tag,
.profile-country-tag,
.profile-mbti-tag {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  padding: 2px 8px;
  border: 2px solid rgba(10,10,10,0.08);
  color: rgba(10,10,10,0.5);
  letter-spacing: 0.5px;
}

.profile-profession-tag { border-color: var(--color-orange, #FF6B1A); color: var(--color-orange, #FF6B1A); }
.profile-mbti-tag { border-color: var(--color-green, #43C165); color: var(--color-green, #43C165); }

.profile-bio-snippet {
  width: 100%;
  font-size: 0.75rem;
  color: rgba(10,10,10,0.4);
  line-height: 1.4;
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Agent Timeline */
.agent-timeline {
  margin-bottom: 14px;
}

.timeline-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.mini-timeline {
  display: flex;
  gap: 2px;
  height: 16px;
  background: var(--color-gray);
  padding: 3px;
}

.timeline-hour {
  flex: 1;
  background: rgba(10,10,10,0.08);
  transition: all 0.2s;
}

.timeline-hour.active {
  background: #FF6B1A;
}

.timeline-marks {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-family: var(--font-mono);
  font-size: 9px;
  color: rgba(10,10,10,0.4);
}

/* Agent Params */
.agent-params {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.param-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.param-item .param-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
}

.param-item .param-value {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  color: rgba(10,10,10,0.5);
}

.param-value.with-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mini-bar {
  height: 4px;
  background: #FF6B1A;
  min-width: 4px;
  max-width: 40px;
}

.param-value.positive {
  color: #43C165;
}

.param-value.negative {
  color: #FF4444;
}

.param-value.neutral {
  color: rgba(10,10,10,0.5);
}

.param-value.highlight {
  color: #FF6B1A;
}

/* Platforms Grid */
.platforms-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.platform-card {
  background: var(--color-gray);
  padding: 14px;
  border: 2px solid rgba(10,10,10,0.08);
}

.platform-card-header {
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

.platform-name {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

.platform-params {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.param-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.param-label {
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgba(10,10,10,0.5);
}

.param-value {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  color: #0A0A0A;
}

/* Reasoning Content */
.reasoning-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reasoning-item {
  padding: 12px 14px;
  background: var(--color-gray);
}

.reasoning-text {
  font-size: 13px;
  color: rgba(10,10,10,0.5);
  line-height: 1.7;
  margin: 0;
}

/* Profile Modal */
.profile-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.profile-modal {
  background: #FAFAFA;
  width: 90%;
  max-width: 600px;
  max-height: 85vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border: 2px solid rgba(10,10,10,0.12);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 22px;
  background: #FAFAFA;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

.modal-header-info {
  flex: 1;
}

.modal-name-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}

.modal-realname {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: #0A0A0A;
}

.modal-username {
  font-family: var(--font-mono);
  font-size: 13px;
  color: rgba(10,10,10,0.4);
}

.modal-profession {
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgba(10,10,10,0.5);
  background: var(--color-gray);
  padding: 4px 10px;
  display: inline-block;
  font-weight: 500;
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  color: rgba(10,10,10,0.4);
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: color 0.2s;
  padding: 0;
}

.close-btn:hover {
  color: rgba(10,10,10,0.7);
}

.modal-body {
  padding: 22px;
  overflow-y: auto;
  flex: 1;
}

/* Basic Info Grid */
.modal-info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px 16px;
  margin-bottom: 32px;
  padding: 0;
  background: transparent;
  border-radius: 0;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
  font-weight: 600;
}

.info-value {
  font-size: 15px;
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

.info-value.mbti {
  font-family: var(--font-mono);
  color: #FF6B1A;
}

/* Section Area */
.modal-section {
  margin-bottom: 28px;
}

.section-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 12px;
}

.section-bio {
  font-size: 14px;
  color: rgba(10,10,10,0.7);
  line-height: 1.6;
  margin: 0;
  padding: 16px;
  background: var(--color-gray);
  border-left: 3px solid rgba(10,10,10,0.12);
}

/* Topic Tags */
.topics-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.topic-item {
  font-family: var(--font-mono);
  font-size: 11px;
  color: #FF6B1A;
  background: rgba(255,107,26,0.1);
  padding: 4px 10px;
  transition: all 0.2s;
  border: none;
}

.topic-item:hover {
  background: rgba(255,107,26,0.2);
  color: #FF6B1A;
}

/* Detailed Persona */
.persona-dimensions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.dimension-card {
  background: var(--color-gray);
  padding: 12px;
  border-left: 3px solid rgba(10,10,10,0.12);
  transition: all 0.2s;
}

.dimension-card:hover {
  background: rgba(10,10,10,0.05);
  border-left-color: #FF6B1A;
}

.dim-title {
  display: block;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  color: rgba(10,10,10,0.7);
  margin-bottom: 4px;
}

.dim-desc {
  display: block;
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  line-height: 1.4;
}

.persona-content {
  max-height: none;
  overflow: visible;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
}

.persona-content::-webkit-scrollbar {
  width: 4px;
}

.persona-content::-webkit-scrollbar-thumb {
  background: rgba(10,10,10,0.12);
}

.section-persona {
  font-size: 13px;
  color: rgba(10,10,10,0.5);
  line-height: 1.8;
  margin: 0;
  text-align: justify;
}

/* System Logs */
.system-logs {
  background: #0A0A0A;
  color: rgba(250,250,250,0.8);
  padding: 16px;
  font-family: var(--font-mono);
  border-top: 2px solid rgba(10,10,10,0.12);
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid rgba(250,250,250,0.1);
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 10px;
  color: rgba(250,250,250,0.4);
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
  height: 80px; /* Approx 4 lines visible */
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
  gap: 12px;
  line-height: 1.5;
}

.log-time {
  color: rgba(250,250,250,0.3);
  min-width: 75px;
}

.log-msg {
  color: rgba(250,250,250,0.7);
  word-break: break-all;
}

/* Spinner */
.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(10,10,10,0.08);
  border-top-color: #FF6B1A;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
/* Orchestration Content */
.orchestration-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 16px;
}

.box-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: rgba(10,10,10,0.5);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 11px;
}

.narrative-box {
  background: #FAFAFA;
  padding: 22px;
  border: 2px solid rgba(10,10,10,0.08);
  transition: all 0.3s ease;
}

.narrative-box .box-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(10,10,10,0.5);
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 3px;
  margin-bottom: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.special-icon {
  transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.narrative-box:hover .special-icon {
  transform: rotate(180deg);
}

.narrative-text {
  font-size: 14px;
  color: rgba(10,10,10,0.7);
  line-height: 1.8;
  margin: 0;
  text-align: justify;
  letter-spacing: 0.01em;
}

.topics-section {
  background: #FAFAFA;
}

.hot-topics-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hot-topic-tag {
  font-family: var(--font-mono);
  font-size: 12px;
  color: #FF6B1A;
  background: rgba(255,107,26,0.1);
  padding: 4px 10px;
  font-weight: 500;
}

.hot-topic-more {
  font-size: 11px;
  color: rgba(10,10,10,0.4);
  padding: 4px 6px;
}

.initial-posts-section {
  border-top: 2px solid rgba(10,10,10,0.08);
  padding-top: 16px;
}

.posts-timeline {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-left: 8px;
  border-left: 2px solid rgba(10,10,10,0.08);
  margin-top: 12px;
}

.timeline-item {
  position: relative;
  padding-left: 20px;
}

.timeline-marker {
  position: absolute;
  left: 0;
  top: 14px;
  width: 12px;
  height: 2px;
  background: rgba(10,10,10,0.12);
}

.timeline-content {
  background: var(--color-gray);
  padding: 12px;
  border: 2px solid rgba(10,10,10,0.08);
}

.post-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.post-role {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  color: rgba(10,10,10,0.7);
  text-transform: uppercase;
  letter-spacing: 3px;
}

.post-agent-info {
  display: flex;
  align-items: center;
  gap: 6px;
}

.post-id,
.post-username {
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.5);
  line-height: 1;
  vertical-align: baseline;
}

.post-username {
  margin-right: 6px;
}

.post-text {
  font-size: 12px;
  color: rgba(10,10,10,0.5);
  line-height: 1.5;
  margin: 0;
}

/* Simulation Rounds Configuration Styles */
.rounds-config-section {
  margin: 22px 0;
  padding-top: 22px;
  border-top: 2px solid rgba(10,10,10,0.08);
}

.rounds-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: #0A0A0A;
}

.section-desc {
  font-size: 12px;
  color: rgba(10,10,10,0.4);
}

.desc-highlight {
  font-family: var(--font-mono);
  font-weight: 600;
  color: #0A0A0A;
  background: var(--color-gray);
  padding: 1px 6px;
  margin: 0 2px;
}

/* Switch Control */
.switch-control {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px 4px 4px;
  transition: background 0.2s;
}

.switch-control:hover {
  background: var(--color-gray);
}

.switch-control input {
  display: none;
}

.switch-track {
  width: 36px;
  height: 20px;
  background: rgba(10,10,10,0.12);
  position: relative;
  transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
}

.switch-track::after {
  content: '';
  position: absolute;
  left: 2px;
  top: 2px;
  width: 16px;
  height: 16px;
  background: #FAFAFA;
  transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
}

.switch-control input:checked + .switch-track {
  background: #0A0A0A;
}

.switch-control input:checked + .switch-track::after {
  transform: translateX(16px);
}

.switch-label {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
  color: rgba(10,10,10,0.5);
}

.switch-control input:checked ~ .switch-label {
  color: #0A0A0A;
}

/* Slider Content */
.rounds-content {
  animation: fadeIn 0.3s ease;
}

.slider-display {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 16px;
}

.slider-main-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.val-num {
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 700;
  color: #0A0A0A;
}

.val-unit {
  font-family: var(--font-mono);
  font-size: 12px;
  color: rgba(10,10,10,0.5);
  font-weight: 500;
}

.slider-meta-info {
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  background: var(--color-gray);
  padding: 4px 8px;
}

.range-wrapper {
  position: relative;
  padding: 0 2px;
}

.minimal-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 4px;
  background: rgba(10,10,10,0.08);
  outline: none;
  background-image: linear-gradient(#0A0A0A, #0A0A0A);
  background-size: var(--percent, 0%) 100%;
  background-repeat: no-repeat;
  cursor: pointer;
}

.minimal-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: #FAFAFA;
  border: 2px solid #0A0A0A;
  cursor: pointer;
  transition: transform 0.1s;
  margin-top: -6px; /* Center thumb */
}

.minimal-slider::-webkit-slider-thumb:hover {
  transform: scale(1.1);
}

.minimal-slider::-webkit-slider-runnable-track {
  height: 4px;
}

.range-marks {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  position: relative;
}

.mark-recommend {
  cursor: pointer;
  transition: color 0.2s;
  position: relative;
}

.mark-recommend:hover {
  color: #0A0A0A;
}

.mark-recommend.active {
  color: #0A0A0A;
  font-weight: 600;
}

.mark-recommend::after {
  content: '';
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  width: 1px;
  height: 4px;
  background: rgba(10,10,10,0.12);
}

/* Auto Info */
.auto-info-card {
  display: flex;
  align-items: center;
  gap: 22px;
  background: var(--color-gray);
  padding: 16px 22px;
}

.auto-value {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  gap: 4px;
  padding-right: 22px;
  border-right: 2px solid rgba(10,10,10,0.08);
}

.auto-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
}

.auto-meta-row {
  display: flex;
  align-items: center;
}

.duration-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  color: rgba(10,10,10,0.5);
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  padding: 3px 8px;
}

.auto-desc {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auto-desc p {
  margin: 0;
  font-size: 13px;
  color: rgba(10,10,10,0.5);
  line-height: 1.5;
}

.highlight-tip {
  margin-top: 4px !important;
  font-size: 12px !important;
  color: #0A0A0A !important;
  font-weight: 500;
  cursor: pointer;
}

.highlight-tip:hover {
  text-decoration: underline;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Modal Transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .profile-modal {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.modal-leave-active .profile-modal {
  transition: all 0.3s ease-in;
}

.modal-enter-from .profile-modal,
.modal-leave-to .profile-modal {
  transform: scale(0.95) translateY(10px);
  opacity: 0;
}
</style>
