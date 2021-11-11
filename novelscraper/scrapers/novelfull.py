"""
scrapers/novelfull.py

Defines and implements the NovelFull scraper class.
"""

from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from re import findall
from typing import Dict, List

from bs4 import BeautifulSoup
from bs4.element import Tag
from loguru import logger
from novelscraper.models import ScraperError
from novelscraper.scrapers.basescraper import BaseScraper


class NovelFull(BaseScraper):
    """
    This scraper is used to scrape novel's from NovelFull.
    """

    def __init__(self, url: str, start_chapter: int = 1, end_chapter: int = 1) -> None:
        self.domain = "https://novelfull.com"

        if self.domain not in url:
            raise ScraperError(f"NovelFull scraper does not support the given URL: '{url}'")

        self.url = url

        if start_chapter < 1:
            raise ScraperError("Invalid start page, must be greater than 0")

        self.start_chapter = start_chapter

        if end_chapter < 1:
            raise ScraperError("Invalid end page, must be greater or equal to start page")

        self.end_chapter = end_chapter

    def calculate_pages_to_scrape(self) -> List[int]:
        """Calculates which pages from NovelFull to scrape, based on the start and end chapter."""

        logger.trace("Calculating which pages to scrape...")

        start_chapter_rest: int = self.start_chapter % 50
        end_chapter_rest: int = self.end_chapter % 50

        start_page: int = self.start_chapter // 50
        end_page: int = self.end_chapter // 50

        if start_chapter_rest == 0:
            start_page -= 1

        if end_chapter_rest == 0:
            end_page -= 1

        return list(range(start_page + 1, end_page + 1 + 1))

    def scrape_novel_info(self) -> None:
        """Scrapes the novel's information from the novel's main page."""

        logger.info("Scraping novel information...")

        # Get the page's content.
        novel_page_content: bytes = self.get_page_content(self.url)

        # Parse the page's content.
        soup: BeautifulSoup = BeautifulSoup(novel_page_content, "html.parser")

        # Find the novel's title. Usually within a <h3 class="title"> tag.
        self.novel_title: str = soup.find("h3", {"class": "title"}).get_text()
        logger.info(f"Novel title: {self.novel_title}")

        # Find the novel's cover image. Usually within a <img alt="..."> tag,
        # on which the "alt" attribute is the title of the novel.
        novel_cover_image_tag: Tag = soup.find("img", {"alt": self.novel_title})
        self.novel_cover_image_bytes: bytes = self.get_page_content(
            self.domain + novel_cover_image_tag.get("src")
        )

        # Find the novel's author. Usually after a <h3>Author:</h3> tag.
        self.novel_author: str = soup.find("h3", text="Author:").find_next_sibling("a").get_text()
        logger.info(f"Novel author: {self.novel_author}")

        # Find the novel's description. Usually within a <div id="desc-text"> tag.
        novel_description_div: str = soup.find("div", {"class": "desc-text"})

        # Find all <p> tags, which contain the text of the description
        # and extract the text from them.
        novel_description_text_list: List[str] = [
            p.get_text() for p in novel_description_div.find_all("p", text=True)
        ]
        self.novel_description: str = "\n".join(novel_description_text_list)

    def scrape_novel_page(self, page: int) -> List[Dict[str, str]]:
        """
        Scrapes the given page, accessing each chapter in the page
         then scraping it's contents.
        """

        logger.info(f"Scraping page: {page}...")

        # Get the page's content.
        start_page_content: bytes = self.get_page_content(self.url + f"?page={page}")

        # Parse the page's content.
        soup: BeautifulSoup = BeautifulSoup(start_page_content, "html.parser")

        # Find the chapter list. Usually within <div id="list-chapter">.
        chapter_list: Tag = soup.find("div", {"id": "list-chapter"})

        # Find all chapter links. Usually within <a> tags that contain the "title" attribute.
        chapters: List[Tag] = chapter_list.find_all("a", {"title": True})

        # Filter out all the chapters that are not in the range of the start and end chapter.
        chapters = self.filter_chapter_list(chapters)

        # List to hold the chapter data.
        chapters_info: List[Dict[str, str]] = []

        # Use a ThreadPoolExecutor to scrape the chapters in parallel.
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results_gen = executor.map(self.scrape_chapter_page, chapters)

            # Iterate over the results of the scraping and add them to the list.
            chapters_info: List[Dict[str, str]] = list(results_gen)

        return chapters_info

    def filter_chapter_list(self, chapters: List[Tag]) -> List[Tag]:
        """
        Filters out all the chapters that are not in the range of the start and end chapter.
        By default it will include all chapters that do not have numbers in their title.
        """

        filtered_chapters: List[Tag] = []
        for chapter in chapters:
            chapter_title: str = chapter.get("title")
            chapter_number_list: List[str] = findall(r"\d+", chapter_title)
            if len(chapter_number_list) > 0:
                if self.start_chapter <= int(chapter_number_list[0]) <= self.end_chapter:
                    filtered_chapters.append(chapter)
            else:
                filtered_chapters.append(chapter)

        return filtered_chapters

    def scrape_chapter_page(self, chapter: Tag) -> Dict[str, str]:
        """
        Scrape's the given chapter page, extracting it's contents.
        By default, chapter that do not have a number in their title
        will use '-1' as the chapter number.
        """

        chapter_url: str = chapter.get("href")
        chapter_title: str = chapter.get("title")
        chapter_number_list: List[str] = findall(r"\d+", chapter_title)
        if len(chapter_number_list) > 0:
            chapter_number: int = int(chapter_number_list[0])
        else:
            chapter_number: int = -1

        logger.debug(f"Scraping chapter: '{chapter_title}'...")

        # Get the chapter's content.
        chapter_page_content: bytes = self.get_page_content(f"{self.domain}{chapter_url}")

        # Parse the chapter's content.
        chapter_soup: BeautifulSoup = BeautifulSoup(chapter_page_content, "html.parser")

        # Find the chapter's content. Usually within <div id="chapter-content">.
        chapter_content: Tag = chapter_soup.find("div", {"id": "chapter-content"})

        # Find all <p> tags, which contain the text of the chapter and extract the text from them.
        chapter_text_list: List[str] = [
            str(p) for p in chapter_content.find_all("p", text=True, recursive=True)
        ]

        # Workaround for the fact that the chapter's text is sometimes
        # not within the <div id='chapter-content'>.
        if len(chapter_text_list) <= 1:
            logger.warning(
                f"Chapter '{chapter_title}' has no content. Trying to look for "
                + "content outside of <div id='chapter-content'>"
            )
            chapter_text_list: List[str] = [
                str(p) for p in chapter_soup.find_all("p", text=True, recursive=True)
            ]
            if len(chapter_text_list) > 1:
                logger.success(
                    "Found content outside of <div id='chapter-content'>. "
                    + "Using this as the chapter's content..."
                )
            else:
                logger.error("Could not find content. Stopping...")
                return {
                    "chapter_url": chapter_url,
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "chapter_content": "Novel-Scraper failed to scrape "
                    + "the contents of this chapter.",
                }

        # Join the chapter's text together and return it.
        chapter_text: str = "\n".join(chapter_text_list)

        # Add the chapter's information to the dictionary.
        return {
            "chapter_url": chapter_url,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "chapter_content": chapter_text,
        }

    def scrape(self) -> None:
        """
        Scrapes the novel's chapters and creates an EPUB file.
        Ties up all the methods together and runs them in sequence.
        """

        self.scrape_novel_info()

        # List of pages to scrape.
        pages_to_scrape: List[int] = self.calculate_pages_to_scrape()
        logger.info(f"Pages to scrape: {len(pages_to_scrape)} -> {pages_to_scrape}")

        # List which will contain all scraped chapters.
        chapters_info: List[Dict[str, str]] = []

        # Scrape each page and add the chapters to the list.
        for page in pages_to_scrape:
            chapters_info += self.scrape_novel_page(page)

        # Create the epub file.
        self.create_epub(chapters_info)

        logger.success("Done")

    @staticmethod
    def run(args: Namespace) -> None:
        """
        Create the scraper and runs it.
        """
        raise ScraperError("NovelFull is currently not supported since it implemented CAPTCHA.")

        # novel_full = NovelFull(args.url, args.start_page, args.end_page)
        # novel_full.scrape()
