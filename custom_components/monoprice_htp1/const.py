"""Constants for the Monoprice HTP-1 integration."""

import logging

DOMAIN = "monoprice_htp1"
LOGGER = logging.getLogger(DOMAIN)

def ui_lock_signal(entry_id: str) -> str:
    """Dispatcher signal used to refresh entity availability when UI lock toggles."""
    return f"{DOMAIN}_{entry_id}_ui_lock"

# Dirac filter types as stored in /cal/slots/N/filterType.
# Full names for the sensor, short names as the WebUI shows them (RC/BM/BC/ART).
DIRAC_FILTER_NAMES = {
    "Dirac Live": "Dirac Live",
    "Dirac Live Bass Management": "Bass Management",
    "Dirac Live Bass Control": "Bass Control",
    "Dirac Active Room Treatment": "Active Room Treatment",
}
DIRAC_FILTER_SHORT = {
    "Dirac Live": "RC",
    "Dirac Live Bass Management": "BM",
    "Dirac Live Bass Control": "BC",
    "Dirac Active Room Treatment": "ART",
}
