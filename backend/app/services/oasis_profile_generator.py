"""
OASIS Agent Profile Generator
Convert entities from the knowledge graph to OASIS simulation platform's required Agent Profile format

Optimization improvements:
1. Call knowledge graph retrieval function to enrich node information
2. Optimize prompts to generate very detailed personas
3. Distinguish between individual entities and abstract group entities
"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from ..config import Config
from ..utils.llm_client import create_llm_client
from ..utils.logger import get_logger
from .entity_reader import EntityNode
from .web_enrichment import WebEnricher
from ..storage import GraphStorage

logger = get_logger('miroshark.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent Profile data structure"""
    # Common fields
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    # Optional fields - Reddit style
    karma: int = 1000
    
    # Optional fields - Twitter style
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # Risk/engagement fields (used for agent behavior calibration)
    risk_tolerance: str = "moderate"  # "high", "moderate", or "low"

    # B2B email inbox simulation fields
    # These are populated when simulation_type == "email_inbox"
    budget_authority: bool = False           # Can they approve L&D spend directly?
    cold_email_skepticism: float = 0.6       # 0.0 = open, 1.0 = extremely skeptical
    inbox_habit: str = "batch_processor"     # morning_scanner | batch_processor | responsive
    pain_signal_sensitivity: Dict[str, float] = field(default_factory=dict)  # pain_type → 0-1
    decision_style: str = "roi_driven"       # roi_driven | risk_averse | early_adopter | social_proof

    # Additional persona information
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)
    
    # Source entity information
    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """Convert to Reddit platform format"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS library requires field name as username (no underscore)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
        # Add additional persona information (if available)
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics

        return profile

    def to_twitter_format(self) -> Dict[str, Any]:
        """Convert to Twitter platform format"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS library requires field name as username (no underscore)
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        # Add additional persona information
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_inbox_format(self) -> Dict[str, Any]:
        """Convert to email inbox simulation format.

        Returns a dict compatible with Wonderwall's UserInfo(profile={"other_info": ...})
        structure, which EmailInboxPromptBuilder reads to build B2B decision-maker personas.
        """
        user_profile = self.persona or f"{self.name} is an HR professional at a Spanish SME."
        if self.profession:
            user_profile = f"{self.profession}. {user_profile}"

        return {
            "user_id": self.user_id,
            "name": self.user_name,
            "description": self.bio or f"HR professional: {self.name}",
            # B2B inbox-specific fields read by EmailInboxPromptBuilder
            "user_profile": user_profile,
            "budget_authority": self.budget_authority,
            "cold_email_skepticism": self.cold_email_skepticism,
            "inbox_habit": self.inbox_habit,
            "pain_signal_sensitivity": self.pain_signal_sensitivity,
            "decision_style": self.decision_style,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to complete dictionary format"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
            # B2B email inbox fields
            "budget_authority": self.budget_authority,
            "cold_email_skepticism": self.cold_email_skepticism,
            "inbox_habit": self.inbox_habit,
            "pain_signal_sensitivity": self.pain_signal_sensitivity,
            "decision_style": self.decision_style,
        }


def _social_metrics_for_entity_type(entity_type: str, entity=None) -> Dict[str, int]:
    """Derive social media metrics from entity type and graph structure.

    Replaces the previous random.randint() fallbacks with values grounded in
    the entity's structural role. An institutional media outlet should have
    high follower counts; a student should have modest ones.

    If the entity has related_edges (from the knowledge graph), the degree
    (number of connections) is used as a scaling factor — more connected
    entities get proportionally higher metrics.
    """
    # Use graph degree as a scaling factor (1.0 = baseline, up to ~3.0 for hubs)
    degree = 1
    if entity and hasattr(entity, 'related_edges') and entity.related_edges:
        degree = len(entity.related_edges)
    elif entity and hasattr(entity, 'attributes') and isinstance(entity.attributes, dict):
        degree = entity.attributes.get('degree', 1)
    degree_factor = min(3.0, 1.0 + (degree - 1) * 0.15)

    et = entity_type.lower()

    # Base metrics by entity archetype
    if et in ("mediaoutlet", "socialmediaplatform"):
        base = {"karma": 15000, "friend_count": 200, "follower_count": 50000, "statuses_count": 10000}
    elif et in ("university", "governmentagency", "organization", "ngo"):
        base = {"karma": 8000, "friend_count": 150, "follower_count": 20000, "statuses_count": 5000}
    elif et in ("publicfigure", "expert", "faculty"):
        base = {"karma": 5000, "friend_count": 300, "follower_count": 8000, "statuses_count": 3000}
    elif et in ("student", "alumni"):
        base = {"karma": 800, "friend_count": 200, "follower_count": 300, "statuses_count": 500}
    elif et in ("politician", "official", "regulator"):
        base = {"karma": 6000, "friend_count": 250, "follower_count": 15000, "statuses_count": 4000}
    else:
        base = {"karma": 1500, "friend_count": 120, "follower_count": 500, "statuses_count": 800}

    # Scale by graph degree and add small deterministic jitter from entity name hash
    name_hash = 0
    if entity and hasattr(entity, 'name') and entity.name:
        name_hash = hash(entity.name) % 100  # 0-99 deterministic per entity
    jitter = 0.85 + (name_hash / 100) * 0.30  # 0.85 to 1.15

    return {
        k: max(1, int(v * degree_factor * jitter))
        for k, v in base.items()
    }


