import argparse
import asyncio
import logging

from dotenv import load_dotenv

from app import App
from client import ShopwareClient
from grabber import GrowShopGrabber


async def main() -> None:
    """
    The main entry point of the application.

    This function sets up the environment, parses command-line arguments, and runs the application.
    """

    load_dotenv()

    logging.basicConfig(level=logging.INFO)

    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "-l",
        "--links",
        help="link of product catalogs to need parse",
        required=False,
    )
    args = argparser.parse_args()
    if args.links is None:
        need_parse_links = []
    else:
        need_parse_links = args.links.split(",")

    shopware_client = ShopwareClient(url="https://raul.testshop193.com")
    growshop_grabber = GrowShopGrabber(
        url="https://www.grow-shop24.de", catalog_links=need_parse_links
    )
    app = App(grabber=growshop_grabber, client=shopware_client)
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
