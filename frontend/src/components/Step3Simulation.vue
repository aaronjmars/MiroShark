<template>
  <div class="simulation-panel">
    <!-- Actions Bar (above platforms) -->
    <div class="actions-bar">
      <!-- Back to Step 2 -->
      <button
        v-if="phase !== 1"
        class="action-btn secondary"
        @click="emit('go-back')"
      >← Config</button>

      <!-- Pause (while running) -->
      <button
        v-if="phase === 1"
        class="action-btn danger"
        :disabled="isStopping"
        @click="handleStopSimulation"
      >
        <span v-if="isStopping" class="loading-spinner-small"></span>
        {{ isStopping ? 'Pausing...' : 'Pause' }}
      </button>

      <!-- Restart (when stopped, completed, or failed) -->
      <button
        v-if="phase === 2 || runStatus.runner_status === 'failed'"
        class="action-btn secondary"
        :disabled="isStarting"
        @click="handleRestart"
      >
        {{ runStatus.runner_status === 'failed' ? 'Restart (failed)' : 'Restart' }}
      </button>

      <!-- Replay (when simulation has data) -->
      <button
        v-if="phase === 2 && allActions.length > 0"
        class="action-btn secondary"
        @click="openReplay"
      >
        ▶ Replay
      </button>

      <!-- Generate Article (when simulation has data) -->
      <button
        v-if="phase === 2 && allActions.length > 0"
        class="action-btn secondary"
        @click="openArticleDrawer"
        title="Generate a publishable article brief from simulation results"
      >
        ✍ Article
      </button>

      <!-- Influence Leaderboard toggle -->
      <button
        v-if="allActions.length > 0"
        class="action-btn secondary"
        :class="{ active: showInfluence }"
        @click="showInfluence = !showInfluence"
        title="Agent influence leaderboard"
      >
        ◈ Influence
      </button>

      <!-- Resume (when paused/stopped/failed with partial data) -->
      <button
        v-if="phase === 2 && hasPartialData"
        class="action-btn secondary"
        :disabled="isStarting"
        @click="handleResume"
      >
        <span v-if="isStarting" class="loading-spinner-small"></span>
        {{ isStarting ? 'Resuming...' : 'Resume' }}
      </button>

      <!-- Skip to Report / Generate Report -->
      <button
        class="action-btn primary"
        :disabled="!canGenerateReport || isGeneratingReport"
        @click="handleNextStep"
      >
        <span v-if="isGeneratingReport" class="loading-spinner-small"></span>
        <template v-if="isGeneratingReport">Starting...</template>
        <template v-else-if="phase === 1">Skip to Report ⟶</template>
        <template v-else>Report →</template>
      </button>
    </div>

    <!-- Total Events Summary -->
    <div class="events-summary">
      <span class="events-label">TOTAL EVENTS:</span>
      <span class="events-total">{{ (runStatus.twitter_actions_count || 0) + (runStatus.reddit_actions_count || 0) + (runStatus.polymarket_actions_count || 0) }}</span>
      <span class="events-divider"></span>
      <span class="events-platform">X <span class="events-count">{{ runStatus.twitter_actions_count || 0 }}</span></span>
      <span class="events-slash">/</span>
      <span class="events-platform">Reddit <span class="events-count">{{ runStatus.reddit_actions_count || 0 }}</span></span>
      <span class="events-slash">/</span>
      <span class="events-platform">Polymarket <span class="events-count">{{ runStatus.polymarket_actions_count || 0 }}</span></span>
    </div>

    <!-- Platform Status Rows -->
    <div class="control-bar">
      <div class="status-group">
        <!-- X (Twitter) -->
        <div class="platform-status twitter" :class="{ active: runStatus.twitter_running, completed: runStatus.twitter_completed, selected: filteredPlatform === 'twitter', dimmed: filteredPlatform && filteredPlatform !== 'twitter' }" @click="filterByPlatform('twitter')">
          <div class="platform-left">
            <svg class="platform-icon" viewBox="0 0 24 24" width="11" height="11" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
            <span class="platform-name">X</span>
            <span v-if="runStatus.twitter_completed" class="status-badge done">done</span>
          </div>
          <div class="platform-stats">
            <span class="stat"><span class="stat-label">RND</span><span class="stat-value mono">{{ runStatus.twitter_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span></span>
            <span class="stat"><span class="stat-label">TIME</span><span class="stat-value mono">{{ twitterElapsedTime }}</span></span>
            <span class="stat"><span class="stat-label">ACTS</span><span class="stat-value mono">{{ runStatus.twitter_actions_count || 0 }}</span></span>
          </div>
          <div class="platform-actions-list"><span class="action-tag">POST</span><span class="action-tag">LIKE</span><span class="action-tag">REPOST</span><span class="action-tag">QUOTE</span><span class="action-tag">FOLLOW</span></div>
        </div>

        <!-- Reddit -->
        <div class="platform-status reddit" :class="{ active: runStatus.reddit_running, completed: runStatus.reddit_completed, selected: filteredPlatform === 'reddit', dimmed: filteredPlatform && filteredPlatform !== 'reddit' }" @click="filterByPlatform('reddit')">
          <div class="platform-left">
            <img src="/reddit.png" class="platform-icon-img" alt="Reddit" />
            <span class="platform-name">Reddit</span>
            <span v-if="runStatus.reddit_completed" class="status-badge done">done</span>
          </div>
          <div class="platform-stats">
            <span class="stat"><span class="stat-label">RND</span><span class="stat-value mono">{{ runStatus.reddit_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span></span>
            <span class="stat"><span class="stat-label">TIME</span><span class="stat-value mono">{{ redditElapsedTime }}</span></span>
            <span class="stat"><span class="stat-label">ACTS</span><span class="stat-value mono">{{ runStatus.reddit_actions_count || 0 }}</span></span>
          </div>
          <div class="platform-actions-list"><span class="action-tag">POST</span><span class="action-tag">COMMENT</span><span class="action-tag">LIKE</span><span class="action-tag">DISLIKE</span><span class="action-tag">SEARCH</span><span class="action-tag">FOLLOW</span></div>
        </div>

        <!-- Polymarket -->
        <div class="platform-status polymarket" :class="{ active: runStatus.polymarket_running, completed: runStatus.polymarket_completed, selected: filteredPlatform === 'polymarket', dimmed: filteredPlatform && filteredPlatform !== 'polymarket' }" @click="filterByPlatform('polymarket')">
          <div class="platform-left">
            <img src="/pm.png" class="platform-icon-img" alt="Polymarket" />
            <span class="platform-name">Polymarket</span>
            <span v-if="runStatus.polymarket_completed" class="status-badge done">done</span>
          </div>
          <div class="platform-stats">
            <span class="stat"><span class="stat-label">RND</span><span class="stat-value mono">{{ runStatus.polymarket_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span></span>
            <span class="stat"><span class="stat-label">TIME</span><span class="stat-value mono">{{ polymarketElapsedTime }}</span></span>
            <span class="stat"><span class="stat-label">TRADES</span><span class="stat-value mono">{{ runStatus.polymarket_actions_count || 0 }}</span></span>
          </div>
          <div class="platform-actions-list"><span class="action-tag">BROWSE</span><span class="action-tag">BUY</span><span class="action-tag">SELL</span><span class="action-tag">CREATE</span><span class="action-tag">COMMENT</span></div>
        </div>
      </div>
    </div>

    <!-- Influence Leaderboard (overlay when toggled) -->
    <InfluenceLeaderboard
      v-if="showInfluence"
      :simulationId="simulationId"
      :visible="showInfluence"
      class="influence-overlay"
    />

    <!-- Main Content: Dual Timeline -->
    <div v-show="!showInfluence" class="main-content-area" ref="scrollContainer" @scroll="onTimelineScroll">
      <!-- Scroll to bottom button -->
      <button
        v-if="showScrollBtn"
        class="scroll-bottom-btn"
        @click="scrollToBottom"
      >↓</button>
      
      <!-- Platform Filter Bar -->
      <div v-if="filteredPlatform" class="agent-filter-bar">
        <div class="filter-info">
          <span class="filter-name" :class="filteredPlatform">{{ filteredPlatform === 'twitter' ? 'X' : filteredPlatform === 'reddit' ? 'Reddit' : 'Polymarket' }}</span>
          <span class="filter-count">{{ chronologicalActions.length }} events</span>
        </div>
        <button class="filter-clear" @click="clearPlatformFilter">Clear</button>
      </div>

      <!-- Agent Filter Bar -->
      <div v-if="filteredAgent" class="agent-filter-bar">
        <div class="filter-info">
          <div class="avatar-placeholder">{{ filteredAgent[0] }}</div>
          <span class="filter-name">{{ filteredAgent }}</span>
          <span class="filter-count">{{ chronologicalActions.length }} events</span>
        </div>
        <button class="filter-clear" @click="clearAgentFilter">Clear</button>
      </div>

      <!-- Timeline Feed -->
      <div class="timeline-feed">
        <div class="timeline-axis"></div>

        <TransitionGroup name="timeline-item">
          <div
            v-for="action in chronologicalActions" 
            :key="action._uniqueId || action.id || `${action.timestamp}-${action.agent_id}`" 
            class="timeline-item"
            :class="action.platform"
          >
            <div class="timeline-marker">
              <div class="marker-dot"></div>
            </div>
            
            <div class="timeline-card">
              <div class="card-header">
                <div class="agent-info clickable" @click="filterByAgent(action.agent_name)">
                  <div class="avatar-placeholder">{{ (action.agent_name || 'A')[0] }}</div>
                  <span class="agent-name">{{ action.agent_name }}</span>
                </div>
                
                <div class="header-meta">
                  <div class="platform-indicator" :class="action.platform">
                    <svg v-if="action.platform === 'twitter'" viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                    <img v-else-if="action.platform === 'reddit'" src="/reddit.png" class="platform-logo" alt="Reddit" />
                    <img v-else-if="action.platform === 'polymarket'" src="/pm.png" class="platform-logo" alt="Polymarket" />
                  </div>
                  <div class="action-badge" :class="getActionTypeClass(action.action_type)">
                    {{ getActionTypeLabel(action.action_type) }}
                  </div>
                </div>
              </div>
              
              <div class="card-body">
                <!-- CREATE_POST: Create Post -->
                <div v-if="action.action_type === 'CREATE_POST' && action.action_args?.content" class="content-text main-text">
                  {{ action.action_args.content }}
                </div>

                <!-- QUOTE_POST: Quote Post -->
                <template v-if="action.action_type === 'QUOTE_POST'">
                  <div v-if="action.action_args?.quote_content" class="content-text">
                    {{ action.action_args.quote_content }}
                  </div>
                  <div v-if="action.action_args?.original_content" class="quoted-block">
                    <div class="quote-header">
                      <svg class="icon-small" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                      <span class="quote-label">@{{ action.action_args.original_author_name || 'User' }}</span>
                    </div>
                    <div class="quote-text">
                      {{ truncateContent(action.action_args.original_content, 150) }}
                    </div>
                  </div>
                </template>

                <!-- REPOST: Repost -->
                <template v-if="action.action_type === 'REPOST'">
                  <div class="repost-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path></svg>
                    <span class="repost-label">Reposted from @{{ action.action_args?.original_author_name || 'User' }}</span>
                  </div>
                  <div v-if="action.action_args?.original_content" class="repost-content">
                    {{ truncateContent(action.action_args.original_content, 200) }}
                  </div>
                </template>

                <!-- LIKE_POST: Like Post -->
                <template v-if="action.action_type === 'LIKE_POST'">
                  <div class="like-info">
                    <svg class="icon-small filled" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                    <span class="like-label">Liked @{{ action.action_args?.post_author_name || 'User' }}'s post</span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="liked-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>

                <!-- CREATE_COMMENT: Create Comment -->
                <template v-if="action.action_type === 'CREATE_COMMENT'">
                  <div v-if="action.action_args?.content" class="content-text">
                    {{ action.action_args.content }}
                  </div>
                  <div v-if="action.action_args?.post_id" class="comment-context">
                    <svg class="icon-small" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                    <span>Reply to post #{{ action.action_args.post_id }}</span>
                  </div>
                </template>

                <!-- SEARCH_POSTS: Search Posts -->
                <template v-if="action.action_type === 'SEARCH_POSTS'">
                  <div class="search-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <span class="search-label">Search Query:</span>
                    <span class="search-query">"{{ action.action_args?.query || '' }}"</span>
                  </div>
                </template>

                <!-- FOLLOW: Follow User -->
                <template v-if="action.action_type === 'FOLLOW'">
                  <div class="follow-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
                    <span class="follow-label">Followed @{{ action.action_args?.target_user_name || action.action_args?.target_user || action.action_args?.user_id || 'User' }}</span>
                  </div>
                </template>

                <!-- DISLIKE_POST -->
                <template v-if="action.action_type === 'DISLIKE_POST'">
                  <div class="like-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path></svg>
                    <span class="like-label">Disliked @{{ action.action_args?.post_author_name || 'User' }}'s post</span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="liked-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>

                <!-- DISLIKE_COMMENT -->
                <template v-if="action.action_type === 'DISLIKE_COMMENT'">
                  <div class="like-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path></svg>
                    <span class="like-label">Disliked @{{ action.action_args?.comment_author_name || 'User' }}'s comment</span>
                  </div>
                  <div v-if="action.action_args?.comment_content" class="liked-content">
                    "{{ truncateContent(action.action_args.comment_content, 120) }}"
                  </div>
                </template>

                <!-- MUTE -->
                <template v-if="action.action_type === 'MUTE'">
                  <div class="follow-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5L6 9H2v6h4l5 4V5z"></path><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>
                    <span class="follow-label">Muted @{{ action.action_args?.target_user_name || action.action_args?.user_id || 'User' }}</span>
                  </div>
                </template>

                <!-- UPVOTE / DOWNVOTE -->
                <template v-if="action.action_type === 'UPVOTE_POST' || action.action_type === 'DOWNVOTE_POST'">
                  <div class="vote-info">
                    <svg v-if="action.action_type === 'UPVOTE_POST'" class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"></polyline></svg>
                    <svg v-else class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    <span class="vote-label">{{ action.action_type === 'UPVOTE_POST' ? 'Upvoted' : 'Downvoted' }} Post</span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="voted-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>

                <!-- DO_NOTHING: No Action (Idle) -->
                <template v-if="action.action_type === 'DO_NOTHING'">
                  <div class="idle-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    <span class="idle-label">Action Skipped</span>
                  </div>
                </template>

                <!-- BUY_SHARES -->
                <template v-if="action.action_type === 'BUY_SHARES'">
                  <div class="trade-info">
                    <span class="trade-direction buy">BUY</span>
                    <span class="trade-detail">{{ formatShares(action.action_args?.shares) }} <strong>{{ action.action_args?.outcome }}</strong> shares</span>
                    <span class="trade-cost">@ ${{ formatPrice(action.action_args?.price) }}</span>
                    <span class="trade-total">${{ formatPrice(action.action_args?.cost) }}</span>
                  </div>
                  <div v-if="action.action_args?.market_id" class="market-ref">Market #{{ action.action_args.market_id }}</div>
                </template>

                <!-- SELL_SHARES -->
                <template v-if="action.action_type === 'SELL_SHARES'">
                  <div class="trade-info">
                    <span class="trade-direction sell">SELL</span>
                    <span class="trade-detail">{{ formatShares(action.action_args?.shares) }} <strong>{{ action.action_args?.outcome }}</strong> shares</span>
                    <span class="trade-cost">@ ${{ formatPrice(action.action_args?.price || (action.action_args?.usd_received && action.action_args?.shares ? action.action_args.usd_received / action.action_args.shares : null)) }}</span>
                    <span class="trade-total text-green">${{ formatPrice(action.action_args?.usd_received) }}</span>
                  </div>
                  <div v-if="action.action_args?.market_id" class="market-ref">Market #{{ action.action_args.market_id }}</div>
                </template>

                <!-- CREATE_MARKET -->
                <template v-if="action.action_type === 'CREATE_MARKET'">
                  <div class="market-question">"{{ action.action_args?.question }}"</div>
                  <div v-if="action.action_args?.market_id" class="market-ref">Market #{{ action.action_args.market_id }}</div>
                </template>

                <!-- COMMENT_ON_MARKET -->
                <template v-if="action.action_type === 'COMMENT_ON_MARKET'">
                  <div v-if="action.action_args?.content" class="content-text">{{ action.action_args.content }}</div>
                  <div v-if="action.action_args?.market_id" class="market-ref">Market #{{ action.action_args.market_id }}</div>
                </template>

                <!-- BROWSE_MARKETS / VIEW_PORTFOLIO -->
                <template v-if="action.action_type === 'BROWSE_MARKETS'">
                  <div class="idle-info"><span class="idle-label">Browsed active markets</span></div>
                </template>
                <template v-if="action.action_type === 'VIEW_PORTFOLIO'">
                  <div class="idle-info"><span class="idle-label">Checked portfolio</span></div>
                </template>

                <!-- Generic fallback -->
                <div v-if="!['CREATE_POST', 'QUOTE_POST', 'REPOST', 'LIKE_POST', 'DISLIKE_POST', 'CREATE_COMMENT', 'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'FOLLOW', 'MUTE', 'UPVOTE_POST', 'DOWNVOTE_POST', 'DO_NOTHING', 'BUY_SHARES', 'SELL_SHARES', 'CREATE_MARKET', 'COMMENT_ON_MARKET', 'BROWSE_MARKETS', 'VIEW_PORTFOLIO'].includes(action.action_type) && action.action_args?.content" class="content-text">
                  {{ action.action_args.content }}
                </div>
              </div>

              <div class="card-footer">
                <span class="time-tag">R{{ action.round_num }} • {{ formatActionTime(action.timestamp) }}</span>
                <!-- Platform tag removed as it is in header now -->
              </div>
            </div>
          </div>
        </TransitionGroup>

        <div v-if="allActions.length === 0" class="waiting-state">
          <div class="pulse-ring"></div>
          <span>Waiting for agent actions...</span>
        </div>
      </div>
    </div>

    <!-- Bottom Info / Logs -->
    <div class="system-logs" :class="{ collapsed: monitorCollapsed }">
      <div class="log-header" @click="monitorCollapsed = !monitorCollapsed">
        <span class="log-title">SIMULATION MONITOR <span class="log-toggle">{{ monitorCollapsed ? '▲' : '▼' }}</span></span>
        <span class="log-id copyable" @click.stop="copySimId" :title="copied ? 'Copied!' : 'Click to copy'">{{ simulationId || 'NO_SIMULATION' }}{{ copied ? ' ✓' : '' }}</span>
      </div>
      <div v-show="!monitorCollapsed" class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>

    <!-- Article Drawer Overlay -->
    <Transition name="article-drawer">
      <div v-if="showArticleDrawer" class="article-drawer-overlay" @click.self="showArticleDrawer = false">
        <div class="article-drawer">
          <div class="article-drawer-header">
            <span class="article-drawer-title">Generated Article</span>
            <div class="article-drawer-actions">
              <button
                class="article-action-btn"
                :disabled="isGeneratingArticle || !articleText"
                @click="copyArticle"
                :title="articleCopied ? 'Copied!' : 'Copy to clipboard'"
              >{{ articleCopied ? 'Copied!' : 'Copy' }}</button>
              <button
                class="article-action-btn"
                :disabled="isGeneratingArticle || !articleText"
                @click="downloadArticle"
                title="Download as .md"
              >Download .md</button>
              <button class="article-close-btn" @click="showArticleDrawer = false">✕</button>
            </div>
          </div>

          <div class="article-drawer-body">
            <!-- Loading state -->
            <div v-if="isGeneratingArticle" class="article-loading">
              <div class="article-loading-spinner"></div>
              <span>Generating article from simulation data...</span>
            </div>

            <!-- Error state -->
            <div v-else-if="articleError" class="article-error">
              <span class="article-error-msg">{{ articleError }}</span>
              <button class="article-action-btn" @click="generateArticle">Retry</button>
            </div>

            <!-- Article content -->
            <div
              v-else-if="articleText"
              class="article-content generated-content"
              v-html="renderArticleMarkdown(articleText)"
            ></div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  startSimulation,
  stopSimulation,
  resumeSimulation,
  getRunStatus,
  getRunStatusDetail,
  generateSimulationArticle
} from '../api/simulation'
import { generateReport } from '../api/report'
import InfluenceLeaderboard from './InfluenceLeaderboard.vue'

const props = defineProps({
  simulationId: String,
  maxRounds: Number, // Max rounds passed from Step2
  minutesPerRound: {
    type: Number,
    default: 30 // Default 30 minutes per round
  },
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

const router = useRouter()

// State
const isGeneratingReport = ref(false)
const phase = ref(0) // 0: Not Started, 1: Running, 2: Completed
const isStarting = ref(false)
const isStopping = ref(false)
const startError = ref(null)
const runStatus = ref({})
const allActions = ref([]) // All actions (incremental accumulation)
const actionIds = ref(new Set()) // Action ID set for deduplication
const scrollContainer = ref(null)
const showScrollBtn = ref(false)
const copied = ref(false)
const monitorCollapsed = ref(false)
const filteredAgent = ref(null)
const filteredPlatform = ref(null)
const showInfluence = ref(false)

// Article drawer state
const showArticleDrawer = ref(false)
const articleText = ref('')
const isGeneratingArticle = ref(false)
const articleError = ref(null)
const articleCopied = ref(false)

const filterByAgent = (agentName) => {
  filteredAgent.value = filteredAgent.value === agentName ? null : agentName
}

const clearAgentFilter = () => {
  filteredAgent.value = null
}

const filterByPlatform = (platform) => {
  filteredPlatform.value = filteredPlatform.value === platform ? null : platform
}

const clearPlatformFilter = () => {
  filteredPlatform.value = null
}

const copySimId = () => {
  if (!props.simulationId) return
  navigator.clipboard.writeText(props.simulationId)
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}

const onTimelineScroll = () => {
  const el = scrollContainer.value
  if (!el) return
  showScrollBtn.value = el.scrollTop + el.clientHeight < el.scrollHeight - 100
}

const scrollToBottom = () => {
  const el = scrollContainer.value
  if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
}

// Computed
// Display actions in chronological order (latest at bottom)
const chronologicalActions = computed(() => {
  let actions = allActions.value
  if (filteredPlatform.value) {
    actions = actions.filter(a => a.platform === filteredPlatform.value)
  }
  if (filteredAgent.value) {
    actions = actions.filter(a => a.agent_name === filteredAgent.value)
  }
  return actions
})

// Per-platform action counts
const twitterActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'twitter').length
})

const redditActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'reddit').length
})

const polymarketActionsCount = computed(() => {
  return allActions.value.filter(a => a.platform === 'polymarket').length
})

// Has partial data (not fully completed) — show Resume button
const hasPartialData = computed(() => {
  const currentRound = runStatus.value.current_round || 0
  const totalRounds = runStatus.value.total_rounds || 0
  return currentRound > 0 && currentRound < totalRounds
})

// Can generate report: simulation completed, stopped, failed with data, or currently running with data
const canGenerateReport = computed(() => {
  if (phase.value === 2) return true  // completed/stopped
  if (phase.value === 1) {
    // Allow skip-to-report if we have some actions
    const totalActions = (runStatus.value.twitter_actions_count || 0) + (runStatus.value.reddit_actions_count || 0)
    return totalActions > 0
  }
  return false
})

// Format simulated elapsed time (calculated from rounds and minutes per round)
const formatElapsedTime = (currentRound) => {
  if (!currentRound || currentRound <= 0) return '0h'
  const totalMinutes = currentRound * props.minutesPerRound
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

// Twitter platform simulated elapsed time
const twitterElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.twitter_current_round || 0)
})