class OasisProfileGenerator:
    """
    OASIS Profile Generator

    Convert entities from the knowledge graph to Agent Profile required by OASIS simulation

    Optimization features:
    1. Call knowledge graph retrieval function to get richer context
    2. Generate very detailed personas (including basic info, career history, personality traits, social media behavior, etc.)
    3. Distinguish between individual entities and abstract group entities
    """

    # MBTI types list
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # Common countries list
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France", 
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]
    
    # Individual entity types (require generating specific personas)
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure",
        "expert", "faculty", "official", "journalist", "activist",
        "politician", "scientist", "researcher", "athlete", "artist",
        "musician", "author", "entrepreneur", "investor", "diplomat",
        "celebrity", "ceo", "executive", "regulator",
    ]

    # Keywords in entity type names that indicate an individual
    INDIVIDUAL_TYPE_KEYWORDS = [
        "founder", "forecaster", "user", "trader", "influencer",
        "analyst", "advisor", "leader", "critic", "advocate",
        "commentator", "blogger", "developer", "engineer",
    ]

    # Group/institutional entity types (require generating representative account personas)
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo",
        "mediaoutlet", "company", "institution", "group", "community",
        "agency", "platform", "network", "protocol", "framework",
        "fund", "exchange", "consortium", "coalition",
    ]
    
    # B2B entity types for email inbox simulation
    B2B_PERSONA_TYPES = [
        "hrdirector", "headofpeople", "hrmanager", "peopleops",
        "cpo", "ceo", "founder", "directorofhr", "vpofpeople",
        "talentacquisition", "learninganddevelopment", "ldmanager",
    ]

    # B2B company types (generate representative personas, not individuals)
    B2B_COMPANY_TYPES = [
        "sme", "startup", "scaleup", "techcompany", "b2bcompany",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        storage: Optional[GraphStorage] = None,
        graph_id: Optional[str] = None,
        simulation_requirement: Optional[str] = None,
        simulation_type: str = "social",
    ):
        self.model_name = model_name or Config.LLM_MODEL_NAME
        self.llm = create_llm_client(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
        )

        # GraphStorage for hybrid search enrichment
        self.storage = storage
        self.graph_id = graph_id

        # Web enrichment for notable figures / thin context
        self.web_enricher = WebEnricher()
        self.simulation_requirement = simulation_requirement or ""

        # "social" (default) or "email_inbox" — controls persona generation strategy
        self.simulation_type = simulation_type
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        Generate OASIS Agent Profile from knowledge graph entity

        Args:
            entity: Knowledge graph entity node
            user_id: User ID (for OASIS)
            use_llm: Whether to use LLM to generate detailed persona

        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        # Basic information
        name = entity.name
        user_name = self._generate_username(name)
        
        # Build context information
        context = self._build_entity_context(entity)
        
        if use_llm:
            # Use LLM to generate detailed persona
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # Use rules to generate basic persona
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        # Derive risk_tolerance from entity type and MBTI if the LLM didn't provide one
        risk_tolerance = profile_data.get("risk_tolerance")
        if not risk_tolerance:
            risk_tolerance = self._infer_risk_tolerance(
                entity_type, profile_data.get("mbti"), profile_data.get("profession"),
                entity_name=name,
            )

        # Derive social metrics from entity type + graph degree instead of random dice rolls.
        # These defaults are still approximations, but they're at least grounded in the
        # entity's structural role rather than random.randint().
        social_defaults = _social_metrics_for_entity_type(entity_type, entity)

        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            risk_tolerance=risk_tolerance,
            karma=profile_data.get("karma", social_defaults["karma"]),
            friend_count=profile_data.get("friend_count", social_defaults["friend_count"]),
            follower_count=profile_data.get("follower_count", social_defaults["follower_count"]),
            statuses_count=profile_data.get("statuses_count", social_defaults["statuses_count"]),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
            # B2B email inbox fields — populated when simulation_type == "email_inbox"
            budget_authority=bool(profile_data.get("budget_authority", False)),
            cold_email_skepticism=float(profile_data.get("cold_email_skepticism", 0.6)),
            inbox_habit=profile_data.get("inbox_habit", "batch_processor"),
            pain_signal_sensitivity=profile_data.get("pain_signal_sensitivity", {}),
            decision_style=profile_data.get("decision_style", "roi_driven"),
        )
    
    def _generate_username(self, name: str) -> str:
        """Generate username"""
        # Remove special characters, convert to lowercase
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # Add random suffix to avoid duplicates
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    @staticmethod
    def _infer_risk_tolerance(entity_type: str, mbti: Optional[str], profession: Optional[str],
                              entity_name: str = "") -> str:
        """Infer risk tolerance from entity characteristics."""
        # Check entity name for domain-specific hints
        name_lower = (entity_name or "").lower()
        if any(w in name_lower for w in ("hedge fund", "venture", "trading", "capital",
                                          "defi")):
            return "high"
        if any(w in name_lower for w in ("stablecoin", "usdc", "usdt", "reserve", "treasury")):
            return "low"

        # Institutional entities tend to be conservative
        if entity_type and entity_type.lower() in (
            "governmentagency", "ngo", "institution", "university"
        ):
            return "low"
        # Companies and media — vary based on domain
        if entity_type and entity_type.lower() in ("company", "mediaoutlet", "organization"):
            # Use name hash for deterministic but varied assignment
            if entity_name:
                h = hash(entity_name) % 3
                return ["low", "moderate", "high"][h]
            return "moderate"
        # Derive from MBTI: perceiving types (xNxP) tend to be more risk-tolerant
        if mbti and len(mbti) == 4:
            if mbti[1] == 'N' and mbti[3] == 'P':
                return "high"
            if mbti[1] == 'S' and mbti[3] == 'J':
                return "low"
        # Derive from profession keywords
        if profession:
            p = profession.lower()
            if any(w in p for w in ("trader", "investor", "entrepreneur", "activist")):
                return "high"
            if any(w in p for w in ("accountant", "official", "administrator", "lawyer")):
                return "low"
        return random.choice(["high", "moderate", "moderate", "low"])

    def _search_graph_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        Use GraphStorage hybrid search to obtain rich information related to entity

        Uses storage.search() (hybrid vector + BM25) for both edges and nodes.

        Args:
            entity: Entity node object

        Returns:
            Dictionary containing facts, node_summaries, context
        """
        if not self.storage:
            return {"facts": [], "node_summaries": [], "context": ""}

        entity_name = entity.name

        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }

        if not self.graph_id:
            logger.debug(f"Skip knowledge graph search: graph_id not set")
            return results

        comprehensive_query = f"All information, activities, events, relationships and background about {entity_name}"

        try:
            # Search edges (facts)
            edge_results = self.storage.search(
                graph_id=self.graph_id,
                query=comprehensive_query,
                limit=30,
                scope="edges"
            )

            all_facts = set()
            if isinstance(edge_results, dict) and 'edges' in edge_results:
                for edge in edge_results['edges']:
                    fact = edge.get('fact', '')
                    if fact:
                        all_facts.add(fact)
            results["facts"] = list(all_facts)

            # Search nodes (entity summaries)
            node_results = self.storage.search(
                graph_id=self.graph_id,
                query=comprehensive_query,
                limit=20,
                scope="nodes"
            )

            all_summaries = set()
            if isinstance(node_results, dict) and 'nodes' in node_results:
                for node in node_results['nodes']:
                    summary = node.get('summary', '')
                    if summary:
                        all_summaries.add(summary)
                    name = node.get('name', '')
                    if name and name != entity_name:
                        all_summaries.add(f"Related Entity: {name}")
            results["node_summaries"] = list(all_summaries)

            # Build combined context
            context_parts = []
            if results["facts"]:
                context_parts.append("Fact Information:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("Related Entities:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)

            logger.info(f"Knowledge graph hybrid search completed: {entity_name}, retrieved {len(results['facts'])} facts, {len(results['node_summaries'])} related nodes")

        except Exception as e:
            logger.warning(f"Knowledge graph search failed ({entity_name}): {e}")

        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        Build complete context information for an entity

        Includes:
        1. Edge information (facts) of the entity itself
        2. Detailed information of related nodes
        3. Rich information from knowledge graph hybrid retrieval
        """
        context_parts = []
        
        # 1. Add entity attribute information
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### Entity Attributes\n" + "\n".join(attrs))
        
        # 2. Add related edge information (facts/relationships)
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # No limit on count
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (related entity)")
                    else:
                        relationships.append(f"- (related entity) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### Related Facts and Relationships\n" + "\n".join(relationships))
        
        # 3. Add detailed information of related nodes
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # No limit on count
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # Filter out default labels
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### Related Entity Information\n" + "\n".join(related_info))
        
        # 4. Use knowledge graph hybrid search to get richer information
        graph_results = self._search_graph_for_entity(entity)

        if graph_results.get("facts"):
            # Deduplication: exclude existing facts
            new_facts = [f for f in graph_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Facts Retrieved from Knowledge Graph\n" + "\n".join(f"- {f}" for f in new_facts[:15]))

        if graph_results.get("node_summaries"):
            context_parts.append("### Related Nodes Retrieved from Knowledge Graph\n" + "\n".join(f"- {s}" for s in graph_results["node_summaries"][:10]))

        # 5. Web enrichment — fetch real-world info for notable figures or thin context
        existing_context = "\n\n".join(context_parts)
        entity_type = entity.get_entity_type() or "Entity"
        web_context = self.web_enricher.enrich_if_needed(
            entity_name=entity.name,
            entity_type=entity_type,
            existing_context=existing_context,
            simulation_requirement=self.simulation_requirement,
        )
        if web_context:
            context_parts.append(web_context)

        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """Check if this is an individual type entity.

        Uses exact match on known types, then keyword matching on the type name.
        Defaults to True for unknown types (individual is the safer assumption —
        produces richer personas than the institutional template).
        """
        et = entity_type.lower().replace(" ", "")
        # Exact match
        if et in self.INDIVIDUAL_ENTITY_TYPES:
            return True
        # Keyword match (e.g., "CryptoFounder" contains "founder")
        for keyword in self.INDIVIDUAL_TYPE_KEYWORDS:
            if keyword in et:
                return True
        # If it's a known group type, it's not individual
        if self._is_group_entity(entity_type):
            return False
        # Default: treat unknown types as individual (safer)
        return True

    def _is_group_entity(self, entity_type: str) -> bool:
        """Check if this is a group/institutional type entity"""
        et = entity_type.lower().replace(" ", "")
        return et in self.GROUP_ENTITY_TYPES
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        Use LLM to generate very detailed persona

        Differentiated by entity type:
        - Individual entity: Generate specific character profile
        - Group/institutional entity: Generate representative account profile
        """
        
        is_individual = self._is_individual_entity(entity_type)

        # B2B email inbox mode: always generate B2B decision-maker personas
        if self.simulation_type == "email_inbox":
            prompt = self._build_b2b_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        elif is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # Try multiple times until success or max retries reached
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                messages = [
                    {"role": "system", "content": self._get_system_prompt(is_individual)},
                    {"role": "user", "content": prompt}
                ]
                content = self.llm.chat(
                    messages=messages,
                    temperature=0.7 - (attempt * 0.1),
                    response_format={"type": "json_object"},
                )

                # Try to parse JSON
                try:
                    result = json.loads(content)

                    # Validate required fields
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name} is a {entity_type}."

                    return result

                except json.JSONDecodeError as je:
                    logger.warning(f"JSON parsing failed (attempt {attempt+1}): {str(je)[:80]}")

                    # Try to fix JSON
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result

                    last_error = je

            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))  # Exponential backoff
        
        logger.warning(f"LLM persona generation failed ({max_attempts} attempts): {last_error}, using rule-based generation")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """Fix truncated JSON (output truncated by max_tokens limit)"""
        import re
        
        # If JSON is truncated, try to close it
        content = content.strip()

        # Count unclosed brackets
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # Check for unclosed strings
        # Simple check: if there's no comma or closing bracket after the last quote, the string may be truncated
        if content and content[-1] not in '",}]':
            # Try to close the string
            content += '"'
        
        # Close brackets
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """Try to fix corrupted JSON"""
        import re
        
        # 1. First try to fix truncation
        content = self._fix_truncated_json(content)
        
        # 2. Try to extract JSON portion
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. Handle newline issues in strings
            # Find all string values and replace newlines within them
            def fix_string_newlines(match):
                s = match.group(0)
                # Replace actual newlines within strings with spaces
                s = s.replace('\n', ' ').replace('\r', ' ')
                # Replace excess spaces
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # Match JSON string values
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. Try to parse
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. If still failing, try more aggressive fix
                try:
                    # Remove all control characters
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # Replace all consecutive whitespace
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. Try to extract partial information from content
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # May be truncated
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name} is a {entity_type}.")
        
        # If meaningful content was extracted, mark as fixed
        if bio_match or persona_match:
            logger.info(f"Extracted partial information from corrupted JSON")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        # 7. Complete failure, return basic structure
        logger.warning(f"JSON fix failed, returning basic structure")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name} is a {entity_type}."
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """Get system prompt"""
        if is_individual:
            return (
                "You are an expert character writer creating social media personas for a "
                "multi-agent simulation. Your personas must feel like REAL people — messy, "
                "opinionated, contradictory, specific. Avoid generic corporate-speak or "
                "balanced-sounding descriptions. Every person has biases, blind spots, and "
                "strong feelings about something. Lean into those.\n\n"
                "Return valid JSON. All string values must be plain text (no newlines, no markdown). "
                "Use English."
            )
        return (
            "You are an expert in institutional communications creating official social media "
            "account personas for a multi-agent simulation. Institutional accounts have a distinct "
            "voice — formal but not robotic, on-message but not tone-deaf. They hedge on "
            "controversies, amplify achievements, and deflect criticism with practiced diplomacy.\n\n"
            "Return valid JSON. All string values must be plain text (no newlines, no markdown). "
            "Use English."
        )
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Build detailed persona prompt for individual entities"""

        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
        context_str = context[:3000] if context else "No additional context"

        return f"""Create a persona for this person to use in a social media simulation.

ENTITY: {entity_name} ({entity_type})
SUMMARY: {entity_summary}
ATTRIBUTES: {attrs_str}

CONTEXT (from knowledge graph and research):
{context_str}

Return JSON with these fields:

"bio": A punchy social media bio (2-3 sentences). Not a resume — a vibe. What would this person actually write in their Twitter/Reddit bio? Include their attitude, not just their job title.

"persona": A rich character description (800-1200 words). Write this as a character brief for an actor, not a Wikipedia entry. Cover:
- WHO THEY ARE: Background, career, education. But focus on what shaped their worldview, not just facts.
- HOW THEY THINK: Their reasoning style — do they argue from data, emotion, authority, personal experience? Are they charitable to opponents or combative? Do they change their mind easily or dig in?
- WHAT THEY CARE ABOUT: Their 2-3 strongest opinions on the simulation topic. Be specific — not "supports regulation" but "believes self-regulation has failed because of X, and points to Y as evidence."
- THEIR BLIND SPOTS: What are they wrong about, or what do they refuse to consider? Every real person has these.
- ONLINE BEHAVIOR: How they actually post — long threads vs. one-liners, sarcastic vs. earnest, confrontational vs. diplomatic, uses data vs. anecdotes. Do they dunk on people? Do they write essays? Do they meme?
- WHAT WOULD MAKE THEM CHANGE THEIR MIND: What evidence or argument could shift their position? Or are they unmovable on this topic?

"age": Integer
"gender": "male" or "female"
"mbti": MBTI type (e.g., "INTJ")
"country": Country name
"profession": Their job title or role
"interested_topics": ["topic1", "topic2", ...] (3-6 topics)

IMPORTANT: Do NOT include karma, friend_count, follower_count, or statuses_count — those are computed separately.
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Build detailed persona prompt for group/institutional entities"""

        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
        context_str = context[:3000] if context else "No additional context"

        return f"""Create an official social media account persona for this organization.

ENTITY: {entity_name} ({entity_type})
SUMMARY: {entity_summary}
ATTRIBUTES: {attrs_str}

CONTEXT (from knowledge graph and research):
{context_str}

Return JSON with these fields:

"bio": The official account bio (2-3 sentences). Professional but not boring. Think real organizational Twitter bios — they have personality within institutional constraints.

"persona": A communications playbook for this account (600-900 words). This is a guide for how the account behaves online:
- INSTITUTIONAL IDENTITY: What is this organization, and what is its public mission? What image does it project?
- OFFICIAL POSITION: Where does this organization stand on the simulation topic? What's the official line? How do they frame it?
- VOICE AND TONE: Formal vs. accessible? Does it use jargon or plain language? First person plural ("we believe") or third person ("the organization maintains")? Does it show personality or stay buttoned-up?
- CONTENT STRATEGY: What does this account actually post? Press releases, data, opinion pieces, event promotion? Does it engage in debates or just broadcast?
- CONTROVERSY HANDLING: How does it respond to criticism? Ignore, deflect, address head-on, or issue a carefully worded non-response?
- RED LINES: What will this account never say or do? What positions would be off-brand?

"age": 30
"gender": "other"
"mbti": MBTI type reflecting the account's communication style. VARY THIS — not all orgs are ISTJ. \
Examples: "ISTJ" (conservative, by-the-book), "ENTJ" (assertive, agenda-setting), "ENFJ" (community-building, outreach), \
"INTP" (technical, research-focused), "ESTP" (bold, action-oriented)
"country": Country where headquartered
"profession": Brief description of institutional function
"interested_topics": ["topic1", "topic2", ...] (3-6 focus areas)

IMPORTANT: Do NOT include karma, friend_count, follower_count, or statuses_count — those are computed separately.
"""
    
    def _build_b2b_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """Build B2B decision-maker persona prompt for email inbox simulation.

        Generates an HR Director / Head of People persona at a Spanish SME
        with B2B-specific traits that determine cold email response behavior.
        """
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
        context_str = context[:3000] if context else "No additional context"

        return f"""Create a B2B decision-maker persona for an email inbox simulation.
This persona represents an HR Director or Head of People at a Spanish SME (80-150 employees).

SOURCE ENTITY: {entity_name} ({entity_type})
ENTITY SUMMARY: {entity_summary}
ATTRIBUTES: {attrs_str}

CONTEXT (from ICP profile and knowledge graph):
{context_str}

SIMULATION GOAL: {self.simulation_requirement[:500] if self.simulation_requirement else "B2B cold email copy variant testing"}

Return JSON with these fields:

"bio": Short professional bio (2 sentences). Real LinkedIn bio style — specific title, company type, years experience.

"persona": Character description for the simulation (400-600 words). Include:
- Current role and company context (what kind of company, how many employees, growth stage)
- L&D/training situation: Do they have a dedicated L&D team? How is training currently handled?
- Top 3 work pressures RIGHT NOW (hiring, retention, skills gap, compliance, etc.)
- Relationship with technology: Are they a digital adopter or cautious about new tools?
- Typical day: When do they check email? How much time do they have for vendors?
- Cold email behavior: How do they handle cold outreach? What makes them stop and read?

"age": Age (35-55 realistic range for this role)
"gender": "male" or "female"
"mbti": MBTI type (VARY this — common types in HR: ENFJ, ISFJ, ESTJ, ENFP, ENTJ)
"country": "Spain"
"profession": Exact job title (e.g. "HR Director", "Head of People", "People & Culture Manager")
"interested_topics": ["talent development", "employee retention", ...] (4-6 specific topics)

"budget_authority": true if they can approve L&D spend directly, false if they need CFO/CEO sign-off
"cold_email_skepticism": float 0.0-1.0 (0.7-0.9 realistic for busy HR Directors)
"inbox_habit": one of "morning_scanner", "batch_processor", "responsive"
"pain_signal_sensitivity": object mapping pain types to sensitivity (0.0-1.0):
  {{
    "skills_gap": 0.8,
    "employee_retention": 0.7,
    "onboarding_inefficiency": 0.6,
    "no_l&d_team": 0.9,
    "hiring_cost": 0.5,
    "manager_development": 0.6
  }}
"decision_style": one of "roi_driven", "risk_averse", "early_adopter", "social_proof"

IMPORTANT: Vary the personas meaningfully. Not all HR Directors are the same.
Some are overwhelmed solo HR in a fast-growing startup. Others are seasoned professionals
at established companies with clear L&D gaps. Make each one a real person.
Do NOT include karma, friend_count, follower_count, or statuses_count.
"""

    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate basic persona using rules"""

        # Generate different personas based on entity type
        entity_type_lower = entity_type.lower()
        
        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic and social discussions. They enjoy sharing perspectives and connecting with peers.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }
        
        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": f"Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {entity_type.lower()} who shares insights and opinions on important matters. They are known for their expertise and influence in public discourse.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }
        
        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity that reports news and facilitates public discourse. The account shares timely updates and engages with the audience on current events.",
                "age": 30,  # Virtual age for institutions
                "gender": "other",  # Institutions use other
                "mbti": "ISTJ",  # Institutional style: rigorous and conservative
                "country": "China",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }

        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions, announcements, and engages with stakeholders on relevant matters.",
                "age": 30,  # Virtual age for institutions
                "gender": "other",  # Institutions use other
                "mbti": "ISTJ",  # Institutional style: rigorous and conservative
                "country": "China",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }
        
        else:
            # Default persona
            return {
                "bio": entity_summary[:500] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name} is a {entity_type.lower()} participating in social discussions.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }
    
    def set_graph_id(self, graph_id: str):
        """Set knowledge graph ID for knowledge graph search"""
        self.graph_id = graph_id

    @staticmethod
    def _interleave_by_type(entities: list) -> list:
        """Reorder entities to interleave types for diverse early results.

        Instead of [Org, Org, Org, Person, Person], produces
        [Person, Org, Person, Org, Org] — round-robin by type.
        """
        from collections import defaultdict
        buckets = defaultdict(list)
        for e in entities:
            etype = (e.get_entity_type() or "Entity").lower()
            buckets[etype].append(e)

        # Sort buckets so individual types come first (more interesting personas)
        individual_keys = []
        group_keys = []
        for key in buckets:
            if key in ("person", "publicfigure", "expert", "faculty", "student",
                       "alumni", "journalist", "activist", "politician", "official",
                       "cryptofounder", "electionforecaster", "predictionmarketuser",
                       "cryptoinfluencer", "regulatoryofficial"):
                individual_keys.append(key)
            else:
                group_keys.append(key)

        ordered_keys = individual_keys + group_keys
        # Add any keys not in either list
        for key in buckets:
            if key not in ordered_keys:
                ordered_keys.append(key)

        # Round-robin interleave
        result = []
        iterators = {k: iter(buckets[k]) for k in ordered_keys}
        while iterators:
            exhausted = []
            for key in ordered_keys:
                if key not in iterators:
                    continue
                try:
                    result.append(next(iterators[key]))
                except StopIteration:
                    exhausted.append(key)
            for key in exhausted:
                del iterators[key]

        return result

    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 15,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        Batch generate Agent Profiles from entities (supports parallel generation)

        Args:
            entities: List of entities
            use_llm: Whether to use LLM for detailed persona generation
            progress_callback: Progress callback function (current, total, message)
            graph_id: Knowledge graph ID for knowledge graph search to get richer context
            parallel_count: Number of parallel generations, default 5
            realtime_output_path: File path for real-time writing (if provided, writes after each generation)
            output_platform: Output platform format ("reddit" or "twitter")

        Returns:
            List of Agent Profiles
        """
        import concurrent.futures
        from threading import Lock
        
        # Set graph_id for knowledge graph search
        if graph_id:
            self.graph_id = graph_id

        # Interleave entity types for diverse early results
        # (instead of all orgs first, then all people)
        entities = self._interleave_by_type(entities)

        total = len(entities)
        profiles = [None] * total  # Pre-allocate list to maintain order
        completed_count = [0]  # Use list so it can be modified in closure
        lock = Lock()

        # Helper function for real-time file writing
        def save_profiles_realtime():
            """Save generated profiles to file in real time"""
            if not realtime_output_path:
                return

            with lock:
                # Filter out generated profiles
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return

                try:
                    if output_platform == "reddit":
                        # Reddit JSON format
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV format
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"Failed to save profiles in real time: {e}")
        
        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """Worker function to generate a single profile"""
            entity_type = entity.get_entity_type() or "Entity"

            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )

                # Output generated persona to console and log in real time
                self._print_generated_profile(entity.name, entity_type, profile)

                return idx, profile, None

            except Exception as e:
                logger.error(f"Failed to generate persona for entity {entity.name}: {str(e)}")
                # Create a fallback profile
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"Starting parallel generation of {total} Agent personas (parallelism: {parallel_count})...")
        print(f"\n{'='*60}")
        print(f"Starting Agent persona generation - {total} entities, parallelism: {parallel_count}")
        print(f"{'='*60}\n")

        # Use thread pool for parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # Submit all tasks
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"

                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile

                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]

                    # Write to file in real time
                    save_profiles_realtime()

                    if progress_callback:
                        progress_callback(
                            current,
                            total,
                            f"Completed {current}/{total}: {entity.name} ({entity_type})"
                        )

                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} using fallback persona: {error}")
                    else:
                        logger.info(f"[{current}/{total}] Successfully generated persona: {entity.name} ({entity_type})")

                except Exception as e:
                    logger.error(f"Exception while processing entity {entity.name}: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # Write to file in real time (even for fallback personas)
                    save_profiles_realtime()

        print(f"\n{'='*60}")
        print(f"Persona generation complete! Generated {len([p for p in profiles if p])} Agents")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """Output generated persona to console in real time (full content, no truncation)"""
        separator = "-" * 70

        # Build full output content (no truncation)
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else 'None'

        output_lines = [
            f"\n{separator}",
            f"[Generated] {entity_name} ({entity_type})",
            f"{separator}",
            f"Username: {profile.user_name}",
            f"",
            f"[Bio]",
            f"{profile.bio}",
            f"",
            f"[Detailed Persona]",
            f"{profile.persona}",
            f"",
            f"[Basic Attributes]",
            f"Age: {profile.age} | Gender: {profile.gender} | MBTI: {profile.mbti}",
            f"Profession: {profile.profession} | Country: {profile.country}",
            f"Interested Topics: {topics_str}",
            separator
        ]

        output = "\n".join(output_lines)

        # Only output to console (avoid duplication, logger no longer outputs full content)
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        Save profiles to file (choose correct format based on platform).

        OASIS platform format requirements:
        - Twitter: CSV format
        - Reddit: JSON format (default)

        Args:
            profiles: List of profiles
            file_path: File path
            platform: Platform type ("twitter" or "reddit")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Save Twitter Profile as CSV format (compliant with OASIS official requirements)

        OASIS Twitter required CSV fields:
        - user_id: User ID (sequential from 0 based on CSV order)
        - name: User's real name
        - username: System username
        - user_char: Detailed persona description (injected into LLM system prompt to guide Agent behavior)
        - description: Short public bio (displayed on user profile page)

        user_char vs description distinction:
        - user_char: Internal use, LLM system prompt, determines how Agent thinks and acts
        - description: External display, bio visible to other users
        """
        import csv
        
        # Ensure file extension is .csv
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write OASIS required headers
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            # Write data rows
            for idx, profile in enumerate(profiles):
                # user_char: Full persona (bio + persona), for LLM system prompt
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # Handle newlines (replace with spaces in CSV)
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')

                # description: Short bio, for external display
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')

                row = [
                    idx,                    # user_id: Sequential ID starting from 0
                    profile.name,           # name: Real name
                    profile.user_name,      # username: Username
                    user_char,              # user_char: Full persona (internal LLM use)
                    description             # description: Short bio (external display)
                ]
                writer.writerow(row)
        
        logger.info(f"Saved {len(profiles)} Twitter Profiles to {file_path} (OASIS CSV format)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        Normalize gender field to OASIS required English format

        OASIS requires: male, female, other
        """
        if not gender:
            return "other"

        gender_lower = gender.lower().strip()

        # Gender mapping
        gender_map = {
            "male": "male",
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        Save Reddit Profile as JSON format

        Uses the same format as to_reddit_format(), ensuring OASIS can read correctly.
        Must include user_id field, which is key for OASIS agent_graph.get_agent() matching!

        Required fields:
        - user_id: User ID (integer, used to match poster_agent_id in initial_posts)
        - username: Username
        - name: Display name
        - bio: Bio
        - persona: Detailed persona
        - age: Age (integer)
        - gender: "male", "female", or "other"
        - mbti: MBTI type
        - country: Country
        """
        data = []
        for idx, profile in enumerate(profiles):
            # Use the same format as to_reddit_format()
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,  # Critical: must include user_id
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:500] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is a participant in social discussions.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS required fields - ensure all have default values
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "China",
            }

            # Optional fields
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(profiles)} Reddit Profiles to {file_path} (JSON format, includes user_id field)")

    # Keep old method name as alias for backward compatibility
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[Deprecated] Please use save_profiles() method"""
        logger.warning("save_profiles_to_json is deprecated, please use save_profiles method")
        self.save_profiles(profiles, file_path, platform)

