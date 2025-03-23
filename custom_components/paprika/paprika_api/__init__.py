import json
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)

class PaprikaApi:

    def __init__(self, token: str):
        _LOGGER.info("Setting up client")
        self.access_token = token
        self.session = aiohttp.ClientSession("https://www.paprikaapp.com/api/v2/")
        self.session.headers["authorization"] = f"Bearer {self.access_token}"
    
    @classmethod
    async def login(cls, email: str, password: str):
        """Use a username and password to get a token that can be used to initialise the client for other calls."""
        async with aiohttp.ClientSession() as session: 
            response = await session.post("https://paprikaapp.com/api/v1/account/login", data={"email": email, "password": password})
            json_response =  await response.json()
            # TODO: remove this once confirmed working:
            _LOGGER.warning(json.dumps(json_response))
            return json_response["result"]["token"]

