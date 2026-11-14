"""Data update coordinator for the Livoltek Local integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SCAN_INTERVAL, CONF_UNIT_ID, DEFAULT_SCAN_INTERVAL, DOMAIN, REQUEST_TIMEOUT
from .livoltek import LivoltekData, LivoltekError, async_read

_LOGGER = logging.getLogger(__name__)

type LivoltekConfigEntry = ConfigEntry[LivoltekCoordinator]


class LivoltekCoordinator(DataUpdateCoordinator[LivoltekData]):
    """Read the inverter with a single Modbus request per update."""

    config_entry: LivoltekConfigEntry

    def __init__(self, hass: HomeAssistant, entry: LivoltekConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        )

    async def _async_update_data(self) -> LivoltekData:
        data = self.config_entry.data
        try:
            return await async_read(data[CONF_HOST], data[CONF_PORT], data[CONF_UNIT_ID], REQUEST_TIMEOUT)
        except LivoltekError as err:
            # Expected at night: the inverter switches off and the Wi-Fi module stops answering for it.
            raise UpdateFailed(f"Could not read the inverter: {err}") from err
