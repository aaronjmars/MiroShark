"""
Configuration management
Loads configuration uniformly from the .env file in the project root directory
"""

import os
from dotenv import load_dotenv

# Load the .env file from the project root directory
# Path: MiroShark/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # If no .env in root directory, try loading environment variables (for production)
    load_dotenv(override=True)


class Config:
    """Flask configuration class"""

    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'miroshark-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON configuration - disable ASCII escaping, display non-ASCII characters directly (instead of \uXXXX format)
    JSON_AS_ASCII = False
    
    # LLM configuration (unified OpenAI format)
    # LLM_PROVIDER: "openai" (default, any OpenAI-compatible API) or "claude-code" (local CLI)
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'openai')
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # Smart model — optional stronger model for intelligence-sensitive workflows
    # (report generation, ontology extraction, graph reasoning).
    # When not set, these workflows use the default LLM config above.
    SMART_PROVIDER = os.environ.get('SMART_PROVIDER', '')   # "openai", "claude-code", or empty (inherit)
    SMART_API_KEY = os.environ.get('SMART_API_KEY', '')
    SMART_BASE_URL = os.environ.get('SMART_BASE_URL', '')
    SMART_MODEL_NAME = os.environ.get('SMART_MODEL_NAME', '')
    
    # Neo4j configuration
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'miroshark')

    # Embedding configuration
    # EMBEDDING_PROVIDER: "ollama" (default) uses /api/embed, "openai" uses /v1/embeddings
    EMBEDDING_PROVIDER = os.environ.get('EMBEDDING_PROVIDER', 'ollama')
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'nomic-embed-text')
    EMBEDDING_BASE_URL = os.environ.get('EMBEDDING_BASE_URL', 'http://localhost:11434')
    EMBEDDING_API_KEY = os.environ.get('EMBEDDING_API_KEY', '')
    EMBEDDING_DIMENSIONS = int(os.environ.get('EMBEDDING_DIMENSIONS', '768'))
    
    # File upload configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # Text processing configuration
    DEFAULT_CHUNK_SIZE = 1000  # Default chunk size (doubled from 500 for fewer NER calls + better context)
    DEFAULT_CHUNK_OVERLAP = 50  # Default overlap size
    
    # Wonderwall simulation configuration
    WONDERWALL_DEFAULT_MAX_ROUNDS = int(os.environ.get('WONDERWALL_DEFAULT_MAX_ROUNDS', '10'))
    WONDERWALL_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    # Wonderwall platform available actions configuration
    WONDERWALL_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    WONDERWALL_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    WONDERWALL_POLYMARKET_ACTIONS = [
        'browse_markets', 'buy_shares', 'sell_shares',
        'view_portfolio', 'create_market', 'comment_on_market', 'do_nothing'
    ]
    # Email inbox simulation actions (prospect-sim B2B copy variant testing)
    WONDERWALL_INBOX_ACTIONS = [
        'open_email', 'read_email', 'reply', 'forward', 'archive', 'do_nothing'
    ]
    
    # Web Enrichment — LLM-powered research for persona generation
    # Triggers for notable figures (politicians, CEOs, etc.) or when graph context is thin
    WEB_ENRICHMENT_ENABLED = os.environ.get('WEB_ENRICHMENT_ENABLED', 'true').lower() == 'true'
    # Optional: dedicated model for web research (e.g. "perplexity/sonar-pro" on OpenRouter
    # for grounded search, or "perplexity/sonar" for fast search). If empty, uses default LLM.
    WEB_SEARCH_MODEL = os.environ.get('WEB_SEARCH_MODEL', '')

    # NER model — optional faster model for entity extraction (high-volume, mechanical task)
    # When not set, NER uses the default LLM config above.
    NER_MODEL_NAME = os.environ.get('NER_MODEL_NAME', '')
    NER_BASE_URL = os.environ.get('NER_BASE_URL', '')
    NER_API_KEY = os.environ.get('NER_API_KEY', '')

    # Observability configuration
    MIROSHARK_LOG_PROMPTS = os.environ.get('MIROSHARK_LOG_PROMPTS', 'false').lower() == 'true'
    MIROSHARK_LOG_LEVEL = os.environ.get('MIROSHARK_LOG_LEVEL', 'info')  # debug|info|warn

    # Report Agent configuration
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        if cls.LLM_PROVIDER != 'claude-code' and not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY is not configured")
        if not cls.NEO4J_URI:
            errors.append("NEO4J_URI is not configured")
        if not cls.NEO4J_PASSWORD:
            errors.append("NEO4J_PASSWORD is not configured")
        return errors

