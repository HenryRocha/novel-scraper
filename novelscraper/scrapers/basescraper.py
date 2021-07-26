from loguru import logger
from novelscraper.models import ScraperError
from requests import get


class BaseScraper:
    max_workers: int = 50

    def get_page_content(self, url: str) -> bytes:
        """
        Sends a GET request to the given URL and returns the response's content,
        if the response's code was 200.
        """

        request = get(url)
        logger.trace(f"Sending GET request to '{url}'")

        if request.status_code == 200:
            return request.content
        else:
            raise ScraperError(f"GET request to '{url}' failed.")