// Reddit platform simulated elapsed time
const redditElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.reddit_current_round || 0)
})

// Polymarket platform simulated elapsed time
const polymarketElapsedTime = computed(() => {
  return formatElapsedTime(runStatus.value.polymarket_current_round || 0)
})

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

// Reset all state (for restarting simulation)
const resetAllState = () => {
  phase.value = 0
  runStatus.value = {}
  allActions.value = []
  actionIds.value = new Set()
  prevTwitterRound.value = 0
  prevRedditRound.value = 0
  startError.value = null
  isStarting.value = false
  isStopping.value = false
  stopPolling()  // Stop any previously existing polling
}

// Start simulation
const doStartSimulation = async () => {
  if (!props.simulationId) {
    addLog('Error: missing simulationId')
    return
  }

  // Reset all state first to avoid influence from previous simulation
  resetAllState()

  isStarting.value = true
  startError.value = null
  addLog('Starting dual-platform parallel simulation...')
  emit('update-status', 'processing')
  
  try {
    const params = {
      simulation_id: props.simulationId,
      platform: 'parallel',
      force: true,  // Force restart
      enable_graph_memory_update: true,  // Enable dynamic graph memory update
      enable_cross_platform: true  // Agents see their activity on other platforms
    }
    
    if (props.maxRounds) {
      params.max_rounds = props.maxRounds
      addLog(`Set max simulation rounds: ${props.maxRounds}`)
    }

    addLog('Dynamic graph memory update mode enabled')
    
    const res = await startSimulation(params)
    
    if (res.success && res.data) {
      if (res.data.force_restarted) {
        addLog('Old simulation logs cleaned, restarting simulation')
      }
      addLog('Simulation engine started successfully')
      addLog(`  ├─ PID: ${res.data.process_pid || '-'}`)
      
      phase.value = 1
      runStatus.value = res.data
      
      startStatusPolling()
      startDetailPolling()
    } else {
      startError.value = res.error || 'Start failed'
      addLog(`Start failed: ${res.error || 'Unknown error'}`)
      emit('update-status', 'error')
    }
  } catch (err) {
    startError.value = err.message
    addLog(`Start error: ${err.message}`)
    emit('update-status', 'error')
  } finally {
    isStarting.value = false
  }
}

