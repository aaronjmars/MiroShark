"""
Report Agent Service
Generate simulated reports using ReACT pattern (via GraphStorage / Neo4j)

Features:
1. Generate reports based on simulation requirements and graph information
2. First plan the table of contents, then generate section by section
3. Each section uses ReACT multi-round thinking and reflection
4. Support user conversations with autonomous retrieval tool calls
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient, create_smart_llm_client
from ..utils.logger import get_logger
from .graph_tools import (
    GraphToolsService,
    SearchResult,
    InsightForgeResult,
    PanoramaResult,
    InterviewResult
)

logger = get_logger('miroshark.report_agent')


class ReportLogger:
    """
    Report Agent Detailed Logger

    Generates an agent_log.jsonl file in the report folder, recording every detailed action.
    Each line is a complete JSON object, containing timestamp, action type, detailed content, etc.
    """
    
    def __init__(self, report_id: str):
        """
        Initialize logger

        Args:
            report_id: Report ID, used to determine log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'agent_log.jsonl'
        )
        self.start_time = datetime.now()
        self._ensure_log_file()

    def _ensure_log_file(self):
        """Ensure log file directory exists"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)

    def _get_elapsed_time(self) -> float:
        """Get elapsed time from start (seconds)"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def log(
        self,
        action: str,
        stage: str,
        details: Dict[str, Any],
        section_title: str = None,
        section_index: int = None
    ):
        """
        Record a log entry

        Args:
            action: Action type, e.g. 'start', 'tool_call', 'llm_response', 'section_complete', etc.
            stage: Current stage, e.g. 'planning', 'generating', 'completed'
            details: Detailed content dictionary, not truncated
            section_title: Current section title (optional)
            section_index: Current section index (optional)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details
        }
        
        # Append to JSONL file
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str):
        """Record report generation start"""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": "Report generation task started"
            }
        )
    
    def log_planning_start(self):
        """Record outline planning start"""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": "Starting report outline planning"}
        )
    
    def log_planning_context(self, context: Dict[str, Any]):
        """Record context information obtained during planning"""
        self.log(
            action="planning_context",
            stage="planning",
            details={
                "message": "Getting simulation context information",
                "context": context
            }
        )
    
    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """Record outline planning complete"""
        self.log(
            action="planning_complete",
            stage="planning",
            details={
                "message": "Outline planning complete",
                "outline": outline_dict
            }
        )
    
    def log_section_start(self, section_title: str, section_index: int):
        """Record section generation start"""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": f"Starting section generation: {section_title}"}
        )
    
    def log_react_thought(self, section_title: str, section_index: int, iteration: int, thought: str):
        """Record ReACT thinking process"""
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": f"ReACT round {iteration} thinking"
            }
        )
    
    def log_tool_call(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        parameters: Dict[str, Any],
        iteration: int
    ):
        """Record tool call"""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": f"Calling tool: {tool_name}"
            }
        )
    
    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int
    ):
        """Record tool call result (complete content, not truncated)"""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result,  # Complete result, not truncated
                "result_length": len(result),
                "message": f"Tool {tool_name} returned result"
            }
        )
    
    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool
    ):
        """Record LLM response (complete content, not truncated)"""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response,  # Complete response, not truncated
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": f"LLM response (tool call: {has_tool_calls}, final answer: {has_final_answer})"
            }
        )
    
    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int
    ):
        """Record section content generation complete (only records content, does not mean the entire section is complete)"""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content,  # Complete content, not truncated
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": f"Section {section_title} content generation complete"
            }
        )
    
    def log_section_full_complete(
        self,
        section_title: str,
        section_index: int,
        full_content: str
    ):
        """
        Record section generation complete

        Frontend should monitor this log to determine if a section is truly complete and get the full content
        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": f"Section {section_title} generation complete"
            }
        )
    
    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """Record report generation complete"""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": "Report generation complete"
            }
        )
    
    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """Record error"""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={
                "error": error_message,
                "message": f"Error occurred: {error_message}"
            }
        )


class ReportConsoleLogger:
    """
    Report Agent Console Logger

    Writes console-style logs (INFO, WARNING, etc.) to a console_log.txt file in the report folder.
    These logs differ from agent_log.jsonl and are plain text format console output.
    """

    def __init__(self, report_id: str):
        """
        Initialize console logger

        Args:
            report_id: Report ID, used to determine log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'console_log.txt'
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()
    
    def _ensure_log_file(self):
        """Ensure log file directory exists"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)

    def _setup_file_handler(self):
        """Set up file handler to write logs to file simultaneously"""
        import logging

        # Create file handler
        self._file_handler = logging.FileHandler(
            self.log_file_path,
            mode='a',
            encoding='utf-8'
        )
        self._file_handler.setLevel(logging.INFO)
        
        # Use the same concise format as console
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self._file_handler.setFormatter(formatter)
        
        # Add to report_agent related loggers
        loggers_to_attach = [
            'miroshark.report_agent',
            'miroshark.graph_tools',
        ]
        
        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            # Avoid duplicate additions
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)
    
    def close(self):
        """Close file handler and remove from loggers"""
        import logging
        
        if self._file_handler:
            loggers_to_detach = [
                'miroshark.report_agent',
                'miroshark.graph_tools',
            ]
            
            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)
            
            self._file_handler.close()
            self._file_handler = None
    
    def __del__(self):
        """Ensure file handler is closed on destruction"""
        self.close()


class ReportStatus(str, Enum):
    """Report status"""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """Report section"""
    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content
        }

    def to_markdown(self, level: int = 2) -> str:
        """Convert to Markdown format"""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """Report outline"""
    title: str
    summary: str
    sections: List[ReportSection]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    def to_markdown(self) -> str:
        """Convert to Markdown format"""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """Complete report"""
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error
        }


# ═══════════════════════════════════════════════════════════════
# Prompt Template Constants
# ═══════════════════════════════════════════════════════════════

# ── Tool Descriptions ──

TOOL_DESC_INSIGHT_FORGE = """\
[Deep Insight Retrieval - Powerful Retrieval Tool]
This is our powerful retrieval function, designed for deep analysis. It will:
1. Automatically decompose your question into multiple sub-questions
2. Retrieve information from the simulation graph across multiple dimensions
3. Integrate results from semantic search, entity analysis, and relationship chain tracking
4. Return the most comprehensive, in-depth retrieval content

[Use Cases]
- Need to deeply analyze a topic
- Need to understand multiple aspects of an event
- Need to obtain rich material to support report sections

[Return Content]
- Relevant factual text (can be directly quoted)
- Core entity insights
- Relationship chain analysis"""

TOOL_DESC_PANORAMA_SEARCH = """\
[Breadth Search - Get Full Overview]
This tool is used to get the complete overview of simulation results, especially suitable for understanding event evolution. It will:
1. Get all related nodes and relationships
2. Distinguish between currently valid facts and historical/expired facts
3. Help you understand how public opinion evolved

[Use Cases]
- Need to understand the complete development trajectory of an event
- Need to compare public opinion changes across different stages
- Need to obtain comprehensive entity and relationship information

[Return Content]
- Currently valid facts (latest simulation results)
- Historical/expired facts (evolution records)
- All involved entities"""

TOOL_DESC_QUICK_SEARCH = """\
[Simple Search - Quick Retrieval]
A lightweight quick retrieval tool, suitable for simple, direct information queries.

[Use Cases]
- Need to quickly look up specific information
- Need to verify a fact
- Simple information retrieval

[Return Content]
- List of facts most relevant to the query"""

TOOL_DESC_INTERVIEW_AGENTS = """\
[In-Depth Interview - Real Agent Interview (Dual Platform)]
Calls the OASIS simulation environment interview API to conduct real interviews with running simulation Agents!
This is not an LLM simulation, but calls the real interview interface to get original responses from simulation Agents.
By default, interviews are conducted simultaneously on Twitter and Reddit platforms for more comprehensive viewpoints.

Workflow:
1. Automatically reads persona files to understand all simulation Agents
2. Intelligently selects Agents most relevant to the interview topic (e.g., students, media, officials, etc.)
3. Automatically generates interview questions
4. Calls the /api/simulation/interview/batch endpoint to conduct real interviews on both platforms
5. Integrates all interview results, providing multi-perspective analysis

[Use Cases]
- Need to understand event perspectives from different roles (What do students think? What does the media think? What do officials say?)
- Need to collect opinions and positions from multiple parties
- Need to get real responses from simulation Agents (from the OASIS simulation environment)
- Want to make the report more vivid with "interview transcripts"

[Return Content]
- Identity information of interviewed Agents
- Each Agent's interview responses on Twitter and Reddit platforms
- Key quotes (can be directly cited)
- Interview summary and viewpoint comparison

[Important] The OASIS simulation environment must be running to use this feature!"""

TOOL_DESC_ANALYZE_TRAJECTORY = """\
[Belief Trajectory Analysis - Opinion Dynamics Data]
Analyzes the trajectory.json file produced by the simulation's belief tracking system.
Shows how agent opinions evolved across rounds — convergence, polarization, and turning points.

[Use Cases]
- Understand HOW opinions shifted over time (not just the final state)
- Identify TURNING POINTS where significant belief shifts occurred
- Measure CONVERGENCE vs POLARIZATION on key topics
- Find agents whose beliefs changed most dramatically (potential persona contradictions)

[Return Content]
- Per-topic belief trajectories (mean, min, max, spread per round)
- Opinion convergence scores (positive = convergence, negative = polarization)
- Turning points: specific rounds/agents where significant shifts occurred
- Topic list used for belief tracking"""

