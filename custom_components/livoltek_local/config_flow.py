"""Config and options flow for the Livoltek Local integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    REQUEST_TIMEOUT,
)
from .livoltek import LivoltekConnectionError, LivoltekError, LivoltekModbusError, async_read

SCAN_INTERVAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL, step=10, mode=NumberSelectorMode.BOX, unit_of_measurement="s"
    )
)


async def _probe(host: str, port: int, unit_id: int) -> str | None:
    """Return an error key, or None when the Wi-Fi module answered."""
    try:
        await async_read(host, port, unit_id, REQUEST_TIMEOUT)
    except LivoltekModbusError:
        # The module answered but the inverter did not (normal at night): the address is right.
        return None
    except LivoltekConnectionError:
        return "cannot_connect"
    except LivoltekError:
        return "invalid_response"
    return None


class LivoltekLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the Wi-Fi module address."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            unit_id = int(user_input[CONF_UNIT_ID])
            await self.async_set_unique_id(f"{host}:{port}:{unit_id}")
            self._abort_if_unique_id_configured()
            error = await _probe(host, port, unit_id)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=f"Inversor Livoltek ({host})",
                    data={CONF_HOST: host, CONF_PORT: port, CONF_UNIT_ID: unit_id},
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                )

        defaults = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): TextSelector(),
                vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)): NumberSelector(
                    NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> LivoltekLocalOptionsFlow:
        """Return the options flow."""
        return LivoltekLocalOptionsFlow()


class LivoltekLocalOptionsFlow(OptionsFlowWithReload):
    """Change how often the inverter is read."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the polling interval."""
        if user_input is not None:
            return self.async_create_entry(data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])})
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        schema = vol.Schema({vol.Required(CONF_SCAN_INTERVAL, default=current): SCAN_INTERVAL_SELECTOR})
        return self.async_show_form(step_id="init", data_schema=schema)
