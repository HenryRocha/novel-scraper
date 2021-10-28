from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from bs4 import BeautifulSoup
from bs4.element import Tag
from ebooklib import epub
from loguru import logger
from novelscraper.models import ScraperError
from novelscraper.scrapers.basescraper import BaseScraper


class WuxiaWorld(BaseScraper):
    max_workers: int = 50
    domain: str = "https://www.wuxiaworld.com"
    url: str
    start_chapter: int
    end_chapter: int
    novel_title: str
    novel_author: str
    novel_description: str
    novel_cover_image_bytes: bytes
    novel_chapter_link: str

    def __init__(self, url: str, start_chapter: int = 1, end_chapter: int = 1) -> None:
        if self.domain not in url:
            raise ScraperError(
                f"WuxiaWorld scraper does not support the given URL: '{url}'"
            )
        else:
            self.url = url

        if start_chapter < 1:
            raise ScraperError("Invalid start chapter, must be greater than 0")
        else:
            self.start_chapter = start_chapter

        if end_chapter < 1:
            raise ScraperError(
                "Invalid end chapter, must be greater or equal to start chapter"
            )
        else:
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

        # Find the novel's cover image. Usually within a <img alt="..."> tag, on which the "alt" attribute is
        # the title of the novel.
        novel_cover_image_tag: Tag = soup.find("img", {"class": "img-thumbnail"})
        self.novel_cover_image_bytes: bytes = self.get_page_content(
            novel_cover_image_tag.get("src")
        )

        # Find the novel's author. Usually after a <h3>Author:</h3> tag.
        self.novel_author: str = (
            soup.find("dt", text="Author:").find_next_sibling("dd").get_text()
        )
        logger.info(f"Novel author: {self.novel_author}")

        # Find the novel's description. Usually within a <div id="desc-text"> tag.
        novel_description_div: str = soup.find("h3", text="Synopsis").find_next_sibling(
            "div"
        )

        # Find all <p> tags, which contain the text of the description and extract the text from them.
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
        By default, chapter that do not have a number in their title will use '-1' as the chapter number.
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

    def create_epub(self, chapters_info: List[Dict[str, str]]) -> None:
        """Creates an EPUB file from the given chapters information."""

        book = epub.EpubBook()
        book.set_identifier("nvsc_100")
        book.set_title(self.novel_title)
        book.add_author(self.novel_author)
        book.set_cover("cover.png", self.novel_cover_image_bytes)
        book.set_language("en")
        book.add_metadata("DC", "description", self.novel_description)
        book.spine = ["nav"]

        # Sort the chapter in ascending order, based on the chapter's number.
        chapters_info.sort(key=lambda chapter: chapter["chapter_number"])

        for chapter in chapters_info:
            chapter_number: int = chapter["chapter_number"]
            chapter_title: str = chapter["chapter_title"]
            chapter_content: str = chapter["chapter_content"]
            logger.trace(f"Adding chapter {chapter_number} to EPUB...")

            book_chapter = epub.EpubHtml(
                title=chapter_title, file_name=f"{chapter_title}.xhtml", lang="en"
            )
            book_chapter.set_content(
                f"<html><body><h1>{chapter_title}</h1><p>{chapter_content}</p></body></html>"
            )
            book.add_item(book_chapter)
            book.toc.append(book_chapter)
            book.spine.append(book_chapter)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Create the epub file.
        logger.info("Creating EPUB file...")

        filename_novel_title: str = self.novel_title.replace(" ", "_")
        epub.write_epub(
            f"{filename_novel_title}.Chapters{self.start_chapter}-{self.end_chapter}.epub",
            book,
            {},
        )

    def scrape(self) -> None:
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
        wuxiaWorld = WuxiaWorld(args.url, args.start_chapter, args.end_chapter)
        wuxiaWorld.scrape()
