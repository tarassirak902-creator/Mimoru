"""Handler package bootstrap for shared router composition."""

# Keep the reversible setup wizard attached to the early navigation router.
# main.py already registers navigation_fixes before the legacy onboarding router,
# so these callbacks win without changing the established router order.
from app.handlers import navigation_fixes, wizard_navigation

navigation_fixes.router.include_router(wizard_navigation.router)
