import logging
from abc import ABC, abstractmethod

from models import Product


class Grabber(ABC):
    """
    An abstract base class for grabbers.

    A grabber is responsible for fetching product data from a source.
    """
    @abstractmethod
    async def grab(self) -> list[Product]: ...


class Client(ABC):
    """
    An abstract base class for clients.

    A client is responsible for interacting with an API to send product data.
    """
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def auth(self) -> None: ...

    @abstractmethod
    async def send_data(self, data: any) -> None: ...


class App:
    """
    The main application class.

    This class coordinates the grabber and client to fetch product data and send it to the API.
    """
    def __init__(self, grabber: Grabber, client: Client):
        """
        Initializes the App instance.

        Args:
            grabber (Grabber): The grabber instance to use.
            client (Client): The client instance to use.
        """
        self.grabber = grabber
        self.client = client

    async def run(self):
        """
        Runs the application.

        This method starts the client, authenticates, grabs product data, sends it to the API, and stops the client.
        """
        try:
            data: list[Product] = await self.grabber.grab()
            
            await self.client.start()
            await self.client.auth()
            await self.client.send_data(data)

        except Exception as e:
            logging.fatal(f"app error: {e}")
        finally:
            await self.client.stop()
