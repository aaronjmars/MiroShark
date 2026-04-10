"""
API Routes Module
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)
templates_bp = Blueprint('templates', __name__)
settings_bp = Blueprint('settings', __name__)
observability_bp = Blueprint('observability', __name__)
runs_bp = Blueprint('runs', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401
from . import templates  # noqa: E402, F401
from . import settings  # noqa: E402, F401
from . import observability  # noqa: E402, F401
from . import runs  # noqa: E402, F401

