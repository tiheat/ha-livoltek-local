"""Livoltek Local: read a Livoltek grid-tie inverter over Modbus TCP through its Wi-Fi module."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import LivoltekConfigEntry, LivoltekCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LivoltekConfigEntry) -> bool:
    """Set up a Livoltek inverter entry."""
    coordinator = LivoltekCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LivoltekConfigEntry) -> bool:
    """Unload an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
