"""
scrapers/basescraper.py

Defines and implements the BaseScraper class.
"""

from typing import Dict, List

from ebooklib import epub
from loguru import logger
from novelscraper.models import ScraperError
from requests import get


class BaseScraper:
    """
    BaseScraper is an abstract class. All scrapers must inherit from it.
    """

    max_workers: int = 50
    domain: str
    url: str
    start_chapter: int
    end_chapter: int
    novel_title: str
    novel_author: str
    novel_description: str
    novel_cover_image_bytes: bytes
    novel_chapter_link: str

    @staticmethod
    def get_page_content(url: str) -> bytes:
        """
        Sends a GET request to the given URL and returns the response's content,
        if the response's code was 200.
        """

        request = get(url)
        logger.debug(f"Sending GET request to '{url}'")

        if request.status_code == 200:
            return request.content

        logger.debug(f"Failed response '{request.content}'")
        raise ScraperError(f"GET request to '{url}' failed.")

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