// Resume simulation from last completed round
const handleResume = async () => {
  if (!props.simulationId) return

  const fromRound = runStatus.value.current_round || 0
  addLog(`Resuming simulation from round ${fromRound}...`)

  isStarting.value = true
  startError.value = null
  emit('update-status', 'processing')

  try {
    const params = {
      simulation_id: props.simulationId,
      platform: 'parallel',
      enable_graph_memory_update: true
    }

    if (props.maxRounds) {
      params.max_rounds = props.maxRounds
    }

    const res = await resumeSimulation(params)

    if (res.success && res.data) {
      addLog(`Resumed from round ${res.data.resumed_from_round || fromRound}`)
      addLog(`  ├─ PID: ${res.data.process_pid || '-'}`)
      phase.value = 1
      runStatus.value = { ...runStatus.value, ...res.data }
      startStatusPolling()
      startDetailPolling()
    } else {
      startError.value = res.error || 'Resume failed'
      addLog(`Resume failed: ${res.error || 'Unknown error'}`)
      emit('update-status', 'error')
    }
  } catch (err) {
    startError.value = err.message
    addLog(`Resume error: ${err.message}`)
    emit('update-status', 'error')
  } finally {
    isStarting.value = false
  }
}

// Open replay view
const openReplay = () => {
  router.push({ name: 'Replay', params: { simulationId: props.simulationId } })
}

