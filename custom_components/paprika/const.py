"""Constants for the Paprika integration."""

DOMAIN = "paprika"

# Option: how each planned meal's recipe is put in its calendar event description
CONF_RECIPE_FORMAT = "recipe_format"
RECIPE_FORMAT_NONE = "none"
RECIPE_FORMAT_HTML = "html"
RECIPE_FORMATS = [RECIPE_FORMAT_NONE, RECIPE_FORMAT_HTML]
DEFAULT_RECIPE_FORMAT = RECIPE_FORMAT_NONE
