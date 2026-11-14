"""Sensors for the Livoltek Local integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LivoltekConfigEntry, LivoltekCoordinator
from .livoltek import LivoltekData


@dataclass(frozen=True, kw_only=True)
class LivoltekSensorDescription(SensorEntityDescription):
    """Describe a Livoltek sensor."""

    value_fn: Callable[[LivoltekData], Any]


def _power(key: str, fn: Callable[[LivoltekData], Any]) -> LivoltekSensorDescription:
    return LivoltekSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=fn,
    )


def _voltage(key: str, fn: Callable[[LivoltekData], Any]) -> LivoltekSensorDescription:
    return LivoltekSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=fn,
    )


def _current(key: str, fn: Callable[[LivoltekData], Any]) -> LivoltekSensorDescription:
    return LivoltekSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=fn,
    )


SENSORS: tuple[LivoltekSensorDescription, ...] = (
    _power("ac_power", lambda d: d.ac_power),
    LivoltekSensorDescription(
        key="energy_today",
        translation_key="energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        value_fn=lambda d: d.energy_today,
    ),
    LivoltekSensorDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        value_fn=lambda d: d.frequency,
    ),
    _voltage("pv1_voltage", lambda d: d.pv1_voltage),
    _current("pv1_current", lambda d: d.pv1_current),
    _power("pv1_power", lambda d: d.pv1_power),
    _voltage("pv2_voltage", lambda d: d.pv2_voltage),
    _current("pv2_current", lambda d: d.pv2_current),
    _power("pv2_power", lambda d: d.pv2_power),
    LivoltekSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.temperature,
    ),
    LivoltekSensorDescription(
        key="status",
        translation_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.status,
    ),
    LivoltekSensorDescription(
        key="power_factor",
        translation_key="power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda d: d.power_factor,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: LivoltekConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(LivoltekSensor(coordinator, description) for description in SENSORS)


class LivoltekSensor(CoordinatorEntity[LivoltekCoordinator], SensorEntity):
    """Livoltek inverter sensor."""

    _attr_has_entity_name = True
    entity_description: LivoltekSensorDescription

    def __init__(self, coordinator: LivoltekCoordinator, description: LivoltekSensorDescription) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name="Inversor",
            manufacturer="Livoltek",
            model="Grid-tie inverter (Modbus TCP via HF-LPB130)",
            configuration_url=f"http://{entry.data[CONF_HOST]}/",
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