// Restart simulation (force restart from scratch)
const handleRestart = async () => {
  if (!props.simulationId) return
  addLog('Restarting simulation from scratch...')
  resetAllState()
  doStartSimulation()
}

// Stop simulation
const handleStopSimulation = async () => {
  if (!props.simulationId) return

  isStopping.value = true
  addLog('Stopping simulation...')
  
  try {
    const res = await stopSimulation({ simulation_id: props.simulationId })
    
    if (res.success) {
      addLog('Simulation stopped')
      phase.value = 2
      stopPolling()
      emit('update-status', 'completed')
    } else {
      addLog(`Stop failed: ${res.error || 'Unknown error'}`)
    }
  } catch (err) {
    addLog(`Stop error: ${err.message}`)
  } finally {
    isStopping.value = false
  }
}

// Poll status
let statusTimer = null
let detailTimer = null

const startStatusPolling = () => {
  statusTimer = setInterval(fetchRunStatus, 2000)
}

const startDetailPolling = () => {
  detailTimer = setInterval(fetchRunStatusDetail, 3000)
}

const stopPolling = () => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
  if (detailTimer) {
    clearInterval(detailTimer)
    detailTimer = null
  }
}

// Track previous round for each platform, for detecting changes and logging
const prevTwitterRound = ref(0)
const prevRedditRound = ref(0)

