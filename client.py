import asyncio
import logging
import os
from random import sample
import string
import uuid

from aiohttp import ClientSession

from models import Product


class ShopwareClient:
    """
    A client for interacting with the Shopware API.

    Attributes:
        session (ClientSession): The aiohttp client session.
        url (str): The base URL of the Shopware API.
        currencies (dict): A dictionary of currency IDs, keyed by symbol.
        categories (dict): A dictionary of category IDs, keyed by name.
        taxes (dict): A dictionary of tax IDs, keyed by name.
    """

    session: ClientSession

    refresh_token: str
    exp: int

    def __init__(self, url: str):
        """
        Initializes the ShopwareClient instance.

        Args:
            url (str): The base URL of the Shopware API.
        """
        self.url = url
        self.sales_channel_id = os.getenv("SALES_CHANNEL_ID")
        self.currencies = dict()
        self.categories = dict()
        self.taxes = dict()
        self.media_folders = dict()

    async def start(self) -> None:
        """
        Starts the aiohttp client session.
        """
        self.session = ClientSession(self.url)
        self.session.headers["Content-Type"] = "application/json"

    async def stop(self) -> None:
        """
        Closes the aiohttp client session.
        """
        await self.session.close()

    async def auth(self) -> None:
        """
        Authenticates with the Shopware API using OAuth.

        Raises:
            Exception: If authentication fails.
        """

        suffix = "/api/oauth/token"

        data = {
            "client_id": "administration",
            "grant_type": "password",
            "username": os.getenv("SHOPWARE_USERNAME"),
            "password": os.getenv("SHOPWARE_PASSWORD"),
        }

        response = await self.session.post(suffix, json=data)
        content = await response.json()

        if response.status != 200:
            logging.error(f"error when authenticating in shopware: {content}")
            raise Exception("shopware auth error")

        self.session.headers["Authorization"] = (
            f"{content.get('token_type')} {content.get('access_token')}"
        )
        self.exp = content.get("expires_in") - 10
        self.refresh_token = content.get("refresh_token")

    async def refresh(self) -> None:
        """
        Refresh the token
        """
        suffix = "/api/oauth/token"

        while True:
            await asyncio.sleep(self.exp)
            data = {
                "client_id": "administration",
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            }

            response = await self.session.post(suffix, json=data)
            content = await response.json()

            if response.status != 200:
                logging.error(f"error when refresh the token: {content}")
                raise Exception("shopware refresh error")

            self.session.headers["Authorization"] = (
                f"{content.get('token_type')} {content.get('access_token')}"
            )
            self.refresh_token = content.get("refresh_token")

    async def send_data(self, data: list[Product]) -> None:
        """
        Sends product data to the Shopware API.

        Args:
            data (list[Product]): A list of Product instances to send.

        Raises:
            Exception: If sending data fails.
        """
        suffix = "/api/product"

        task = asyncio.create_task(self.refresh())

        for product in data:
            try:
                product_data = await self._product_data(product)
                if product_data is None:
                    continue

                product_id = await self._get_product_id(product_data.get("name"))
                if product_id is None:
                    logging.info("send create product")
                    logging.debug(f"send create request with data: {product_data}")
                    product_data["visibilities"] = [
                        {"salesChannelId": self.sales_channel_id, "visibility": 30},
                    ]
                    response = await self.session.post(url=suffix, json=product_data)
                else:
                    logging.info(f"send update product where id is {product_id}")
                    logging.debug(
                        f"send update request where product id is {product_id} with data: {product_data}"
                    )
                    del product_data["productNumber"]
                    response = await self.session.patch(
                        url=suffix + "/" + product_id, json=product_data
                    )

                if response.status != 204:
                    content = await response.json()
                    logging.error(
                        f"(status {response.status}) error when send product data: {content}"
                    )

            except Exception as e:
                logging.error(f"error when create product data | skip: {e}")
                continue

        task.cancel()

    async def _product_data(self, product: Product) -> dict:
        """
        Converts a Product instance to a dictionary.

        Args:
            product (Product): The Product instance to convert.

        Returns:
            dict: The product data as a dictionary.
        """
        data = product.to_dict()

        num, symbol = product.price.split()
        num = float(".".join(num.split(",")[:1]))
        currency_id = await self._get_currency_id(symbol)
        if currency_id is None:
            return None

        data["price"] = [
            {
                "currencyId": currency_id,
                "gross": num,
                "net": num,
                "linked": True,
            }
        ]

        category = dict()
        category_name = product.category_set[-1]
        category_id = await self._get_category_id(category_name)
        if category_id is None:
            category["name"] = category_name

            for i, parent in enumerate(product.category_set[:-1][::-1]):
                last_parent = category
                while True:
                    par = last_parent.get("parent", None)
                    if not par:
                        break
                    last_parent = par

                parent_id = await self._get_category_id(parent)
                if parent_id is not None:
                    last_parent["parent"] = {"id": parent_id}
                    break

                last_parent["parent"] = {"name": parent}

                if i == len(product.category_set) - 2:
                    last_parent["parent"]["parent"] = {
                        "id": await self._get_category_id("Home")
                    }
        else:
            category["id"] = category_id

        data["categories"] = [
            category,
        ]

        media = []
        for i, image_url in enumerate(product.image_urls):
            id_ = str(uuid.uuid4().hex)
            resp_create = await self.session.post(
                "/api/media",
                json={
                    "id": id_,
                    "private": False,
                    "mediaFolderId": await self._get_product_media_folder_id(),
                },
            )

            if resp_create.status != 204:
                content_create = await resp_create.json()
                logging.error(f"could not create media | skip: {content_create}")
                continue

            file_name, extension = image_url.split("/")[-1].split(".")
            
            resp_upload = await self.session.post(
                f"/api/_action/media/{id_}/upload?extension={extension}&fileName={file_name + ''.join(sample(string.ascii_letters, 5))}",
                json={"url": image_url},
            )

            if resp_upload.status != 204:
                content_upload = await resp_upload.json(content_type=None)
                logging.error(
                    f"could not upload media from url: {image_url} | skip: {content_upload}"
                )
                continue

            if i == 0:
                data["cover"] = {"mediaId": id_}
                continue

            media.append({"mediaId": id_})

        data["media"] = media

        data["productNumber"] = str(uuid.uuid4())
        data["taxId"] = await self._get_standard_tax_id()
        data["stock"] = 0

        return data

    async def _get_currency_id(self, symbol: str) -> str:
        """
        Gets the currency ID for a given symbol.

        Args:
            symbol (str): The currency symbol.

        Returns:
            str: The currency ID.
        """
        currency_id = self.currencies.get(symbol, None)
        if currency_id is None:
            suffix = "/api/search/currency"

            data = {"filter": {"symbol": symbol}}

            response = await self.session.post(suffix, json=data)
            content = await response.json()
            content_data = content.get("data", [])

            if len(content_data) == 0:
                return None

            currency_id = content_data[0].get("id")
            self.currencies[symbol] = currency_id

        return currency_id

    async def _get_standard_tax_id(self) -> str:
        """
        Gets the standard tax ID.

        Returns:
            str: The standard tax ID.
        """
        tax_id = self.taxes.get("standard", None)
        if tax_id is None:
            suffix = "/api/search/tax"

            data = {"filter": {"name": "Standard rate"}}

            response = await self.session.post(suffix, json=data)
            content = await response.json()

            tax_id = content.get("data")[0].get("id")
            self.currencies["standard"] = tax_id

        return tax_id

    async def _get_product_media_folder_id(self) -> str:
        """
        Gets the product media folder ID.

        Returns:
            str: The product_media_folder ID.
        """
        media_folder_id = self.media_folders.get("product", None)
        if media_folder_id is None:
            suffix = "/api/search/media-folder"

            data = {"filter": {"name": "Product Media"}}

            response = await self.session.post(suffix, json=data)
            content = await response.json()

            if len(content.get("data")) == 0:
                return None

            media_folder_id = content.get("data")[0].get("id")
            self.media_folders["product"] = media_folder_id

        return media_folder_id

    async def _get_category_id(self, name: str) -> str:
        """
        Gets the category ID for a given name.

        Args:
            name (str): The category name.

        Returns:
            str: The category ID.
        """
        category_id = self.categories.get(name, None)
        if category_id is None:
            suffix = "/api/search/category"

            data = {"filter": {"name": name}}

            response = await self.session.post(suffix, json=data)
            content = await response.json()

            if len(content.get("data")) == 0:
                return None

            category_id = content.get("data")[0].get("id")
            self.categories[name] = category_id

        return category_id

    async def _get_product_id(self, name: str) -> str:
        """
        Gets the product ID for a given name.

        Args:
            name (str): The product name.

        Returns:
            str: The product ID.
        """
        suffix = "/api/search/product"

        data = {"filter": {"name": name}}

        response = await self.session.post(suffix, json=data)
        content = await response.json()

        if len(content.get("data")) == 0:
            return None

        product_id = content.get("data")[0].get("id")

        return product_id
