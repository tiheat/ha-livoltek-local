"""Constants for the Livoltek Local integration."""

from __future__ import annotations

DOMAIN = "livoltek_local"

CONF_UNIT_ID = "unit_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
# One request per minute keeps the Wi-Fi module free to upload to the Livoltek cloud.
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 600

REQUEST_TIMEOUT = 5.0