const fetchRunStatus = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getRunStatus(props.simulationId)
    
    if (res.success && res.data) {
      const data = res.data
      
      runStatus.value = data
      
      // Detect round changes for each platform and output logs
      if (data.twitter_current_round > prevTwitterRound.value) {
        addLog(`[Plaza] R${data.twitter_current_round}/${data.total_rounds} | T:${data.twitter_simulated_hours || 0}h | A:${data.twitter_actions_count}`)
        prevTwitterRound.value = data.twitter_current_round
      }
      
      if (data.reddit_current_round > prevRedditRound.value) {
        addLog(`[Community] R${data.reddit_current_round}/${data.total_rounds} | T:${data.reddit_simulated_hours || 0}h | A:${data.reddit_actions_count}`)
        prevRedditRound.value = data.reddit_current_round
      }
      
      // Check if simulation is complete (via runner_status or platform completion status)
      const isCompleted = data.runner_status === 'completed' || data.runner_status === 'stopped'

      // Additional check: if backend hasn't updated runner_status yet but platforms report completion
      // Check via twitter_completed and reddit_completed status
      const platformsCompleted = checkPlatformsCompleted(data)
      
      if (isCompleted || platformsCompleted) {
        if (platformsCompleted && !isCompleted) {
          addLog('All platform simulations have ended')
        }
        addLog('Simulation completed')
        phase.value = 2
        stopPolling()
        emit('update-status', 'completed')
      }
    }
  } catch (err) {
    console.warn('Failed to get run status:', err)
  }
}

// Check if all enabled platforms have completed
const checkPlatformsCompleted = (data) => {
  // If no platform data, return false
  if (!data) return false

  // Check completion status for each platform
  const twitterCompleted = data.twitter_completed === true
  const redditCompleted = data.reddit_completed === true
  
  // If at least one platform completed, check if all enabled platforms are done
  // Determine if platform is enabled via actions_count (if count > 0 or was previously running)
  const twitterEnabled = (data.twitter_actions_count > 0) || data.twitter_running || twitterCompleted
  const redditEnabled = (data.reddit_actions_count > 0) || data.reddit_running || redditCompleted
  
  // If no platform is enabled, return false
  if (!twitterEnabled && !redditEnabled) return false
  
  // Check if all enabled platforms have completed
  if (twitterEnabled && !twitterCompleted) return false
  if (redditEnabled && !redditCompleted) return false
  
  return true
}

const fetchRunStatusDetail = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getRunStatusDetail(props.simulationId)
    
    if (res.success && res.data) {
      // Use all_actions to get the complete action list
      const serverActions = res.data.all_actions || []
      
      // Incrementally add new actions (deduplicated)
      let newActionsAdded = 0
      serverActions.forEach(action => {
        // Generate unique ID
        const actionId = action.id || `${action.timestamp}-${action.platform}-${action.agent_id}-${action.action_type}`
        
        if (!actionIds.value.has(actionId)) {
          actionIds.value.add(actionId)
          allActions.value.push({
            ...action,
            _uniqueId: actionId
          })
          newActionsAdded++
        }
      })
      
      // Do not auto-scroll, let users freely browse the timeline
      // New actions are appended at the bottom
    }
  } catch (err) {
    console.warn('Failed to get detailed status:', err)
  }
}

// Helpers
const getActionTypeLabel = (type) => {
  const labels = {
    'CREATE_POST': 'POST',
    'REPOST': 'REPOST',
    'LIKE_POST': 'LIKE',
    'CREATE_COMMENT': 'COMMENT',
    'LIKE_COMMENT': 'LIKE',
    'DISLIKE_POST': 'DISLIKE',
    'DISLIKE_COMMENT': 'DISLIKE',
    'MUTE': 'MUTE',
    'DO_NOTHING': 'IDLE',
    'FOLLOW': 'FOLLOW',
    'SEARCH_POSTS': 'SEARCH',
    'QUOTE_POST': 'QUOTE',
    'UPVOTE_POST': 'UPVOTE',
    'DOWNVOTE_POST': 'DOWNVOTE',
    // Polymarket
    'BUY_SHARES': 'BUY',
    'SELL_SHARES': 'SELL',
    'CREATE_MARKET': 'NEW MARKET',
    'BROWSE_MARKETS': 'BROWSE',
    'VIEW_PORTFOLIO': 'PORTFOLIO',
    'COMMENT_ON_MARKET': 'COMMENT',
  }
  return labels[type] || type || 'UNKNOWN'
}

const getActionTypeClass = (type) => {
  const classes = {
    'CREATE_POST': 'badge-post',
    'REPOST': 'badge-action',
    'LIKE_POST': 'badge-action',
    'CREATE_COMMENT': 'badge-comment',
    'LIKE_COMMENT': 'badge-action',
    'QUOTE_POST': 'badge-post',
    'FOLLOW': 'badge-meta',
    'SEARCH_POSTS': 'badge-meta',
    'UPVOTE_POST': 'badge-action',
    'DOWNVOTE_POST': 'badge-action',
    'DISLIKE_POST': 'badge-action',
    'DISLIKE_COMMENT': 'badge-action',
    'MUTE': 'badge-meta',
    'DO_NOTHING': 'badge-idle',
    // Polymarket
    'BUY_SHARES': 'badge-trade-buy',
    'SELL_SHARES': 'badge-trade-sell',
    'CREATE_MARKET': 'badge-post',
    'BROWSE_MARKETS': 'badge-meta',
    'VIEW_PORTFOLIO': 'badge-meta',
    'COMMENT_ON_MARKET': 'badge-comment',
  }
  return classes[type] || 'badge-default'
}

const formatShares = (n) => {
  if (n == null) return '?'
  return Number(n).toFixed(1)
}

const formatPrice = (n) => {
  if (n == null) return '?'
  return Number(n).toFixed(2)
}

const truncateContent = (content, maxLength = 100) => {
  if (!content) return ''
  if (content.length > maxLength) return content.substring(0, maxLength) + '...'
  return content
}

const formatActionTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

const handleNextStep = async () => {
  if (!props.simulationId) {
    addLog('Error: missing simulationId')
    return
  }

  if (isGeneratingReport.value) {
    addLog('Report generation request already sent, please wait...')
    return
  }

  isGeneratingReport.value = true

  // If simulation is still running, stop it first
  if (phase.value === 1) {
    addLog('Stopping simulation before generating report...')
    try {
      await stopSimulation({ simulation_id: props.simulationId })
      phase.value = 2
      stopPolling()
      addLog('Simulation stopped — proceeding with partial data')
      emit('update-status', 'completed')
    } catch (err) {
      addLog(`Warning: could not stop simulation (${err.message}), proceeding anyway`)
      stopPolling()
      phase.value = 2
    }
  }

  try {
    // First try to get existing report (don't regenerate)
    addLog('Checking for existing report...')
    const res = await generateReport({
      simulation_id: props.simulationId,
      force_regenerate: false
    })

    if (res.success && res.data) {
      const reportId = res.data.report_id
      if (res.data.already_generated) {
        addLog(`Found existing report: ${reportId}`)
      } else {
        addLog(`Report generation started: ${reportId}`)
      }
      router.push({ name: 'Report', params: { reportId } })
    } else {
      addLog(`Failed to start report generation: ${res.error || 'Unknown error'}`)
      isGeneratingReport.value = false
    }
  } catch (err) {
    addLog(`Report generation error: ${err.message}`)
    isGeneratingReport.value = false
  }
}

// Scroll log to bottom
const logContent = ref(null)
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