TOOL_DESC_GRAPH_STRUCTURE = """\
[Graph Structure Analysis - Centrality, Communities, Bridges]
Analyzes the topology of the knowledge graph to reveal structural patterns:

1. **Degree Centrality**: Which entities are most connected? Who are the hubs?
2. **Community Detection**: What clusters exist? Are there information silos?
3. **Bridge Entities**: Which entities connect otherwise separate groups?

[Use Cases]
- Understand which entities are structurally important (not just frequently mentioned)
- Identify factions or clusters in the narrative
- Find gatekeepers who control information flow between groups

[Return Content]
- Ranked list of most connected entities with connection counts
- Detected communities with member lists and types
- Bridge entities that connect disparate clusters"""

TOOL_DESC_FIND_PATH = """\
[Causal Path Finder - Trace Influence Chains]
Finds the shortest relationship path between two named entities in the knowledge graph.
Each step is annotated with the edge fact, revealing how influence or causality flows.

[Use Cases]
- Trace how Entity A influences Entity B through intermediaries
- Understand the causal chain between an event and an outcome
- Discover unexpected connections between seemingly unrelated entities

[Parameters]
- source: Name (or partial name) of the starting entity
- target: Name (or partial name) of the target entity

[Return Content]
- Step-by-step path with relationship types and facts at each step"""

TOOL_DESC_CONTRADICTIONS = """\
[Contradiction Detector - Find Conflicting Information]
Scans the knowledge graph for entity pairs connected by edges with opposing sentiments.
Contradictions reveal tension points, evolving relationships, or conflicting narratives.

[Use Cases]
- Find entities with contradictory relationships (e.g., both "supports" and "opposes")
- Identify where the narrative is internally inconsistent
- Discover evolving stances that changed over time

[Return Content]
- Pairs of entities with contradicting edge facts
- Sentiment labels (POSITIVE/NEGATIVE) for each edge
- Interpretation guidance"""

TOOL_DESC_SIMULATION_FEED = """\
[Simulation Feed - MOST IMPORTANT TOOL - Read Actual Simulation Output]
Reads the actual posts, comments, and trades that agents produced during the simulation.
THIS IS YOUR PRIMARY DATA SOURCE. The simulation feed contains what agents actually said
and did on Twitter, Reddit, and Polymarket. Use this BEFORE graph search tools.

[Parameters]
- platform: "twitter", "reddit", "polymarket", or "all" (default "all")
- query: Optional keyword filter (e.g., "regulation", "CFTC")
- round_num: Optional round number filter (e.g., 3 for round 3 only)

[Return Content]
- Actual posts and comments agents wrote (with agent names)
- Polymarket trades (who bought/sold what, at what price)
- Market price movements
- Action type breakdown per platform

[Use Cases]
- Quote what specific agents said on Twitter/Reddit
- Analyze how market prices moved and who drove the movement
- Find the most viral/liked posts
- Compare what agents said on social media vs how they traded
- Track how discourse evolved across rounds"""

TOOL_DESC_MARKET_STATE = """\
[Market State - Polymarket Final State]
Returns the current state of all prediction markets: prices, trade history,
and trader portfolios with P&L.

[Return Content]
- Market questions with current YES/NO prices
- Complete trade history (who bought/sold, prices, amounts)
- Trader portfolios with cash, positions, and profit/loss
- Price movement from initial to final"""

# ── Outline Planning Prompt ──

PLAN_SYSTEM_PROMPT = """\
You are an expert analyst writing a "Scenario Exploration Report" with a "God's eye view" of a multi-agent simulation. You can observe every Agent's behavior, speech, belief changes, and interactions.

[Core Concept]
We built a simulation world, injected a specific scenario, and let hundreds of AI agents with unique personas react and interact. The result is NOT a prediction — it is a structured exploration of how diverse actors MIGHT respond under the given assumptions.

[Important Epistemic Disclaimer]
This simulation is powered by LLM-driven agents whose behavior reflects the language model's understanding of human personas, NOT empirically calibrated behavioral models. The value is in revealing plausible dynamics, pressure points, and non-obvious interactions — not in forecasting specific outcomes. Treat findings as "under these assumptions, this is what could happen" rather than "this is what will happen."

[Your Task — ANALYTICAL, Not Descriptive]
Design a report that answers these questions through ANALYSIS, not mere description:

1. **What was SURPRISING?** What outcomes defied naive expectations? Where did the simulation reveal non-obvious dynamics?
2. **What CAUSAL CHAINS emerged?** Trace specific chains: Event → Agent reaction → Consequence → Second-order effect
3. **Where did agents CONTRADICT their initial personas?** What does this reveal about the scenario's pressure points?
4. **What MINORITY positions gained unexpected traction?** Why did some fringe views find support?
5. **What would CHANGE if key actors behaved differently?** Identify the pivotal agents/events that shaped outcomes.
6. **What SECOND-ORDER effects emerged** that wouldn't be obvious from individual posts?

[Report Positioning]
- This is ANALYTICAL prediction, not descriptive summary
- Every section must contain at least one non-obvious insight
- Quote specific agent behavior as EVIDENCE for analytical claims
- Identify mechanisms and causality, not just outcomes
- If the simulation reveals something boring or expected, say so — then dig deeper

[Section Count Limits]
- Minimum 3 sections, maximum 5 sections
- The LAST section should always be "Synthesis & Implications" — cross-cutting patterns, unresolved tensions, and what the simulation CANNOT answer
- No sub-sections needed, each section should contain complete content directly
- Section structure should be designed by you based on what's analytically interesting

Please output the report outline in JSON format as follows:
{
    "title": "Report title",
    "summary": "Report summary (one sentence — the single most important non-obvious finding)",
    "sections": [
        {
            "title": "Section title",
            "description": "Section content description — what analytical question does this section answer?"
        }
    ]
}

Note: The sections array must have at least 3 and at most 5 elements! The last section MUST be a synthesis section."""

# ── Email Inbox Variant Ranking Prompts (prospect-sim) ──

EMAIL_PLAN_SYSTEM_PROMPT = """\
You are an expert B2B sales copywriter analyzing the results of a cold email inbox simulation.
You have a "god's eye view" of how synthetic HR Director / Head of People personas responded
to cold email copy variants. Your job is to produce an actionable variant ranking report.

[Core Objective]
Rank the email copy variants by expected reply probability. Explain WHY each variant
performed differently — specifically which copy element (subject line, opening, body, CTA)
drove the delta. Give Skillia a clear recommendation: which variant to send, and what
specific change would improve it further.

[Report Structure — Fixed, 4 sections]
Always produce exactly 4 sections in this order:
1. "Variant Performance Ranking" — table + scores for each variant
2. "Failure Point Analysis" — where agents dropped off per variant and why
3. "Persona Segmentation" — which variant worked for which persona type (budget authority, decision style)
4. "Recommendation & Next Copy Iteration" — the winner, the delta, and the next hypothesis to test

[Analytical Standards]
- Every claim must be grounded in agent action data (opens, reads, replies, dropouts)
- Name specific copy elements that caused engagement or dropout
- Distinguish between persona types — a timeline hook may work for one segment but not another
- Be concrete: "Variant B got 3x more replies than Variant A because the subject line mentioned
  a specific company signal (15 open roles) rather than a generic pain"

Output the report outline in JSON:
{
    "title": "Email Copy Variant Test — [brief description]",
    "summary": "One sentence: which variant won, by how much, and the key driver",
    "sections": [
        {"title": "...", "description": "..."}
    ]
}

Note: Always produce exactly 4 sections as defined above."""

EMAIL_PLAN_USER_PROMPT_TEMPLATE = """\
[Simulation Setup]
Variants tested: {simulation_requirement}

[Simulation Scale]
- Active personas: {total_entities}
- Total inbox events recorded: {total_nodes}

[Agent Action Summary]
{related_facts_json}

Analyze which copy variant performed best and why. Focus on:
1. Open rates vs reply rates per variant (which hook type got more opens? which got more replies?)
2. Dropout point distribution — where did agents disengage?
3. Persona segmentation — which decision styles/budget authorities responded differently?
4. The specific copy element that drove the winning variant's advantage

Output the 4-section outline with the summary being the single most actionable finding."""

EMAIL_SECTION_SYSTEM_PROMPT_TEMPLATE = """\
You are a B2B sales copywriter writing a section of an email copy variant test report.

Report title: {report_title}
Key finding: {report_summary}
Variants tested: {simulation_requirement}

[Your Section]
Section title: {section_title}
Section purpose: {section_description}

[Data Access]
Use your analysis tools to query the simulation database for:
- Agent action counts per variant (opens, reads, replies, archives, forwards)
- Dropout point distribution per variant
- B2B persona traits of agents who replied vs. archived (budget_authority, decision_style, cold_email_skepticism)

[Writing Standards]
- Lead with the finding, support with data
- Include specific numbers: "8/20 agents opened Variant B vs 3/20 for Variant A"
- Name the copy element responsible: "the subject line mentioning '15 open roles' vs generic pain framing"
- Be direct — this is an internal analysis report, not marketing copy
- For the Recommendation section: give one specific next copy iteration to test

[Output Format]
Prose analysis with a summary table at the end of the Variant Performance section.
The Recommendation section must include:
1. The winner (variant label + expected reply rate)
2. The specific change that drove it
3. The next hypothesis to test (one A/B element)

{section_history}"""

