"""
scrapers/wuxiaworld.py

Defines and implements the WuxiaWorld scraper class.
"""

from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from bs4 import BeautifulSoup
from bs4.element import Tag
from loguru import logger
from novelscraper.models import ScraperError
from novelscraper.scrapers.basescraper import BaseScraper


class WuxiaWorld(BaseScraper):
    """
    This scraper is used to scrape novel's from WuxiaWorld.
    """

    def __init__(self, url: str, start_chapter: int = 1, end_chapter: int = 1) -> None:
        self.domain = "https://www.wuxiaworld.com"

        if self.domain not in url:
            raise ScraperError(f"WuxiaWorld scraper does not support the given URL: '{url}'")

        self.url = url

        if start_chapter < 1:
            raise ScraperError("Invalid start chapter, must be greater than 0")

        self.start_chapter = start_chapter

        if end_chapter < 1:
            raise ScraperError("Invalid end chapter, must be greater or equal to start chapter")

        self.end_chapter = end_chapter

    def scrape_novel_info(self) -> None:
        """Scrapes the novel's information from the novel's main page."""

        logger.info("Scraping novel information...")

        # Get the page's content.
        novel_page_content: bytes = self.get_page_content(self.url)

        # Parse the page's content.
        soup: BeautifulSoup = BeautifulSoup(novel_page_content, "html.parser")

        # Find the novel's title. Usually within a <h3 class="title"> tag.
        self.novel_title: str = soup.find("div", {"class": "novel-body"}).h2.text
        logger.info(f"Novel title: {self.novel_title}")

        # Find the novel's cover image. Usually within a <img alt="..."> tag,
        # on which the "alt" attribute is the title of the novel.
        novel_cover_image_tag: Tag = soup.find("img", {"class": "img-thumbnail"})
        self.novel_cover_image_bytes: bytes = self.get_page_content(
            novel_cover_image_tag.get("src")
        )

        # Find the novel's author. Usually after a <h3>Author:</h3> tag.
        self.novel_author: str = soup.find("dt", text="Author:").find_next_sibling("dd").get_text()
        logger.info(f"Novel author: {self.novel_author}")

        # Find the novel's description. Usually within a <div id="desc-text"> tag.
        novel_description_div: str = soup.find("h3", text="Synopsis").find_next_sibling("div")

        # Find all <p> tags, which contain the text of the description
        # and extract the text from them.
        novel_description_text_list: List[str] = [
            p.get_text() for p in novel_description_div.find_all("p", text=True)
        ]
        self.novel_description: str = "\n".join(novel_description_text_list)
        logger.info(f"Novel description: {self.novel_description}")

        # WuxiaWorld's novels follow this URL pattern for chapters, so it makes
        # it easier to scrape the chapters.
        self.novel_chapter_link: str = self.url.split("/")[-1] + "-chapter-"
        if not self.url.endswith("/"):
            self.novel_chapter_link = "/" + self.novel_chapter_link

    def scrape_chapter_page(self, chapter_url: str) -> Dict[str, str]:
        """
        Scrape's the given chapter page, extracting it's contents.
        By default, chapter that do not have a number in their title will
        use '-1' as the chapter number.
        """

        logger.info(f"Scraping chapter: {chapter_url}...")

        # Get the page's content.
        chapter_page_content: bytes = self.get_page_content(chapter_url)

        # Parse the chapter's content.
        chapter_soup: BeautifulSoup = BeautifulSoup(chapter_page_content, "html.parser")

        # Find the chapter's outer div. Usually within <div id="chapter-outer">.
        chapter_outer_div: Tag = chapter_soup.find("div", {"id": "chapter-outer"})

        # Find the chapter's title. Usually within a <h4> tag.
        chapter_title: str = chapter_outer_div.find("h4").text
        logger.debug(f"Chapter title: {chapter_title}")

        # Find the chapter's number. Usually within the chapter's title.
        # Chapter X: title
        chapter_number: int = int(chapter_url.split("-")[-1])

        # Find the chapter's content. Usually within <div id="chapter-content">.
        chapter_content: Tag = chapter_outer_div.find("div", {"id": "chapter-content"})

        # Find all <p> tags, which contain the text of the chapter and extract the text from them.
        chapter_text_list: List[str] = [
            str(p) for p in chapter_content.find_all("p", text=True, recursive=True)
        ]

        # Join the chapter's text together and return it.
        chapter_text: str = "\n".join(chapter_text_list)

        # Add the chapter's information to the dictionary.
        chapter_info: Dict[str, str] = {
            "chapter_url": chapter_url,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "chapter_content": chapter_text,
        }

        return chapter_info

    def scrape(self) -> None:
        """
        Scrapes the novel's chapters and creates an EPUB file.
        Ties up all the methods together and runs them in sequence.
        """

        self.scrape_novel_info()

        # List of pages to scrape.
        chapters_to_scrape: List[str] = [
            self.url + self.novel_chapter_link + str(i)
            for i in range(self.start_chapter, self.end_chapter + 1)
        ]

        # # List which will contain all scraped chapters.
        chapters_info: List[Dict[str, str]] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results_gen = executor.map(self.scrape_chapter_page, chapters_to_scrape)

            # Iterate over the results of the scraping and add them to the list.
            chapters_info: List[Dict[str, str]] = list(results_gen)

        # # Create the epub file.
        self.create_epub(chapters_info)
        logger.success("Done")

    @staticmethod
    def run(args: Namespace) -> None:
        """
        Create the scraper and runs it.
        """

        wuxia_world = WuxiaWorld(args.url, args.start_chapter, args.end_chapter)
        wuxia_world.scrape()
