"""Provides number entities for ConnectLife."""

import logging
from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ConnectLifeCoordinator
from .dictionaries import Dictionaries, Dictionary, Property
from .entity import ConnectLifeEntity
from connectlife.api import LifeConnectError
from connectlife.appliance import ConnectLifeAppliance
from .utils import is_entity, to_unit

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ConnectLife number entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    for appliance in coordinator.data.values():
        dictionary = Dictionaries.get_dictionary(appliance)
        async_add_entities(
            ConnectLifeNumberEntity(
                coordinator,
                appliance,
                s,
                dictionary.properties[s],
                config_entry,
                dictionary,
            )
            for s in appliance.status_list
            if is_entity(
                Platform.NUMBER, dictionary.properties[s], appliance.status_list[s]
            )
        )


class ConnectLifeNumberEntity(ConnectLifeEntity, NumberEntity):
    """Number entities for ConnectLife writeable numeric properties."""

    _attr_native_step = 1

    def __init__(
        self,
        coordinator: ConnectLifeCoordinator,
        appliance: ConnectLifeAppliance,
        status: str,
        dd_entry: Property,
        config_entry: ConfigEntry,
        dictionary: Dictionary,
    ):
        """Initialize the entity."""
        super().__init__(coordinator, appliance, status, Platform.NUMBER, config_entry)
        self.status = status
        device_class = dd_entry.number.device_class
        self.entity_description = NumberEntityDescription(
            key=self._attr_unique_id,
            device_class=device_class,
            entity_registry_visible_default=not dd_entry.hide,
            icon=dd_entry.icon,
            name=status.replace("_", " "),
            native_max_value=dd_entry.number.max_value,
            native_min_value=dd_entry.number.min_value,
            native_unit_of_measurement=to_unit(
                dd_entry.number.unit, appliance=appliance, dictionary=dictionary
            ),
            translation_key=self.to_translation_key(status),
            entity_category=dd_entry.entity_category,
        )
        self.update_state()

    @callback
    def update_state(self):
        if self.status in self.coordinator.data[self.device_id].status_list:
            value = self.coordinator.data[self.device_id].status_list[self.status]
            self._attr_native_value = value
        self._attr_available = self.coordinator.data[self.device_id].offline_state == 1

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        value = int(value)
        _LOGGER.debug("Setting %s to %d on %s", self.status, value, self.nickname)
        try:
            await self.async_update_device({self.status: value})
        except LifeConnectError as api_error:
            raise ServiceValidationError(str(api_error)) from api_error