// Resume: check for existing run state before starting fresh
const tryResumeOrStart = async () => {
  if (!props.simulationId) return

  try {
    const res = await getRunStatus(props.simulationId)

    if (res.success && res.data) {
      const status = res.data.runner_status

      if (status === 'running' || status === 'starting') {
        // Simulation is still running — reconnect to it
        addLog(`Reconnecting to running simulation (round ${res.data.current_round}/${res.data.total_rounds})...`)
        runStatus.value = res.data
        phase.value = 1
        emit('update-status', 'processing')
        startStatusPolling()
        startDetailPolling()
        return
      }

      if (status === 'completed' || status === 'stopped') {
        // Already finished — show completed state
        const totalActions = (res.data.twitter_actions_count || 0) + (res.data.reddit_actions_count || 0)
        addLog(`Previous simulation found: ${status} (${totalActions} actions, round ${res.data.current_round}/${res.data.total_rounds})`)
        runStatus.value = res.data
        phase.value = 2
        emit('update-status', 'completed')
        // Load actions for display
        fetchRunStatusDetail()
        return
      }

      if (status === 'failed') {
        // Crashed — show partial data, let user decide
        const totalActions = (res.data.twitter_actions_count || 0) + (res.data.reddit_actions_count || 0)
        if (totalActions > 0) {
          addLog(`Previous simulation crashed at round ${res.data.current_round}/${res.data.total_rounds} with ${totalActions} actions`)
          addLog('You can generate a report from partial data or restart')
          runStatus.value = res.data
          phase.value = 2  // treat as completed so buttons work
          emit('update-status', 'completed')
          fetchRunStatusDetail()
          return
        }
        // No data — just start fresh
        addLog('Previous simulation failed with no data — starting fresh')
      }
    }
  } catch (err) {
    // No existing state — that's fine, start fresh
  }

  doStartSimulation()
}

const openArticleDrawer = () => {
  showArticleDrawer.value = true
  if (!articleText.value && !isGeneratingArticle.value) {
    generateArticle()
  }
}

const generateArticle = async () => {
  if (!props.simulationId || isGeneratingArticle.value) return
  isGeneratingArticle.value = true
  articleError.value = null
  try {
    const res = await generateSimulationArticle(props.simulationId)
    if (res.success && res.data?.article_text) {
      articleText.value = res.data.article_text
    } else {
      articleError.value = res.error || 'Failed to generate article.'
    }
  } catch (err) {
    articleError.value = err?.message || 'Network error generating article.'
  } finally {
    isGeneratingArticle.value = false
  }
}

const copyArticle = async () => {
  if (!articleText.value) return
  try {
    await navigator.clipboard.writeText(articleText.value)
    articleCopied.value = true
    setTimeout(() => { articleCopied.value = false }, 1800)
  } catch {
    // clipboard not available
  }
}

