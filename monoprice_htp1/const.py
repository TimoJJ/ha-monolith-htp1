"""Constants for the Monoprice HTP-1 integration."""

import logging

DOMAIN = "monoprice_htp1"
LOGGER = logging.getLogger(DOMAIN)

def ui_lock_signal(entry_id: str) -> str:
    """Dispatcher signal used to refresh entity availability when UI lock toggles."""
    return f"{DOMAIN}_{entry_id}_ui_lock"
