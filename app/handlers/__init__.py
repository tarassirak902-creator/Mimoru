"""Handler package bootstrap for shared router composition."""

# Keep the reversible setup wizard attached to the early navigation router.
# main.py already registers navigation_fixes before the legacy onboarding router,
# so these callbacks win without changing the established router order.
from app.handlers import navigation_fixes, wizard_navigation

# The existing setup:start handler lives in navigation_fixes and calls this
# helper at runtime. Point it at the reversible wizard entry keyboard so every
# new setup session follows the contextual back-navigation flow.
navigation_fixes._setup_profile_menu = wizard_navigation._profile_menu
navigation_fixes.router.include_router(wizard_navigation.router)
