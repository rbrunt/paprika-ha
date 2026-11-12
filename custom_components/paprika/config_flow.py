"""Config flow for the Paprika integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_EMAIL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)


from .api import PaprikaApi, PaprikaAuthenticationError
from .const import CONF_RECIPE_FORMAT, DEFAULT_RECIPE_FORMAT, DOMAIN, RECIPE_FORMATS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    try:
        token = await PaprikaApi.login(data[CONF_EMAIL], data[CONF_PASSWORD])
        return {"token": token, "title": data[CONF_EMAIL]}
    except PaprikaAuthenticationError:
        raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth
    


class PaprikaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Paprika."""

    VERSION = 1
    MINOR_VERSION = 0

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> PaprikaOptionsFlow:
        """Get the options flow for this handler."""
        return PaprikaOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data={"token": info["token"]})

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class PaprikaOptionsFlow(OptionsFlowWithReload):
    """Handle Paprika options. Saving reloads the entry so the change applies."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RECIPE_FORMAT,
                        default=self.config_entry.options.get(
                            CONF_RECIPE_FORMAT, DEFAULT_RECIPE_FORMAT
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=RECIPE_FORMATS,
                            translation_key=CONF_RECIPE_FORMAT,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
