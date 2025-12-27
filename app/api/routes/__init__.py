from .customers import router as customers_router
from .documents import router as documents_router
from .user import router as user_router
from .roles import router as role_router
from .user_auction import router as user_auction_router
from .watchlist import router as watchlist_router
from .copart_router import router as copart_route
from .iaai_router import router as iaai_route
from .audit_logs import router as audit_router
from .bot_sessions import router as bot_session_router
from .debug import router as debug_router

from .lot import router as lot_router
from .translation import router as trans_router
from .lead import router as lead_router
from .nhts import router as nhts_router
from .task import router as task_router
from .additional import router as additional_router
from .admin import router as admin_router
from .admin_marketplace import router as admin_marketplace_router
from .marketplace import router as marketplace_router
from .calculator import router as calculator_router

# New routes
from .profile import router as profile_router
from .deposits import router as deposits_router
from .transactions import router as transactions_router
from .notifications import router as notifications_router
from .two_factor import router as two_factor_router
from .websocket import router as websocket_router