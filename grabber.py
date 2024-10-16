import logging

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from models import Product


class GrowShopGrabber:
    """
    A web scraper for grabbing product data from a Grow Shop website.

    Attributes:
        url (str): The base URL of the website.
        catalog_links (list): A list of catalog links to scrape.
    """

    def __init__(self, url: str, catalog_links: list = []) -> None:
        """
        Initializes the GrowShopGrabber instance.

        Args:
            url (str): The base URL of the website.
            catalog_links (list): A list of catalog links to scrape.
        """
        self.url = url
        self.catalog_links = catalog_links

    async def grab(self) -> list[Product]:
        """
        Grabs product data from the website.

        Returns:
            list[Product]: A list of Product instances.
        """
        async with ClientSession() as session:
            products: list[Product] = []
            if len(self.catalog_links) == 0:
                async with session.get(self.url) as resp:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    self._parse_catalog_links(soup)

            for catalog_link in self.catalog_links:
                try:
                    while True:
                        async with session.get(catalog_link) as resp:
                            logging.info(f"start parsing {catalog_link} ...")
                            html = await resp.text()
                            soup = BeautifulSoup(html, "html.parser")

                            try:
                                soup.find("div", id="plh").find("div", class_="row").find("div", class_="thumbnail").find("a")
                                logging.info("stop parsing cause it's general page of product catalogs")
                                break
                            except Exception:
                                pass

                            category, links = self._parse_product_links(soup)

                            for link in links:
                                try:
                                    async with session.get(link) as resp:
                                        html = await resp.text()
                                        soup_ = BeautifulSoup(html, "html.parser")
                                        product = self._parse_product(soup_, category)
                                        products.append(product)

                                except Exception as e:
                                    logging.error(
                                        f"error when parse product | skip: {e}"
                                    )
                                    continue
                            logging.info(f"{catalog_link} was parsed!")
                            next = soup.find(
                                "li",
                                class_="next",
                            )
                            if next is None:
                                break

                            catalog_link = next.find("a").attrs["href"]

                except Exception as e:
                    logging.error(f"error when parse product links | skip: {e}")
                    continue

            return products

    def _parse_catalog_links(self, soup: BeautifulSoup) -> None:
        """
        Parses catalog links from the website.

        Args:
            soup (BeautifulSoup): The HTML soup of the website.
        """
        block_menu = soup.find("div", id="mm-dropdown")
        items = block_menu.find("ul", recursive=False).find_all("li", recursive=False)

        def find_path(items):
            for item in items:
                try:
                    sub = item.find("ul", recursive=False)

                    if sub is None:
                        a = item.find("a")
                        if a:
                            href = a.attrs.get("href")
                            self.catalog_links.append(href)
                        continue

                    find_path(sub)
                except Exception as e:
                    logging.error(f"error when parse catalog links | skip: {e}")
                    continue

        find_path(items)

        self.catalog_links = list(set(self.catalog_links))

    def _parse_product_links(self, soup: BeautifulSoup) -> (str, list):
        """
        Parses product links from a catalog page.

        Args:
            soup (BeautifulSoup): The HTML soup of the catalog page.

        Returns:
            tuple: A tuple containing the category name and a list of product links.
        """
        title = soup.find("h1", class_="title").text
        elements = soup.find_all("a", class_="img-w")

        links = []
        for el in elements:
            if el is None:
                continue

            href = el.attrs.get("href")
            links.append(href)

        return title, links

    def _parse_product(self, soup: BeautifulSoup, category: str) -> Product:
        """
        Parses product data from a product page.

        Args:
            soup (BeautifulSoup): The HTML soup of the product page.
            category (str): The category name.

        Returns:
            Product: A Product instance.
        """
        name = soup.find("h1", class_="product-title").text or ""
        price = soup.find("strong", class_="price").find("span").text or ""
        description = soup.find("div", class_="desc").text or ""
        ean = soup.find("li", "product-sku").find("span").text or ""
        image_urls = []

        gallery = soup.find("div", id="gallery")
        imgs = gallery.find_all("img")
        for img in imgs:
            image_urls.append(img.attrs.get("src"))

        return Product(
            name=name.strip(),
            price=price.strip(),
            description=description.strip(),
            category=category.strip(),
            image_urls=image_urls,
            ean=ean.strip(),
        )