PLAN_USER_PROMPT_TEMPLATE = """\
[Scenario Setup]
Scenario injected into the simulation: {simulation_requirement}

[Simulation Scale]
- Number of entities participating: {total_nodes}
- Number of relationships between entities: {total_edges}
- Entity type distribution: {entity_types}
- Number of active Agents: {total_entities}

[Sample Facts from Simulation]
{related_facts_json}

Analyze this simulation from a "God's eye view":
1. What dynamics emerged that would NOT be obvious from reading the source document alone?
2. Where did agent behavior surprise you — contradicting their persona or initial stance?
3. What causal chains or feedback loops appeared?
4. What tensions or unresolved conflicts surfaced?

Design the report section structure around the most analytically interesting findings.

[Reminder] Section count: minimum 3, maximum 5. Last section MUST be synthesis. Focus on non-obvious insights, not description."""

# ── Section Generation Prompt ──

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert analyst writing a section of a "Scenario Exploration Report" based on multi-agent simulation results.

Report title: {report_title}
Report summary: {report_summary}
Scenario under exploration: {simulation_requirement}

Current section to write: {section_title}

═══════════════════════════════════════════════════════════════
[Core Concept — ANALYTICAL Writing]
═══════════════════════════════════════════════════════════════

The simulation is a structured exploration — NOT a forecast. LLM-driven agents with diverse personas reacted to the scenario. Their behavior represents plausible responses given their assigned characteristics, not empirical predictions.

Your task is to ANALYZE, not describe:
- For every claim, provide: EVIDENCE (specific agent behavior) → MECHANISM (why it happened) → IMPLICATION (what it suggests)
- Identify at least one finding that CONTRADICTS naive expectations
- Trace CAUSAL CHAINS: "Agent X did Y, which caused Agent Z to react with W, leading to outcome Q"
- Flag where agent behavior CONTRADICTS their stated persona — this reveals the scenario's pressure points
- If you find only expected results, dig deeper — look for minority views that gained traction, unexpected alliances, or second-order effects
- Use hedged language: "the simulation suggests..." / "under these assumptions..." — NOT "this will happen"

Do NOT just describe what happened — explain WHY it happened and what it SUGGESTS
Do NOT write a generic summary — every paragraph should contain an analytical insight
Do NOT overclaim — this is scenario exploration, not prophecy

═══════════════════════════════════════════════════════════════
[Most Important Rules - Must Follow]
═══════════════════════════════════════════════════════════════

1. [Must Call Tools to Investigate the Simulation World]
   - You are analyzing the simulation from a "God's eye view"
   - All claims must be grounded in Agent behavior from the simulation
   - Each section must call tools at least 3 times (max 6) to gather evidence
   - **START with simulation_feed** — this is your PRIMARY data source. It contains
     the actual posts, comments, and trades that agents produced. Read it first,
     then use other tools to dig deeper.
   - Use market_state to get Polymarket price movements, trade history, and P&L
   - Use insight_forge for background context from the knowledge graph
   - Use analyze_trajectory for belief evolution data
   - QUOTE actual agent posts/comments — the report should cite what agents SAID

2. [Must Support Claims with Specific Evidence]
   - Every analytical claim needs a quote or data point as evidence:
     > "Agent X (a conservative economist) unexpectedly supported the regulation, saying: '...'"
   - Quote agent speech to show SURPRISES and CONTRADICTIONS, not just to illustrate expected behavior
   - Flag when an agent's actions contradict their persona — this is analytically valuable

3. [Language Consistency - Report Must Be Written in English]
   - All report content must be written in English
   - Content returned by tools may contain mixed-language expressions
   - When quoting content returned by tools, translate it into fluent English
   - This rule applies to both body text and quoted blocks (> format) content

4. [Analytical Integrity]
   - Report content must reflect simulation results — do not fabricate
   - If the simulation produced boring/expected results, say so honestly — then identify what subtle dynamics might explain the lack of surprise
   - If information is insufficient, state what WOULD need to be true to make a stronger claim

═══════════════════════════════════════════════════════════════
[Format Specifications - Extremely Important!]
═══════════════════════════════════════════════════════════════

