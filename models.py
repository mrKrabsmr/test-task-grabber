class Product:
    """
    Represents a product with its details.

    Attributes:
        name (str): The name of the product.
        price (str): The price of the product.
        description (str): The description of the product.
        category (str): The category of the product.
        image_urls (list): A list of image URLs for the product.
        ean (str): The European Article Number (EAN) of the product.
    """

    def __init__(self, name, price, description, category_set, image_urls, ean):
        self.name = name
        self.price = price
        self.description = description
        self.category_set = category_set
        self.image_urls = image_urls
        self.ean = ean

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "ean": self.ean,
        }