const downloadArticle = () => {
  if (!articleText.value) return
  const blob = new Blob([articleText.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `simulation-${props.simulationId || 'article'}.md`
  a.click()
  URL.revokeObjectURL(url)
}

const renderArticleMarkdown = (content) => {
  if (!content) return ''
  let html = content.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  html = html.replace(/^#### (.+)$/gm, '<h5 class="md-h5">$1</h5>')
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  html = html.replace(/^> (.+)$/gm, '<blockquote class="md-quote">$1</blockquote>')
  html = html.replace(/^(\s*)- (.+)$/gm, (match, indent, text) => {
    const level = Math.floor(indent.length / 2)
    return `<li class="md-li" data-level="${level}">${text}</li>`
  })
  html = html.replace(/(<li class="md-li"[^>]*>.*?<\/li>\s*)+/g, '<ul class="md-ul">$&</ul>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  html = html.replace(/\n\n/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br>')
  html = '<p class="md-p">' + html + '</p>'
  html = html.replace(/<p class="md-p"><\/p>/g, '')
  html = html.replace(/<p class="md-p">(<h[2-5])/g, '$1')
  html = html.replace(/(<\/h[2-5]>)<\/p>/g, '$1')
  html = html.replace(/<p class="md-p">(<ul|<blockquote|<pre|<hr)/g, '$1')
  html = html.replace(/(<\/ul>|<\/blockquote>|<\/pre>)<\/p>/g, '$1')
  html = html.replace(/<br>\s*(<ul|<blockquote)/g, '$1')
  html = html.replace(/(<\/ul>|<\/blockquote>)\s*<br>/g, '$1')
  return html
}

onMounted(() => {
  addLog('Step3 Simulation Run initialized')
  tryResumeOrStart()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.simulation-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #FAFAFA;
  font-family: var(--font-mono, 'Space Mono', monospace);
  overflow: hidden;
}

/* --- Control Bar (platforms only) --- */
.control-bar {
  background: #FAFAFA;
  padding: 6px 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 2px solid rgba(10,10,10,0.08);
  z-index: 10;
}

/* --- Actions Bar (buttons) --- */
.actions-bar {
  background: var(--color-gray, #F5F5F5);
  padding: 6px 12px;
  display: flex;
  align-items: stretch;
  justify-content: center;
  gap: 6px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

.events-summary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--color-gray, #F5F5F5);
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.4);
  border-bottom: 2px solid rgba(10,10,10,0.08);
}

.events-label {
  color: rgba(10,10,10,0.4);
}

.events-total {
  color: #FF6B1A;
  font-weight: 700;
  font-size: 13px;
}

.events-divider {
  width: 1px;
  height: 14px;
  background: rgba(10,10,10,0.12);
  margin: 0 4px;
}

.events-platform {
  color: rgba(10,10,10,0.4);
}

.events-count {
  color: #0A0A0A;
  font-weight: 700;
}

.events-slash {
  color: rgba(10,10,10,0.15);
}

.status-group {
  display: flex;
  flex-direction: row;
  gap: 6px;
}

/* Platform Status Rows */
.platform-status {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 6px 10px;
  background: #FAFAFA;
  border: 2px solid rgba(10,10,10,0.08);
  opacity: 0.7;
  transition: all 0.3s;
  position: relative;
}

.platform-left {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 110px;
}

.platform-status {
  cursor: pointer;
  user-select: none;
}

.platform-status:hover {
  background: var(--color-gray, #F5F5F5);
}

.platform-status.selected {
  opacity: 1;
  border-color: #FF6B1A;
  background: #FAFAFA;
}

.platform-status.dimmed {
  opacity: 0.4;
}

.platform-status.active {
  opacity: 1;
  border-color: #FF6B1A;
  background: #FAFAFA;
}

.platform-status.dimmed.active {
  opacity: 0.4;
}

.platform-status.completed {
  opacity: 1;
  border-color: #43C165;
  background: rgba(67,193,101,0.06);
}

.platform-actions-list {
  display: none;
}

.action-tag {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 3px;
  padding: 2px 6px;
  border: 1px solid rgba(10,10,10,0.12);
  color: rgba(10,10,10,0.5);
  text-transform: uppercase;
}

.platform-status.active .action-tag {
  border-color: rgba(10,10,10,0.2);
  color: rgba(10,10,10,0.7);
}

.status-badge.done {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 8px;
  color: #FAFAFA;
  background: #43C165;
  padding: 1px 6px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
}

/* Actions Tooltip */
.actions-tooltip {
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-top: 8px;
  padding: 10px 14px;
  background: #0A0A0A;
  color: #FAFAFA;
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s ease;
  z-index: 100;
  min-width: 180px;
  pointer-events: none;
}

.actions-tooltip::before {
  content: '';
  position: absolute;
  top: -6px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-bottom: 6px solid #0A0A0A;
}

.platform-status:hover .actions-tooltip {
  opacity: 1;
  visibility: visible;
}

.tooltip-title {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 11px;
  font-weight: 600;
  color: rgba(10,10,10,0.4);
  text-transform: uppercase;
  letter-spacing: 3px;
  margin-bottom: 8px;
}

.tooltip-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tooltip-action {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 10px;
  font-weight: 600;
  padding: 3px 8px;
  background: rgba(255, 255, 255, 0.15);
  color: #FAFAFA;
  letter-spacing: 3px;
  text-transform: uppercase;
}

.platform-header {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 1px;
}

.platform-name {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 9px;
  font-weight: 700;
  color: #0A0A0A;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.platform-status.twitter .platform-icon { color: #0A0A0A; }

.platform-icon-img {
  width: 14px;
  height: 14px;
  object-fit: contain;
}

.platform-stats {
  display: flex;
  flex-direction: row;
  gap: 8px;
}

.stat {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.stat-label {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 7px;
  color: rgba(10,10,10,0.4);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
}

.stat-value {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 10px;
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

.stat-total, .stat-unit {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 8px;
  color: rgba(10,10,10,0.4);
  font-weight: 400;
}

.status-badge {
  margin-left: auto;
  color: #43C165;
  display: flex;
  align-items: center;
}

/* Action Button */
/* kept for backwards compat */
.action-controls {
  display: flex;
  gap: 6px;
  align-items: center;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 5px 12px;
  min-width: 100px;
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 10px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  text-transform: uppercase;
  letter-spacing: 3px;
  white-space: nowrap;
}

.action-btn.primary {
  background: #0A0A0A;
  color: #FAFAFA;
}

.action-btn.primary:hover:not(:disabled) {
  background: rgba(10,10,10,0.7);
}

.action-btn.secondary {
  background: #FAFAFA;
  color: rgba(10,10,10,0.7);
  border: 2px solid rgba(10,10,10,0.12);
}

.action-btn.secondary:hover:not(:disabled) {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.2);
}

.action-btn.danger {
  background: #FF4444;
  color: #FAFAFA;
}

.action-btn.danger:hover:not(:disabled) {
  background: #E03C3C;
}

.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* --- Main Content Area --- */
.main-content-area {
  flex: 1;
  overflow-y: auto;
  position: relative;
  background: #FAFAFA;
}

/* --- Influence Leaderboard overlay --- */
.influence-overlay {
  flex: 1;
  overflow: hidden;
  background: var(--background);
  border-top: 1px solid rgba(10,10,10,0.06);
}

/* Highlight the active influence toggle button */
.action-btn.active {
  background: var(--color-orange);
  color: var(--color-white);
  border-color: var(--color-orange);
}

.agent-info.clickable {
  cursor: pointer;
}

.agent-info.clickable:hover .agent-name {
  text-decoration: underline;
}

.agent-filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  margin: 0 16px 8px;
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.12);
}

.filter-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-name {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 12px;
  font-weight: 600;
  color: rgba(10,10,10,0.7);
}

.filter-count {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
}

.filter-clear {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  padding: 3px 10px;
  border: 2px solid rgba(10,10,10,0.12);
  background: #FAFAFA;
  color: rgba(10,10,10,0.5);
  cursor: pointer;
}

.filter-clear:hover {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.2);
}

.scroll-bottom-btn {
  position: sticky;
  top: 8px;
  float: right;
  margin-right: 12px;
  z-index: 20;
  width: 28px;
  height: 28px;
  border: 2px solid rgba(10,10,10,0.12);
  background: #FAFAFA;
  color: rgba(10,10,10,0.7);
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.scroll-bottom-btn:hover {
  background: var(--color-gray, #F5F5F5);
  border-color: rgba(10,10,10,0.2);
}

/* Timeline Header */
.timeline-header {
  position: sticky;
  top: 0;
  background: rgba(250, 250, 250, 0.9);
  backdrop-filter: blur(8px);
  padding: 12px 24px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
  z-index: 5;
  display: flex;
  justify-content: center;
}

.timeline-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 11px;
  color: rgba(10,10,10,0.5);
  background: var(--color-gray, #F5F5F5);
  padding: 4px 12px;
  border: 2px solid rgba(10,10,10,0.08);
}

.total-count {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-weight: 600;
  color: rgba(10,10,10,0.7);
  text-transform: uppercase;
  letter-spacing: 3px;
}

.platform-breakdown {
  display: flex;
  align-items: center;
  gap: 8px;
}

.breakdown-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-mono, 'Space Mono', monospace);
}

.breakdown-divider { color: rgba(10,10,10,0.2); }
.breakdown-item.twitter, .filter-name.twitter { color: #0A0A0A; }
.breakdown-item.reddit, .filter-name.reddit { color: #FF6B1A; }
.breakdown-item.polymarket, .filter-name.polymarket { color: #FF6B1A; }

/* --- Timeline Feed --- */
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
  justify-content: center;
  margin-bottom: 34px;
  position: relative;
  width: 100%;
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
.timeline-item.polymarket .marker-dot { background: #FF6B1A; }
.timeline-item.twitter .timeline-marker { border-color: #0A0A0A; }
.timeline-item.reddit .timeline-marker { border-color: #FF6B1A; }
.timeline-item.polymarket .timeline-marker { border-color: #FF6B1A; }

/* Card Layout */
.timeline-card {
  width: calc(100% - 48px);
  background: #FAFAFA;
  padding: 16px 20px;
  border: 2px solid rgba(10,10,10,0.08);
  position: relative;
  transition: all 0.2s;
}

.timeline-card:hover {
  border-color: #FF6B1A;
}

/* All platforms flow in single column */
.timeline-item.twitter,
.timeline-item.reddit,
.timeline-item.polymarket {
  justify-content: flex-start;
}
.timeline-item .timeline-card {
  margin-left: 32px;
  max-width: 100%;
}

.timeline-item.twitter .timeline-card { border-left: 2px solid #0A0A0A; }
.timeline-item.reddit .timeline-card { border-left: 2px solid #FF6B1A; }
.timeline-item.polymarket .timeline-card { border-left: 2px solid #FF6B1A; }

/* Card Content Styles */
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
  min-height: 24px;
  flex-shrink: 0;
  background: #0A0A0A;
  color: #FAFAFA;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.agent-name {
  font-family: var(--font-mono, 'Space Mono', monospace);
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
  flex-shrink: 0;
}

.platform-indicator.twitter {
  background: #0A0A0A;
  color: #FAFAFA;
}

.platform-indicator.reddit,
.platform-indicator.polymarket {
  background: none;
}

.platform-logo {
  width: 20px;
  height: 20px;
  object-fit: contain;
}

.action-badge {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 9px;
  padding: 2px 6px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  border: 1px solid transparent;
}

/* Monochromatic Badges */
.badge-post { background: rgba(10,10,10,0.06); color: rgba(10,10,10,0.7); border-color: rgba(10,10,10,0.12); }
.badge-comment { background: rgba(10,10,10,0.06); color: rgba(10,10,10,0.5); border-color: rgba(10,10,10,0.12); }
.badge-action { background: #FAFAFA; color: rgba(10,10,10,0.5); border: 1px solid rgba(10,10,10,0.12); }
.badge-meta { background: #FAFAFA; color: rgba(10,10,10,0.4); border: 1px dashed rgba(10,10,10,0.2); }
.badge-idle { opacity: 0.5; }
.badge-trade-buy { background: rgba(67,193,101,0.1); color: #43C165; border-color: rgba(67,193,101,0.2); }
.badge-trade-sell { background: rgba(255,68,68,0.1); color: #FF4444; border-color: rgba(255,68,68,0.2); }

/* Polymarket trade cards */
.trade-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 12px;
  flex-wrap: wrap;
}

.trade-direction {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  letter-spacing: 3px;
}
.trade-direction.buy { background: rgba(67,193,101,0.1); color: #43C165; }
.trade-direction.sell { background: rgba(255,68,68,0.1); color: #FF4444; }

.trade-detail { color: rgba(10,10,10,0.7); }
.trade-cost { color: rgba(10,10,10,0.4); font-size: 11px; }
.trade-total { color: rgba(10,10,10,0.7); font-weight: 600; font-size: 11px; }

.market-question {
  font-size: 12px;
  color: rgba(10,10,10,0.7);
  font-style: italic;
}

.market-ref {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 10px;
  color: rgba(10,10,10,0.4);
  margin-top: 2px;
}

.content-text {
  font-size: 13px;
  line-height: 1.6;
  color: rgba(10,10,10,0.7);
  margin-bottom: 11px;
}

.content-text.main-text {
  font-size: 14px;
  color: #0A0A0A;
}

/* Info Blocks (Quote, Repost, etc) */
.quoted-block, .repost-content {
  background: var(--color-gray, #F5F5F5);
  border: 2px solid rgba(10,10,10,0.08);
  padding: 11px 12px;
  margin-top: 8px;
  font-size: 12px;
  color: rgba(10,10,10,0.5);
}

.quote-header, .repost-info, .like-info, .search-info, .follow-info, .vote-info, .idle-info, .comment-context {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 11px;
  color: rgba(10,10,10,0.5);
}

.icon-small {
  color: rgba(10,10,10,0.4);
}
.icon-small.filled {
  color: rgba(10,10,10,0.4);
}

.search-query {
  font-family: var(--font-mono, 'Space Mono', monospace);
  background: rgba(10,10,10,0.06);
  padding: 0 4px;
}

.card-footer {
  margin-top: 11px;
  display: flex;
  justify-content: flex-end;
  font-size: 10px;
  color: rgba(10,10,10,0.2);
  font-family: var(--font-mono, 'Space Mono', monospace);
}

/* Waiting State */
.waiting-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: rgba(10,10,10,0.2);
  font-family: var(--font-mono, 'Space Mono', monospace);
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
  0% { transform: scale(0.8); opacity: 1; border-color: #FF6B1A; }
  100% { transform: scale(2.5); opacity: 0; border-color: rgba(255,107,26,0.1); }
}

/* Animation */
.timeline-item-enter-active,
.timeline-item-leave-active {
  transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
}

.timeline-item-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.timeline-item-leave-to {
  opacity: 0;
}

/* Logs */
.system-logs {
  background: #0A0A0A;
  color: rgba(250,250,250,0.7);
  padding: 16px;
  font-family: var(--font-mono, 'Space Mono', monospace);
  border-top: 2px solid rgba(10,10,10,0.12);
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid rgba(250,250,250,0.15);
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 11px;
  color: rgba(250,250,250,0.4);
  cursor: pointer;
  user-select: none;
  text-transform: uppercase;
  letter-spacing: 3px;
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

.log-id.copyable {
  cursor: pointer;
  user-select: none;
  transition: color 0.15s;
}

.log-id.copyable:hover {
  color: #FAFAFA;
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
.log-content::-webkit-scrollbar-thumb { background: rgba(250,250,250,0.2); }

.log-line {
  font-size: 11px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time { color: rgba(250,250,250,0.35); min-width: 75px; }
.log-msg { color: rgba(250,250,250,0.6); word-break: break-all; }
.mono { font-family: var(--font-mono, 'Space Mono', monospace); }

/* Loading spinner for button */
.loading-spinner-small {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #FF6B1A;
  animation: spin 0.8s linear infinite;
  margin-right: 6px;
}

/* ---- Article Drawer ---- */
.article-drawer-overlay {
  position: absolute;
  inset: 0;
  background: rgba(10,10,10,0.45);
  z-index: 200;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.article-drawer {
  width: 100%;
  max-width: 780px;
  max-height: 75vh;
  background: #FAFAFA;
  border-top: 2px solid rgba(10,10,10,0.1);
  border-left: 2px solid rgba(10,10,10,0.08);
  border-right: 2px solid rgba(10,10,10,0.08);
  border-radius: 8px 8px 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.article-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(10,10,10,0.08);
  background: #F5F5F5;
  flex-shrink: 0;
}

.article-drawer-title {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #0A0A0A;
}

.article-drawer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.article-action-btn {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 4px 10px;
  background: transparent;
  border: 1px solid rgba(10,10,10,0.2);
  border-radius: 3px;
  cursor: pointer;
  color: #0A0A0A;
  transition: background 0.15s, border-color 0.15s;
}

.article-action-btn:hover:not(:disabled) {
  background: #0A0A0A;
  color: #FAFAFA;
  border-color: #0A0A0A;
}

.article-action-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.article-close-btn {
  font-size: 14px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: rgba(10,10,10,0.4);
  line-height: 1;
  padding: 4px 6px;
  transition: color 0.15s;
}

.article-close-btn:hover { color: #0A0A0A; }

.article-drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.article-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 40px 0;
  color: rgba(10,10,10,0.45);
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 12px;
}

.article-loading-spinner {
  width: 28px;
  height: 28px;
  border: 2px solid rgba(10,10,10,0.12);
  border-top-color: #FF6B1A;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.article-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 32px 0;
}

.article-error-msg {
  font-family: var(--font-mono, 'Space Mono', monospace);
  font-size: 12px;
  color: #e53e3e;
  text-align: center;
}

.article-content {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.7;
  color: #0A0A0A;
}

/* Transition for drawer */
.article-drawer-enter-active, .article-drawer-leave-active {
  transition: opacity 0.2s ease;
}
.article-drawer-enter-active .article-drawer,
.article-drawer-leave-active .article-drawer {
  transition: transform 0.25s ease;
}
.article-drawer-enter-from, .article-drawer-leave-to { opacity: 0; }
.article-drawer-enter-from .article-drawer,
.article-drawer-leave-to .article-drawer { transform: translateY(100%); }

/* Markdown styles for article content */
.article-content :deep(.md-h2) { font-size: 1.25em; font-weight: 700; margin: 1.2em 0 0.5em; }
.article-content :deep(.md-h3) { font-size: 1.1em; font-weight: 700; margin: 1em 0 0.4em; }
.article-content :deep(.md-p) { margin: 0.6em 0; }
.article-content :deep(.md-ul) { margin: 0.5em 0 0.5em 1.2em; padding: 0; }
.article-content :deep(.md-li) { margin: 0.3em 0; list-style-type: disc; }
.article-content :deep(.md-hr) { border: none; border-top: 1px solid rgba(10,10,10,0.1); margin: 1em 0; }
.article-content :deep(.md-quote) { border-left: 3px solid #FF6B1A; margin: 0.8em 0; padding: 4px 12px; color: rgba(10,10,10,0.6); font-style: italic; }
</style>