[One Section = Minimum Content Unit]
- Each section is the smallest unit of the report
- Do NOT use any Markdown headings (#, ##, ###, ####, etc.) within a section
- Do NOT add section main title at the beginning of content
- Section titles are automatically added by the system; you only need to write pure body text
- Use **bold**, paragraph spacing, quotes, and lists to organize content, but do not use headings

[Correct Example]
```
This section analyzes the public opinion propagation trends. Through deep analysis of simulation data, we found...

**Initial Outbreak Phase**

Twitter served as the first scene of public opinion, taking on the core function of initial information dissemination:

> "Twitter contributed 68% of the initial volume..."

**Emotion Amplification Phase**

The Reddit platform further amplified the event's impact through community discussion:

- Strong community engagement
- High emotional resonance
```

[Incorrect Example]
```
## Executive Summary          <- Wrong! Do not add any headings
### 1. Initial Phase          <- Wrong! Do not use ### for subsections
#### 1.1 Detailed Analysis    <- Wrong! Do not use #### for subdivisions

This section analyzes...
```

═══════════════════════════════════════════════════════════════
[Available Retrieval Tools] (Call 3-5 times per section)
═══════════════════════════════════════════════════════════════

{tools_description}

[Tool Usage Tips - Mix different tools, do not only use one type]
- insight_forge: Deep insight analysis, automatically decomposes questions and retrieves facts and relationships across multiple dimensions
- panorama_search: Wide-angle panoramic search, understand the full picture, timeline, and evolution of events
- quick_search: Quickly verify a specific information point
- interview_agents: Interview simulation Agents, get first-person perspectives and real reactions from different roles

═══════════════════════════════════════════════════════════════
[Workflow]
═══════════════════════════════════════════════════════════════

Each reply you can only do one of the following two things (cannot do both):

Option A - Call a tool:
Output your thinking, then call a tool using the following format:
<tool_call>
{{"name": "tool_name", "parameters": {{"param_name": "param_value"}}}}
</tool_call>
The system will execute the tool and return the result to you. You do not need to and cannot write tool return results yourself.

Option B - Output final content:
When you have obtained sufficient information through tools, output section content starting with "Final Answer:".

Strictly prohibited:
- Do not include both tool calls and Final Answer in a single reply
- Do not fabricate tool return results (Observation); all tool results are injected by the system
- Call at most one tool per reply

═══════════════════════════════════════════════════════════════
[Section Content Requirements]
═══════════════════════════════════════════════════════════════

1. Content must be based on simulation data retrieved by tools
2. Extensively quote original text to demonstrate simulation results
3. Use Markdown format (but headings are prohibited):
   - Use **bold text** to highlight key points (instead of sub-headings)
   - Use lists (- or 1.2.3.) to organize points
   - Use blank lines to separate different paragraphs
   - Do NOT use #, ##, ###, #### or any heading syntax
4. [Quote Format Specification - Must Be Standalone Paragraphs]
   Quotes must be standalone paragraphs with a blank line before and after, not mixed within paragraphs:

   Correct format:
   ```
   The school's response was considered lacking in substance.

   > "The school's response model appeared rigid and slow in the rapidly changing social media environment."

   This assessment reflects widespread public dissatisfaction.
   ```

   Incorrect format:
   ```
   The school's response was considered lacking in substance.> "The school's response model..." This assessment reflects...
   ```
5. Maintain logical coherence with other sections
6. [Avoid Repetition] Carefully read the completed section content below, do not repeat the same information
7. [Emphasis Again] Do not add any headings! Use **bold** instead of subsection headings"""

SECTION_USER_PROMPT_TEMPLATE = """\
Completed section content (please read carefully to avoid repetition):
{previous_content}

═══════════════════════════════════════════════════════════════
[Current Task] Write section: {section_title}
═══════════════════════════════════════════════════════════════

[Important Reminders]
1. Carefully read the completed sections above to avoid repeating the same content!
2. You must call tools to get simulation data before starting
3. Mix different tools, do not only use one type
4. Report content must come from retrieval results, do not use your own knowledge

[Format Warning - Must Follow]
- Do NOT write any headings (#, ##, ###, #### are all prohibited)
- Do NOT write "{section_title}" as the beginning
- Section titles are automatically added by the system
- Write body text directly, use **bold** instead of subsection headings

Please begin:
1. First think (Thought) about what information this section needs
2. Then call tools (Action) to get simulation data
3. After collecting enough information, output Final Answer (pure body text, no headings)"""

# ── ReACT Loop Message Templates ──

REACT_OBSERVATION_TEMPLATE = """\
Observation (retrieval result):

═══ Tool {tool_name} returned ═══
{result}

═══════════════════════════════════════════════════════════════
Tools called {tool_calls_count}/{max_tool_calls} times (used: {used_tools_str}){unused_hint}

Before deciding your next step, ask yourself:
- Did this result reveal anything SURPRISING or NON-OBVIOUS?
- Can I now trace a CAUSAL CHAIN (cause → reaction → consequence)?
- Have I found evidence that CONTRADICTS expectations?

If yes → you may have enough for a strong analytical section. Output "Final Answer:"
If no → search for contradictions, minority views, or second-order effects with another tool.
═══════════════════════════════════════════════════════════════"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "[Notice] You have only called tools {tool_calls_count} times, at least {min_tool_calls} times required. "
    "Please call more tools to get more simulation data before outputting Final Answer. {unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "Currently only called tools {tool_calls_count} times, at least {min_tool_calls} times required. "
    "Please call tools to get simulation data. {unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "Tool call count has reached the limit ({tool_calls_count}/{max_tool_calls}), no more tool calls allowed. "
    'Please immediately output section content starting with "Final Answer:" based on the information already obtained.'
)

REACT_UNUSED_TOOLS_HINT = "\nYou haven't used: {unused_list} yet, consider trying different tools for multi-perspective information"

REACT_FORCE_FINAL_MSG = "Tool call limit reached, please directly output Final Answer: and generate section content."

# ── Chat Prompt ──

CHAT_SYSTEM_PROMPT_TEMPLATE = """\
You are a concise and efficient simulation analysis assistant.

[Background]
Scenario explored: {simulation_requirement}

[Generated Analysis Report]
{report_content}

[Rules]
1. Prioritize answering questions based on the report content above
2. Answer questions directly, avoid lengthy deliberation
3. Only call tools to retrieve more data when report content is insufficient to answer
4. Answers should be concise, clear, and well-organized

[Available Tools] (Use only when needed, call at most 1-2 times)
{tools_description}

[Tool Call Format]
<tool_call>
{{"name": "tool_name", "parameters": {{"param_name": "param_value"}}}}
</tool_call>

[Answer Style]
- Concise and direct, avoid lengthy text
- Use > format to quote key content
- Give conclusions first, then explain reasons"""

CHAT_OBSERVATION_SUFFIX = "\n\nPlease answer the question concisely."


# ═══════════════════════════════════════════════════════════════
# ReportAgent Main Class
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - Simulation Report Generation Agent

    Uses ReACT (Reasoning + Acting) pattern:
    1. Planning phase: Analyze simulation requirements, plan report table of contents
    2. Generation phase: Generate content section by section, each section can call tools multiple times
    3. Reflection phase: Check content completeness and accuracy
    """

    # Maximum tool calls per section
    MAX_TOOL_CALLS_PER_SECTION = 6

    # Maximum reflection rounds
    MAX_REFLECTION_ROUNDS = 3

    # Maximum tool calls per chat
    MAX_TOOL_CALLS_PER_CHAT = 2
    
    def __init__(
        self,
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        graph_tools: Optional[GraphToolsService] = None,
        simulation_type: str = "social",
    ):
        """
        Initialize Report Agent

        Args:
            graph_id: Graph ID
            simulation_id: Simulation ID
            simulation_requirement: Simulation requirement description
            llm_client: LLM client (optional)
            graph_tools: Graph tools service (optional, requires external GraphStorage injection)
            simulation_type: "social" (default) or "email_inbox" — selects prompt set
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        # Route to email inbox prompts for prospect-sim variant testing
        self.simulation_type = simulation_type

        self.llm = llm_client or create_smart_llm_client()
        if graph_tools is None:
            raise ValueError(
                "graph_tools (GraphToolsService) is required. "
                "Create it via GraphToolsService(storage=...) and pass it in."
            )
        self.graph_tools = graph_tools
        
        # Tool definitions
        self.tools = self._define_tools()

        # Logger (initialized in generate_report)
        self.report_logger: Optional[ReportLogger] = None
        # Console logger (initialized in generate_report)
        self.console_logger: Optional[ReportConsoleLogger] = None

        logger.info(f"ReportAgent initialization complete: graph_id={graph_id}, simulation_id={simulation_id}")
    
    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define available tools"""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "The question or topic you want to deeply analyze",
                    "report_context": "Current report section context (optional, helps generate more precise sub-questions)"
                }
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "Search query, used for relevance sorting",
                    "include_expired": "Whether to include expired/historical content (default True)"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "Search query string",
                    "limit": "Number of results to return (optional, default 10)"
                }
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "Interview topic or requirement description (e.g., 'understand students' views on the dormitory formaldehyde incident')",
                    "max_agents": "Maximum number of Agents to interview (optional, default 8, max 15)",
                    "agent_names": "Optional list of specific agent names to interview (skips LLM selection when provided)",
                    "dual_platform": "Whether to interview on both platforms (optional, default false — interviews on most active platform only)"
                }
            },
            "analyze_trajectory": {
                "name": "analyze_trajectory",
                "description": TOOL_DESC_ANALYZE_TRAJECTORY,
                "parameters": {
                    "focus": "Optional focus area: 'convergence', 'turning_points', 'polarization', or 'all' (default 'all')"
                }
            },
            "analyze_graph_structure": {
                "name": "analyze_graph_structure",
                "description": TOOL_DESC_GRAPH_STRUCTURE,
                "parameters": {
                    "query": "Optional focus query (e.g., 'media entities' or 'government response')"
                }
            },
            "find_causal_path": {
                "name": "find_causal_path",
                "description": TOOL_DESC_FIND_PATH,
                "parameters": {
                    "source": "Name of the starting entity (or partial match)",
                    "target": "Name of the target entity (or partial match)"
                }
            },
            "detect_contradictions": {
                "name": "detect_contradictions",
                "description": TOOL_DESC_CONTRADICTIONS,
                "parameters": {}
            },
            "simulation_feed": {
                "name": "simulation_feed",
                "description": TOOL_DESC_SIMULATION_FEED,
                "parameters": {
                    "platform": "Platform to read: 'twitter', 'reddit', 'polymarket', or 'all' (default 'all')",
                    "query": "Optional keyword filter for post content",
                    "round_num": "Optional round number filter"
                }
            },
            "market_state": {
                "name": "market_state",
                "description": TOOL_DESC_MARKET_STATE,
                "parameters": {}
            }
        }
    
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> str:
        """
        Execute tool call

        Args:
            tool_name: Tool name
            parameters: Tool parameters
            report_context: Report context (used for InsightForge)

        Returns:
            Tool execution result (text format)
        """
        logger.info(f"Executing tool: {tool_name}, parameters: {parameters}")
        
        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.graph_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                return result.to_text()
            
            elif tool_name == "panorama_search":
                # Breadth search - get full overview
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ['true', '1', 'yes']
                result = self.graph_tools.panorama_search(
                    graph_id=self.graph_id,
                    query=query,
                    include_expired=include_expired
                )
                return result.to_text()
            
            elif tool_name == "quick_search":
                # Simple search - quick retrieval
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.graph_tools.quick_search(
                    graph_id=self.graph_id,
                    query=query,
                    limit=limit
                )
                return result.to_text()
            
            elif tool_name == "interview_agents":
                # In-depth interview - call real OASIS interview API to get simulation Agent responses
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = parameters.get("max_agents", 8)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 15)
                agent_names = parameters.get("agent_names", None)
                if isinstance(agent_names, str):
                    agent_names = [n.strip() for n in agent_names.split(",") if n.strip()]
                dual_platform = parameters.get("dual_platform", False)
                if isinstance(dual_platform, str):
                    dual_platform = dual_platform.lower() in ("true", "1", "yes")
                result = self.graph_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents,
                    agent_names=agent_names,
                    dual_platform=dual_platform,
                )
                return result.to_text()
            
            elif tool_name == "analyze_trajectory":
                # Belief trajectory analysis — reads trajectory.json from simulation
                focus = parameters.get("focus", "all")
                return self._execute_trajectory_analysis(focus)

            elif tool_name == "analyze_graph_structure":
                # Graph structure analysis — centrality, communities, bridges
                query = parameters.get("query", "")
                return self.graph_tools.analyze_graph_structure(
                    graph_id=self.graph_id,
                    query=query
                )

            elif tool_name == "find_causal_path":
                # Causal path between two entities
                source = parameters.get("source", "")
                target = parameters.get("target", "")
                if not source or not target:
                    return "Error: both 'source' and 'target' parameters are required."
                return self.graph_tools.find_causal_path(
                    graph_id=self.graph_id,
                    source=source,
                    target=target
                )

            elif tool_name == "detect_contradictions":
                # Find contradicting edges in the graph
                return self.graph_tools.detect_contradictions(
                    graph_id=self.graph_id
                )

            elif tool_name == "simulation_feed":
                return self._execute_simulation_feed(parameters)

            elif tool_name == "market_state":
                return self._execute_market_state()

            # ========== Backward compatible legacy tools (internally redirected to new tools) ==========
            
            elif tool_name == "search_graph":
                # Redirect to quick_search
                logger.info("search_graph redirected to quick_search")
                return self._execute_tool("quick_search", parameters, report_context)
            
            elif tool_name == "get_graph_statistics":
                result = self.graph_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.graph_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_simulation_context":
                # Redirect to insight_forge, as it is more powerful
                logger.info("get_simulation_context redirected to insight_forge")
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)
            
            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.graph_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            else:
                return f"Unknown tool: {tool_name}. Please use one of: insight_forge, panorama_search, quick_search"
                
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {str(e)}")
            return f"Tool execution failed: {str(e)}"
    
    # Valid tool name set, used for validation during bare JSON fallback parsing
    VALID_TOOL_NAMES = {
        "insight_forge", "panorama_search", "quick_search", "interview_agents",
        "analyze_trajectory", "analyze_graph_structure", "find_causal_path", "detect_contradictions",
        "simulation_feed", "market_state",
    }

    def _execute_trajectory_analysis(self, focus: str = "all") -> str:
        """Execute the analyze_trajectory tool — reads trajectory.json from the simulation directory."""
        sim_dir = self._get_simulation_dir()
        trajectory_path = os.path.join(sim_dir, "trajectory.json")

        if not os.path.exists(trajectory_path):
            return (
                "No belief trajectory data available. The simulation may not have "
                "used the belief tracking system. This tool requires the simulation "
                "to have been run with belief tracking enabled (trajectory.json)."
            )

        try:
            with open(trajectory_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return f"Failed to read trajectory data: {str(e)}"

        lines = []
        lines.append(f"=== Belief Trajectory Analysis ===")
        lines.append(f"Topics tracked: {', '.join(data.get('topics', []))}")
        lines.append(f"Total rounds: {data.get('total_rounds', 0)}")
        lines.append("")

        # Convergence analysis
        if focus in ("all", "convergence", "polarization"):
            convergence = data.get("opinion_convergence", {})
            if convergence:
                lines.append("**Opinion Convergence/Polarization:**")
                for topic, score in convergence.items():
                    if score > 0.1:
                        lines.append(f"  - {topic}: CONVERGED by {score:.2f} — agents moved toward agreement")
                    elif score < -0.1:
                        lines.append(f"  - {topic}: POLARIZED by {abs(score):.2f} — agents became MORE divided")
                    else:
                        lines.append(f"  - {topic}: Stable — no significant shift ({score:.2f})")
                lines.append("")

        # Trajectories
        if focus in ("all", "convergence"):
            trajectories = data.get("belief_trajectories", {})
            for topic, rounds in trajectories.items():
                if rounds:
                    first = rounds[0]
                    last = rounds[-1]
                    lines.append(f"**{topic} trajectory:**")
                    lines.append(f"  Round {first['round']}: mean={first['mean']:.2f}, spread={first['spread']:.2f}")
                    lines.append(f"  Round {last['round']}: mean={last['mean']:.2f}, spread={last['spread']:.2f}")
                    # Find the round with maximum spread (most polarized)
                    max_spread_round = max(rounds, key=lambda r: r['spread'])
                    if max_spread_round['round'] != first['round'] and max_spread_round['round'] != last['round']:
                        lines.append(
                            f"  Peak polarization at round {max_spread_round['round']}: "
                            f"spread={max_spread_round['spread']:.2f}"
                        )
                    lines.append("")

        # Turning points
        if focus in ("all", "turning_points"):
            turning_points = data.get("turning_points", [])
            if turning_points:
                lines.append(f"**Significant Belief Shifts ({len(turning_points)} detected):**")
                for tp in turning_points[:10]:
                    lines.append(
                        f"  - Round {tp['round']}, Agent {tp['agent_id']}: "
                        f"{tp['topic']} shifted {tp['direction']} (delta: {tp['delta']:.3f})"
                    )
                lines.append("")

                # Summarize which agents changed most
                agent_shifts = {}
                for tp in turning_points:
                    aid = tp['agent_id']
                    agent_shifts[aid] = agent_shifts.get(aid, 0) + abs(tp['delta'])
                most_changed = sorted(agent_shifts.items(), key=lambda x: x[1], reverse=True)[:5]
                if most_changed:
                    lines.append("**Agents with most belief change:**")
                    for aid, total_delta in most_changed:
                        lines.append(f"  - Agent {aid}: total shift magnitude {total_delta:.3f}")
                    lines.append("")
            else:
                lines.append("No significant belief shifts detected — opinions remained stable.")
                lines.append("")

        return "\n".join(lines)

    def _get_simulation_dir(self) -> str:
        """Find the simulation directory (tries multiple locations)."""
        candidates = [
            os.path.join(Config.UPLOAD_FOLDER, 'simulations', self.simulation_id),
            os.path.join(os.path.dirname(__file__), '..', '..', 'pipeline_test_output', self.simulation_id),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return candidates[0]  # return default even if missing

    def _execute_simulation_feed(self, parameters: Dict[str, Any]) -> str:
        """Read actual simulation posts, comments, and trades."""
        platform_filter = parameters.get("platform", "all")
        query_filter = (parameters.get("query", "") or "").lower()
        round_filter = parameters.get("round_num")
        if isinstance(round_filter, str):
            round_filter = int(round_filter) if round_filter.isdigit() else None

        sim_dir = self._get_simulation_dir()
        lines = ["=== Simulation Feed ==="]

        platforms = ["twitter", "reddit", "polymarket"] if platform_filter == "all" else [platform_filter]
        total_actions = 0

        for platform in platforms:
            actions_path = os.path.join(sim_dir, platform, "actions.jsonl")
            if not os.path.exists(actions_path):
                continue

            try:
                with open(actions_path, 'r', encoding='utf-8') as f:
                    all_entries = [json.loads(l) for l in f if l.strip()]
            except Exception:
                continue

            # Filter to real actions (not metadata)
            actions = [a for a in all_entries if 'action_type' in a]

            # Apply round filter
            if round_filter is not None:
                actions = [a for a in actions if a.get('round_num') == round_filter]

            # Apply keyword filter
            if query_filter:
                actions = [
                    a for a in actions
                    if query_filter in json.dumps(a.get('action_args', {})).lower()
                    or query_filter in (a.get('agent_name', '') or '').lower()
                ]

            if not actions:
                continue

            lines.append(f"\n**[{platform.upper()}]** — {len(actions)} actions")

            # Action breakdown
            from collections import Counter
            types = Counter(a['action_type'] for a in actions)
            lines.append(f"  Breakdown: {', '.join(f'{t}: {c}' for t, c in types.most_common())}")

            # Show content-producing actions
            content_actions = [
                a for a in actions
                if a.get('action_type') in (
                    'CREATE_POST', 'CREATE_COMMENT', 'QUOTE_POST',
                    'create_post', 'create_comment',
                    'BUY_SHARES', 'SELL_SHARES', 'COMMENT_ON_MARKET',
                )
            ]

            for a in content_actions[:15]:
                agent = a.get('agent_name', f"Agent_{a.get('agent_id', '?')}")
                atype = a.get('action_type', '')
                args = a.get('action_args', {})
                rnd = a.get('round_num', '?')

                content = args.get('content', '') or args.get('quote_content', '')
                if content:
                    lines.append(f"  [R{rnd}] {agent} ({atype}): \"{content[:250]}\"")
                elif atype in ('BUY_SHARES', 'SELL_SHARES'):
                    outcome = args.get('outcome', '?')
                    amount = args.get('amount_usd', args.get('num_shares', '?'))
                    mid = args.get('market_id', '?')
                    lines.append(f"  [R{rnd}] {agent} {atype}: market#{mid} {outcome} ${amount}")

            total_actions += len(actions)

        if total_actions == 0:
            # Recursively search for any .jsonl files that may contain action data
            found_jsonl = []
            if os.path.exists(sim_dir):
                from pathlib import Path
                sim_path = Path(sim_dir)
                # Prefer actions.jsonl files, then fall back to any .jsonl
                found_jsonl = list(sim_path.rglob("actions.jsonl"))
                if not found_jsonl:
                    found_jsonl = list(sim_path.rglob("*.jsonl"))

            if found_jsonl:
                # Try to load actions from discovered files
                for jsonl_file in found_jsonl:
                    try:
                        with open(jsonl_file, 'r', encoding='utf-8') as f:
                            all_entries = [json.loads(l) for l in f if l.strip()]
                        actions = [a for a in all_entries if 'action_type' in a]

                        if round_filter is not None:
                            actions = [a for a in actions if a.get('round_num') == round_filter]
                        if query_filter:
                            actions = [
                                a for a in actions
                                if query_filter in json.dumps(a.get('action_args', {})).lower()
                                or query_filter in (a.get('agent_name', '') or '').lower()
                            ]

                        if not actions:
                            continue

                        # Derive a label from the file path relative to sim_dir
                        rel_path = str(jsonl_file.relative_to(sim_path))
                        lines.append(f"\n**[{rel_path}]** — {len(actions)} actions")

                        from collections import Counter
                        types = Counter(a['action_type'] for a in actions)
                        lines.append(f"  Breakdown: {', '.join(f'{t}: {c}' for t, c in types.most_common())}")

                        content_actions = [
                            a for a in actions
                            if a.get('action_type') in (
                                'CREATE_POST', 'CREATE_COMMENT', 'QUOTE_POST',
                                'create_post', 'create_comment',
                                'BUY_SHARES', 'SELL_SHARES', 'COMMENT_ON_MARKET',
                            )
                        ]

                        for a in content_actions[:15]:
                            agent = a.get('agent_name', f"Agent_{a.get('agent_id', '?')}")
                            atype = a.get('action_type', '')
                            args = a.get('action_args', {})
                            rnd = a.get('round_num', '?')

                            content = args.get('content', '') or args.get('quote_content', '')
                            if content:
                                lines.append(f"  [R{rnd}] {agent} ({atype}): \"{content[:250]}\"")
                            elif atype in ('BUY_SHARES', 'SELL_SHARES'):
                                outcome = args.get('outcome', '?')
                                amount = args.get('amount_usd', args.get('num_shares', '?'))
                                mid = args.get('market_id', '?')
                                lines.append(f"  [R{rnd}] {agent} {atype}: market#{mid} {outcome} ${amount}")

                        total_actions += len(actions)
                    except Exception:
                        continue

            # If still no actions after recursive search, return a clear error
            if total_actions == 0:
                lines.append(f"\n[ERROR] No simulation action data found. The simulation may not have completed successfully.")
                lines.append(f"Searched directory: {sim_dir}")
                if found_jsonl:
                    lines.append(f"Found {len(found_jsonl)} .jsonl file(s) but none contained matching action data.")
                elif os.path.exists(sim_dir):
                    lines.append("No .jsonl files found anywhere in the simulation directory.")
                else:
                    lines.append("The simulation directory does not exist.")

        return "\n".join(lines)

    def _execute_market_state(self) -> str:
        """Read Polymarket final state from SQLite."""
        import sqlite3

        sim_dir = self._get_simulation_dir()
        db_path = os.path.join(sim_dir, "polymarket_simulation.db")

        if not os.path.exists(db_path):
            return f"No Polymarket database found at {db_path}"

        lines = ["=== Polymarket Final State ==="]

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

            # Markets
            for m in conn.execute("SELECT * FROM market ORDER BY market_id"):
                ra, rb = m['reserve_a'], m['reserve_b']
                total = ra + rb
                price_yes = rb / total if total > 0 else 0.5
                trades = conn.execute(
                    "SELECT COUNT(*) FROM trade WHERE market_id=?", (m['market_id'],)
                ).fetchone()[0]
                lines.append(f"\n**Market #{m['market_id']}:** \"{m['question']}\"")
                lines.append(f"  Current price: YES ${price_yes:.3f} / NO ${1-price_yes:.3f}")
                lines.append(f"  Total trades: {trades}")

            # Trade history
            trades = conn.execute(
                "SELECT t.*, u.user_name FROM trade t "
                "LEFT JOIN user u ON t.user_id = u.user_id ORDER BY t.rowid"
            ).fetchall()
            if trades:
                lines.append(f"\n**Trade History** ({len(trades)} trades):")
                for t in trades:
                    agent = t['user_name'] or f"Agent_{t['user_id']}"
                    side = t['side'].upper()
                    lines.append(
                        f"  {side:4s} | {agent:30s} | {t['outcome']:3s} "
                        f"{t['shares']:.0f} shares @ ${t['price']:.3f} "
                        f"(${abs(t['cost']):.0f})"
                    )

            # Portfolios with P&L
            lines.append(f"\n**Trader P&L:**")
            for row in conn.execute(
                "SELECT p.user_id, p.balance, u.user_name FROM portfolio p "
                "LEFT JOIN user u ON p.user_id = u.user_id ORDER BY p.user_id"
            ):
                uid = row['user_id']
                agent = row['user_name'] or f"Agent_{uid}"
                balance = row['balance']

                pos_value = 0
                for pos in conn.execute(
                    "SELECT pos.shares, pos.outcome, m.reserve_a, m.reserve_b, m.outcome_a "
                    "FROM position pos JOIN market m ON pos.market_id = m.market_id "
                    "WHERE pos.user_id = ? AND pos.shares > 0.01", (uid,)
                ):
                    ra, rb = pos['reserve_a'], pos['reserve_b']
                    tot = ra + rb
                    cp = (rb/tot) if pos['outcome'] == pos['outcome_a'] else (ra/tot)
                    pos_value += pos['shares'] * cp

                total_val = balance + pos_value
                pnl = total_val - 1000
                lines.append(
                    f"  {agent:30s} | Cash: ${balance:.0f} | "
                    f"Positions: ${pos_value:.0f} | Total: ${total_val:.0f} | "
                    f"P&L: {'+'if pnl>=0 else ''}{pnl:.0f}"
                )

            conn.close()
        except Exception as e:
            lines.append(f"Error reading market data: {e}")

        return "\n".join(lines)

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from LLM response

        Supported formats (by priority):
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. Bare JSON (the entire response or a single line is a tool call JSON)
        """
        tool_calls = []

        # Format 1: XML style (standard format)
        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # Format 2: Fallback - LLM directly outputs bare JSON (without <tool_call> tags)
        # Only attempted when format 1 doesn't match, to avoid false matches on JSON in body text
        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # Response may contain thinking text + bare JSON, try to extract the last JSON object
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """Validate whether parsed JSON is a valid tool call"""
        # Supports both {"name": ..., "parameters": ...} and {"tool": ..., "params": ...} key names
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            # Normalize key names to name / parameters
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False
    
    def _get_tools_description(self) -> str:
        """Generate tool description text"""
        desc_parts = ["Available tools:"]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  Parameters: {params_desc}")
        return "\n".join(desc_parts)
    
    def plan_outline(
        self,
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        Plan report outline

        Use LLM to analyze simulation requirements and plan report table of contents

        Args:
            progress_callback: Progress callback function

        Returns:
            ReportOutline: Report outline
        """
        logger.info("Starting report outline planning...")
        
        if progress_callback:
            progress_callback("planning", 0, "Analyzing simulation requirements...")

        # First get simulation context
        context = self.graph_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )
        
        if progress_callback:
            progress_callback("planning", 30, "Generating report outline...")
        
        # Select prompts based on simulation type
        if self.simulation_type == "email_inbox":
            system_prompt = EMAIL_PLAN_SYSTEM_PROMPT
            user_prompt = EMAIL_PLAN_USER_PROMPT_TEMPLATE.format(
                simulation_requirement=self.simulation_requirement,
                total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
                total_entities=context.get('total_entities', 0),
                related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
            )
        else:
            system_prompt = PLAN_SYSTEM_PROMPT
            user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
                simulation_requirement=self.simulation_requirement,
                total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
                total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
                entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
                total_entities=context.get('total_entities', 0),
                related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
            )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            if progress_callback:
                progress_callback("planning", 80, "Parsing outline structure...")

            # Parse outline
            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))
            
            outline = ReportOutline(
                title=response.get("title", "Simulation Analysis Report"),
                summary=response.get("summary", ""),
                sections=sections
            )
            
            if progress_callback:
                progress_callback("planning", 100, "Outline planning complete")

            logger.info(f"Outline planning complete: {len(sections)} sections")
            return outline
            
        except Exception as e:
            logger.error(f"Outline planning failed: {str(e)}")
            # Return default outline (3 sections, as fallback)
            return ReportOutline(
                title="Scenario Exploration Report",
                summary="Future trend and risk analysis based on simulation predictions",
                sections=[
                    ReportSection(title="Prediction Scenario and Core Findings"),
                    ReportSection(title="Population Behavior Prediction Analysis"),
                    ReportSection(title="Trend Outlook and Risk Alerts")
                ]
            )
    
    def _generate_section_react(
        self,
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
        Generate single section content using ReACT pattern

        ReACT loop:
        1. Thought - Analyze what information is needed
        2. Action - Call tools to get information
        3. Observation - Analyze tool return results
        4. Repeat until information is sufficient or max iterations reached
        5. Final Answer - Generate section content

        Args:
            section: Section to generate
            outline: Complete outline
            previous_sections: Previous section contents (for maintaining coherence)
            progress_callback: Progress callback
            section_index: Section index (for logging)

        Returns:
            Section content (Markdown format)
        """
        logger.info(f"ReACT generating section: {section.title}")
        
        # Record section start log
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)
        
        # Build user prompt - pass in max 4000 characters per completed section
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # Max 4000 characters per section
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "(This is the first section)"

        # Select section prompt based on simulation type
        if self.simulation_type == "email_inbox":
            system_prompt = EMAIL_SECTION_SYSTEM_PROMPT_TEMPLATE.format(
                report_title=outline.title,
                report_summary=outline.summary,
                simulation_requirement=self.simulation_requirement,
                section_title=section.title,
                section_description=section.description,
                section_history=previous_content,
            )
            user_prompt = f"Write the '{section.title}' section now."
        else:
            system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
                report_title=outline.title,
                report_summary=outline.summary,
                simulation_requirement=self.simulation_requirement,
                section_title=section.title,
                tools_description=self._get_tools_description(),
            )
            user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
                previous_content=previous_content,
                section_title=section.title,
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # ReACT loop
        tool_calls_count = 0
        max_iterations = 8  # Maximum iteration rounds
        min_tool_calls = 2  # Minimum tool call count
        conflict_retries = 0  # Consecutive conflict count when tool call and Final Answer appear simultaneously
        used_tools = set()  # Track names of tools already called
        all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

        # Report context, used for InsightForge sub-question generation
        report_context = f"Section title: {section.title}\nSimulation requirement: {self.simulation_requirement}"
        
        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating", 
                    int((iteration / max_iterations) * 100),
                    f"Deep retrieval and writing ({tool_calls_count}/{self.MAX_TOOL_CALLS_PER_SECTION})"
                )
            
            # Call LLM
            response = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )

            # Check if LLM returned None (API exception or empty content)
            if response is None:
                logger.warning(f"Section {section.title} iteration {iteration + 1}: LLM returned None")
                # If iterations remain, add message and retry
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "(Response was empty)"})
                    messages.append({"role": "user", "content": "Please continue generating content."})
                    continue
                # Last iteration also returned None, break loop to force finish
                break

            logger.debug(f"LLM response: {response[:200]}...")

            # Parse once, reuse results
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # ── Conflict handling: LLM simultaneously output tool call and Final Answer ──
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    f"Section {section.title} round {iteration+1}: "
                    f"LLM simultaneously output tool call and Final Answer (conflict #{conflict_retries})"
                )

                if conflict_retries <= 2:
                    # First two times: discard this response, ask LLM to reply again
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[Format Error] Your reply contains both a tool call and Final Answer, which is not allowed.\n"
                            "Each reply can only do one of the following:\n"
                            "- Call a tool (output a <tool_call> block, do not write Final Answer)\n"
                            "- Output final content (start with 'Final Answer:', do not include <tool_call>)\n"
                            "Please reply again, doing only one of these."
                        ),
                    })
                    continue
                else:
                    # Third time: degrade, truncate to first tool call, force execute
                    logger.warning(
                        f"Section {section.title}: {conflict_retries} consecutive conflicts, "
                        "degrading to truncate and execute first tool call"
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # Record LLM response log
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            # ── Case 1: LLM output Final Answer ──
            if has_final_answer:
                # Tool call count insufficient, reject and require more tool calls
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = f"(These tools haven't been used yet, try them: {', '.join(unused_tools)})" if unused_tools else ""
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                # Normal completion
                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(f"Section {section.title} generation complete (tool calls: {tool_calls_count})")

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            # ── Case 2: LLM attempted to call tools ──
            if has_tool_calls:
                # Tool quota exhausted -> explicitly inform, require Final Answer output
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                # Only execute the first tool call
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(f"LLM attempted to call {len(tool_calls)} tools, only executing the first: {call['name']}")

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                # Build unused tools hint
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list=", ".join(unused_tools))

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # ── Case 3: Neither tool call nor Final Answer ──
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                # Tool call count insufficient, recommend unused tools
                unused_tools = all_tools - used_tools
                unused_hint = f"(These tools haven't been used yet, try them: {', '.join(unused_tools)})" if unused_tools else ""

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # Tool calls sufficient, LLM output content but without "Final Answer:" prefix
            # Directly use this content as final answer, no more idle iterations
            logger.info(f"Section {section.title} no 'Final Answer:' prefix detected, directly adopting LLM output as final content (tool calls: {tool_calls_count})")
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer
        
        # Reached maximum iterations, force content generation
        logger.warning(f"Section {section.title} reached maximum iterations, forcing generation")
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})
        
        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )

        # Check if LLM returned None during forced finish
        if response is None:
            logger.error(f"Section {section.title} LLM returned None during forced finish, using default error message")
            final_answer = f"(This section generation failed: LLM returned empty response, please retry later)"
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response
        
        # Record section content generation complete log
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )
        
        return final_answer
    
    def _generate_synthesis(
        self,
        generated_sections: List[str],
        outline: 'ReportOutline',
    ) -> Optional[str]:
        """Generate cross-section synthesis — patterns, contradictions, and meta-insights.

        This runs after all sections are generated and identifies:
        - Patterns spanning ACROSS sections
        - Contradictions between sections
        - The single most important non-obvious insight
        - What the report CANNOT answer and why

        Returns:
            Synthesis text to append to the last section, or None if generation fails.
        """
        if len(generated_sections) < 2:
            return None

        all_content = "\n\n---\n\n".join(
            sec[:3000] for sec in generated_sections
        )

        system_prompt = (
            "You are an expert analyst performing a cross-section synthesis of a scenario exploration report. "
            "You have just written all the sections below. Now step back and identify meta-patterns."
        )

        user_prompt = f"""\
Here are the sections you've written:

{all_content}

Now write a brief synthesis (300-500 words) that addresses:

1. **Cross-cutting patterns**: What themes or dynamics appear across multiple sections? What connects them?
2. **Internal contradictions**: Do any sections contain findings that tension or contradict each other? What does this tension reveal?
3. **The core insight**: In one sentence, what is the single most important non-obvious finding from this entire simulation?
4. **Epistemic limits**: What important question does this simulation NOT answer? What would we need to investigate further?

Write in the same analytical style as the report. Use **bold** for emphasis. Do NOT use any headings (#, ##, etc.)."""

        try:
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=2048,
            )
            if response:
                logger.info("Cross-section synthesis generated successfully")
                return response.strip()
        except Exception as e:
            logger.warning(f"Synthesis generation failed: {e}")

        return None

    def generate_report(
        self,
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        Generate complete report (real-time section-by-section output)

        Each section is saved to the folder immediately after generation, no need to wait for the entire report.
        File structure:
        reports/{report_id}/
            meta.json       - Report metadata
            outline.json    - Report outline
            progress.json   - Generation progress
            section_01.md   - Section 1
            section_02.md   - Section 2
            ...
            full_report.md  - Complete report

        Args:
            progress_callback: Progress callback function (stage, progress, message)
            report_id: Report ID (optional, auto-generated if not provided)

        Returns:
            Report: Complete report
        """
        import uuid
        
        # If no report_id provided, auto-generate one
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()
        
        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        # Completed section titles list (for progress tracking)
        completed_section_titles = []
        
        try:
            # Initialize: create report folder and save initial state
            ReportManager._ensure_report_folder(report_id)
            
            # Initialize logger (structured log agent_log.jsonl)
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement
            )
            
            # Initialize console logger (console_log.txt)
            self.console_logger = ReportConsoleLogger(report_id)
            
            ReportManager.update_progress(
                report_id, "pending", 0, "Initializing report...",
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            # Phase 1: Plan outline
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, "Starting report outline planning...",
                completed_sections=[]
            )
            
            # Record planning start log
            self.report_logger.log_planning_start()
            
            if progress_callback:
                progress_callback("planning", 0, "Starting report outline planning...")
            
            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg: 
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
            )
            report.outline = outline
            
            # Record planning complete log
            self.report_logger.log_planning_complete(outline.to_dict())
            
            # Save outline to file
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id, "planning", 15, f"Outline planning complete, {len(outline.sections)} sections total",
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            logger.info(f"Outline saved to file: {report_id}/outline.json")
            
            # Phase 2: Generate section by section (save per section)
            report.status = ReportStatus.GENERATING
            
            total_sections = len(outline.sections)
            generated_sections = []  # Save content for context
            
            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)
                
                # Update progress
                ReportManager.update_progress(
                    report_id, "generating", base_progress,
                    f"Generating section: {section.title} ({section_num}/{total_sections})",
                    current_section=section.title,
                    completed_sections=completed_section_titles
                )

                if progress_callback:
                    progress_callback(
                        "generating",
                        base_progress,
                        f"Generating section: {section.title} ({section_num}/{total_sections})"
                    )
                
                # Generate main section content
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg:
                        progress_callback(
                            stage, 
                            base_progress + int(prog * 0.7 / total_sections),
                            msg
                        ) if progress_callback else None,
                    section_index=section_num
                )
                
                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # Save section
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # Record section complete log
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip()
                    )

                logger.info(f"Section saved: {report_id}/section_{section_num:02d}.md")
                
                # Update progress
                ReportManager.update_progress(
                    report_id, "generating", 
                    base_progress + int(70 / total_sections),
                    f"Section {section.title} completed",
                    current_section=None,
                    completed_sections=completed_section_titles
                )
            
            # Phase 2.5: Cross-section synthesis
            if progress_callback:
                progress_callback("generating", 92, "Synthesizing cross-section insights...")

            ReportManager.update_progress(
                report_id, "generating", 92, "Synthesizing cross-section insights...",
                completed_sections=completed_section_titles
            )

            synthesis = self._generate_synthesis(generated_sections, outline)
            if synthesis:
                # Append synthesis to the last section's content (which should be the synthesis section)
                last_section = outline.sections[-1]
                last_section.content = (last_section.content or "") + "\n\n" + synthesis
                # Re-save the last section
                ReportManager.save_section(report_id, len(outline.sections), last_section)
                generated_sections[-1] = f"## {last_section.title}\n\n{last_section.content}"

            # Phase 3: Assemble complete report
            if progress_callback:
                progress_callback("generating", 95, "Assembling complete report...")

            ReportManager.update_progress(
                report_id, "generating", 95, "Assembling complete report...",
                completed_sections=completed_section_titles
            )

            # Use ReportManager to assemble complete report
            report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()
            
            # Calculate total time
            total_time_seconds = (datetime.now() - start_time).total_seconds()
            
            # Record report complete log
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections,
                    total_time_seconds=total_time_seconds
                )
            
            # Save final report
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id, "completed", 100, "Report generation complete",
                completed_sections=completed_section_titles
            )
            
            if progress_callback:
                progress_callback("completed", 100, "Report generation complete")
            
            logger.info(f"Report generation complete: {report_id}")
            
            # Close console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            report.status = ReportStatus.FAILED
            report.error = str(e)
            
            # Record error log
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")
            
            # Save failed state
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "failed", -1, f"Report generation failed: {str(e)}",
                    completed_sections=completed_section_titles
                )
            except Exception:
                pass  # Ignore errors from failed save
            
            # Close console logger
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

    def chat(
        self, 
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Chat with Report Agent

        In conversation, Agent can autonomously call retrieval tools to answer questions

        Args:
            message: User message
            chat_history: Chat history

        Returns:
            {
                "response": "Agent reply",
                "tool_calls": [list of tools called],
                "sources": [information sources]
            }
        """
        logger.info(f"Report Agent chat: {message[:50]}...")
        
        chat_history = chat_history or []
        
        # Get generated report content
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                # Limit report length to avoid excessive context
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [Report content truncated] ..."
        except Exception as e:
            logger.warning(f"Failed to get report content: {e}")
        
        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "(No report yet)",
            tools_description=self._get_tools_description(),
        )

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add chat history
        for h in chat_history[-10:]:  # Limit history length
            messages.append(h)
        
        # Add user message
        messages.append({
            "role": "user", 
            "content": message
        })
        
        # ReACT loop (simplified version)
        tool_calls_made = []
        max_iterations = 2  # Reduced iteration rounds
        
        for iteration in range(max_iterations):
            response = self.llm.chat(
                messages=messages,
                temperature=0.5
            )
            
            # Parse tool calls
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                # No tool calls, return response directly
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
                
                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }
            
            # Execute tool calls (limit count)
            tool_results = []
            for call in tool_calls[:1]:  # Max 1 tool call per round
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result[:1500]  # Limit result length
                })
                tool_calls_made.append(call)
            
            # Add results to messages
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']} result]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })
        
        # Reached max iterations, get final response
        final_response = self.llm.chat(
            messages=messages,
            temperature=0.5
        )
        
        # Clean response
        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
        
        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }


