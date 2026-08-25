#!/usr/bin/env sh
set -eu
python -m compileall -q app alembic tests
ruff check app tests scripts alembic --select E9,F63,F7,F82
pytest -q
python scripts/check_migrations.py
python scripts/check_schema_consistency.py
python scripts/check_router_registration.py
python scripts/check_deployment_consistency.py
python scripts/check_security_baseline.py
python scripts/check_operational_resilience.py
python scripts/check_functionality_surface.py
python scripts/check_callback_coverage.py
python scripts/check_release_consistency.py
python scripts/audit_navigation_buttons.py
python scripts/audit_all_buttons.py
python scripts/audit_fsm_states.py
python scripts/check_codebase_integrity.py
python scripts/audit_handler_contracts.py