class ReportManager:
    """
    Report Manager

    Responsible for report persistence and retrieval

    File structure (section-by-section output):
    reports/
      {report_id}/
        meta.json          - Report metadata and status
        outline.json       - Report outline
        progress.json      - Generation progress
        section_01.md      - Section 1
        section_02.md      - Section 2
        ...
        full_report.md     - Complete report
    """
    
    # Report storage directory
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'reports')
    
    @classmethod
    def _ensure_reports_dir(cls):
        """Ensure reports root directory exists"""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """Get report folder path"""
        return os.path.join(cls.REPORTS_DIR, report_id)
    
    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """Ensure report folder exists and return path"""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder
    
    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """Get report metadata file path"""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")
    
    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """Get complete report Markdown file path"""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")
    
    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """Get outline file path"""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")
    
    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """Get progress file path"""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")
    
    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """Get section Markdown file path"""
        return os.path.join(cls._get_report_folder(report_id), f"section_{section_index:02d}.md")
    
    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """Get Agent log file path"""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")
    
    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """Get console log file path"""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")
    
    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get console log content

        This is the console output log (INFO, WARNING, etc.) during report generation,
        different from the structured log in agent_log.jsonl.

        Args:
            report_id: Report ID
            from_line: Starting line number (for incremental retrieval, 0 means from the beginning)

        Returns:
            {
                "logs": [list of log lines],
                "total_lines": total line count,
                "from_line": starting line number,
                "has_more": whether there are more logs
            }
        """
        log_path = cls._get_console_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # Keep original log line, remove trailing newline
                    logs.append(line.rstrip('\n\r'))
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Already read to the end
        }

    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        Get complete console log (all at once)

        Args:
            report_id: Report ID

        Returns:
            List of log lines
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get Agent log content

        Args:
            report_id: Report ID
            from_line: Starting line number (for incremental retrieval, 0 means from the beginning)

        Returns:
            {
                "logs": [list of log entries],
                "total_lines": total line count,
                "from_line": starting line number,
                "has_more": whether there are more logs
            }
        """
        log_path = cls._get_agent_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # Skip lines that fail to parse
                        continue
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Already read to the end
        }

    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get complete Agent log (for retrieving all at once)

        Args:
            report_id: Report ID

        Returns:
            List of log entries
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        Save report outline

        Called immediately after planning phase completes
        """
        cls._ensure_report_folder(report_id)
        
        with open(cls._get_outline_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Outline saved: {report_id}")
    
    @classmethod
    def save_section(
        cls,
        report_id: str,
        section_index: int,
        section: ReportSection
    ) -> str:
        """
        Save a single section

        Called immediately after each section is generated, enabling section-by-section output

        Args:
            report_id: Report ID
            section_index: Section index (starting from 1)
            section: Section object

        Returns:
            Saved file path
        """
        cls._ensure_report_folder(report_id)

        # Build section Markdown content - clean possible duplicate headings
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # Save file
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(f"Section saved: {report_id}/{file_suffix}")
        return file_path
    
    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        Clean section content

        1. Remove Markdown heading lines at the beginning that duplicate the section title
        2. Convert all ### and lower level headings to bold text

        Args:
            content: Original content
            section_title: Section title

        Returns:
            Cleaned content
        """
        import re
        
        if not content:
            return content
        
        content = content.strip()
        lines = content.split('\n')
        cleaned_lines = []
        skip_next_empty = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check if it's a Markdown heading line
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()
                
                # Check if heading duplicates the section title (skip duplicates within first 5 lines)
                if i < 5:
                    if title_text == section_title or title_text.replace(' ', '') == section_title.replace(' ', ''):
                        skip_next_empty = True
                        continue
                
                # Convert all heading levels (#, ##, ###, ####, etc.) to bold
                # Since section titles are added by the system, content should not have any headings
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # Add empty line
                continue
            
            # If previous line was a skipped heading and current line is empty, skip it too
            if skip_next_empty and stripped == '':
                skip_next_empty = False
                continue
            
            skip_next_empty = False
            cleaned_lines.append(line)
        
        # Remove leading empty lines
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)
        
        # Remove leading separator lines
        while cleaned_lines and cleaned_lines[0].strip() in ['---', '***', '___']:
            cleaned_lines.pop(0)
            # Also remove empty lines after separator
            while cleaned_lines and cleaned_lines[0].strip() == '':
                cleaned_lines.pop(0)
        
        return '\n'.join(cleaned_lines)
    
    @classmethod
    def update_progress(
        cls, 
        report_id: str, 
        status: str, 
        progress: int, 
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None
    ) -> None:
        """
        Update report generation progress

        Frontend can get real-time progress by reading progress.json
        """
        cls._ensure_report_folder(report_id)
        
        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(cls._get_progress_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report generation progress"""
        path = cls._get_progress_path(report_id)
        
        if not os.path.exists(path):
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get list of generated sections

        Returns information about all saved section files
        """
        folder = cls._get_report_folder(report_id)
        
        if not os.path.exists(folder):
            return []
        
        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse section index from filename
                parts = filename.replace('.md', '').split('_')
                section_index = int(parts[1])

                sections.append({
                    "filename": filename,
                    "section_index": section_index,
                    "content": content
                })

        return sections
    
    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
        Assemble complete report

        Assemble complete report from saved section files and clean headings
        """
        folder = cls._get_report_folder(report_id)
        
        # Build report header
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"
        
        # Read all section files in order
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]
        
        # Post-processing: clean heading issues across the entire report
        md_content = cls._post_process_report(md_content, outline)
        
        # Save complete report
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"Complete report assembled: {report_id}")
        return md_content
    
    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
        Post-process report content

        1. Remove duplicate headings
        2. Keep report main title (#) and section titles (##), remove other heading levels (###, ####, etc.)
        3. Clean excess blank lines and separator lines

        Args:
            content: Original report content
            outline: Report outline

        Returns:
            Processed content
        """
        import re
        
        lines = content.split('\n')
        processed_lines = []
        prev_was_heading = False
        
        # Collect all section titles from outline
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Check if it's a heading line
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # Check if it's a duplicate heading (same content heading within 5 consecutive lines)
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r'^(#{1,6})\s+(.+)$', prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    # Skip duplicate heading and following blank lines
                    i += 1
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue
                
                # Heading level handling:
                # - # (level=1) Only keep report main title
                # - ## (level=2) Keep section titles
                # - ### and below (level>=3) Convert to bold text
                
                if level == 1:
                    if title == outline.title:
                        # Keep report main title
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # Section title incorrectly used #, fix to ##
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # Other level-1 headings converted to bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        # Keep section title
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # Non-section level-2 headings converted to bold
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # ### and below level headings converted to bold text
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False
                
                i += 1
                continue
            
            elif stripped == '---' and prev_was_heading:
                # Skip separator lines immediately after headings
                i += 1
                continue
            
            elif stripped == '' and prev_was_heading:
                # Only keep one blank line after heading
                if processed_lines and processed_lines[-1].strip() != '':
                    processed_lines.append(line)
                prev_was_heading = False
            
            else:
                processed_lines.append(line)
                prev_was_heading = False
            
            i += 1
        
        # Clean consecutive blank lines (keep at most 2)
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    @classmethod
    def save_report(cls, report: Report) -> None:
        """Save report metadata and complete report"""
        cls._ensure_report_folder(report.report_id)
        
        # Save metadata JSON
        with open(cls._get_report_path(report.report_id), 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        # Save outline
        if report.outline:
            cls.save_outline(report.report_id, report.outline)
        
        # Save complete Markdown report
        if report.markdown_content:
            with open(cls._get_report_markdown_path(report.report_id), 'w', encoding='utf-8') as f:
                f.write(report.markdown_content)
        
        logger.info(f"Report saved: {report.report_id}")
    
    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """Get report"""
        path = cls._get_report_path(report_id)
        
        if not os.path.exists(path):
            # Backward compatibility: check files stored directly in reports directory
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Rebuild Report object
        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            sections = []
            for s in outline_data.get('sections', []):
                sections.append(ReportSection(
                    title=s['title'],
                    content=s.get('content', '')
                ))
            outline = ReportOutline(
                title=outline_data['title'],
                summary=outline_data['summary'],
                sections=sections
            )
        
        # If markdown_content is empty, try reading from full_report.md
        markdown_content = data.get('markdown_content', '')
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
        
        return Report(
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            simulation_requirement=data['simulation_requirement'],
            status=ReportStatus(data['status']),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error')
        )
    
    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """Get report by simulation ID"""
        cls._ensure_reports_dir()
        
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # New format: folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report and report.simulation_id == simulation_id:
                    return report
            # Backward compatibility: JSON file
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report and report.simulation_id == simulation_id:
                    return report
        
        return None
    
    @classmethod
    def list_reports(cls, simulation_id: Optional[str] = None, limit: int = 50) -> List[Report]:
        """List reports"""
        cls._ensure_reports_dir()
        
        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # New format: folder
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            # Backward compatibility: JSON file
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
        
        # Sort by creation time descending
        reports.sort(key=lambda r: r.created_at, reverse=True)
        
        return reports[:limit]
    
    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """Delete report (entire folder)"""
        import shutil
        
        folder_path = cls._get_report_folder(report_id)
        
        # New format: delete entire folder
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(f"Report folder deleted: {report_id}")
            return True
        
        # Backward compatibility: delete individual files
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")
        
        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True
        
        return deleted
