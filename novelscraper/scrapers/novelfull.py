from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from re import findall
from typing import Dict, List

from bs4 import BeautifulSoup
from bs4.element import Tag
from ebooklib import epub
from loguru import logger
from novelscraper.models import ScraperError
from novelscraper.scrapers.basescraper import BaseScraper


class NovelFull(BaseScraper):
    max_workers: int = 50
    domain: str = "https://novelfull.com"
    url: str
    start_chapter: int
    end_chapter: int
    novel_title: str
    novel_author: str
    novel_description: str
    novel_cover_image_bytes: bytes

    def __init__(self, url: str, start_chapter: int = 1, end_chapter: int = 1) -> None:
        if self.domain not in url:
            raise ScraperError(f"NovelFull scraper does not support the given URL: '{url}'")
        else:
            self.url = url

        if start_chapter < 1:
            raise ScraperError("Invalid start page, must be greater than 0")
        else:
            self.start_chapter = start_chapter

        if end_chapter < 1:
            raise ScraperError("Invalid end page, must be greater or equal to start page")
        else:
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

        # Find the novel's cover image. Usually within a <img alt="..."> tag, on which the "alt" attribute is
        # the title of the novel.
        novel_cover_image_tag: Tag = soup.find("img", {"alt": self.novel_title})
        self.novel_cover_image_bytes: bytes = self.get_page_content(self.domain + novel_cover_image_tag.get("src"))

        # Find the novel's author. Usually after a <h3>Author:</h3> tag.
        self.novel_author: str = soup.find("h3", text="Author:").find_next_sibling("a").get_text()
        logger.info(f"Novel author: {self.novel_author}")

        # Find the novel's description. Usually within a <div id="desc-text"> tag.
        novel_description_div: str = soup.find("div", {"class": "desc-text"})

        # Find all <p> tags, which contain the text of the description and extract the text from them.
        novel_description_text_list: List[str] = [p.get_text() for p in novel_description_div.find_all("p", text=True)]
        self.novel_description: str = "\n".join(novel_description_text_list)

    def scrape_novel_page(self, page: int) -> List[Dict[str, str]]:
        """Scrapes the given page, accessing each chapter in the page and then scraping it's contents."""

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
        chapters = [chapter for chapter in chapters if self.start_chapter <= int(findall(r"\d+", chapter.get("title"))[0]) <= self.end_chapter]

        # List to hold the chapter data.
        chapters_info: List[Dict[str, str]] = []

        # Use a ThreadPoolExecutor to scrape the chapters in parallel.
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results_gen = executor.map(self.scrape_chapter_page, chapters)

            # Iterate over the results of the scraping and add them to the list.
            chapters_info: List[Dict[str, str]] = list(results_gen)

        return chapters_info

    def scrape_chapter_page(self, chapter: Tag) -> Dict[str, str]:
        """Scrape's the given chapter page, extracting it's contents."""

        chapter_url: str = chapter.get("href")
        chapter_title: str = chapter.get("title")
        chapter_number: int = int(findall(r"\d+", chapter.get("title"))[0])

        logger.debug(f"Scraping chapter: '{chapter_title}'...")

        # Get the chapter's content.
        chapter_page_content: bytes = self.get_page_content(f"{self.domain}{chapter_url}")

        # Parse the chapter's content.
        chapter_soup: BeautifulSoup = BeautifulSoup(chapter_page_content, "html.parser")

        # Find the chapter's content. Usually within <div id="chapter-content">.
        chapter_content: Tag = chapter_soup.find("div", {"id": "chapter-content"})

        # Find all <p> tags, which contain the text of the chapter and extract the text from them.
        chapter_text_list: List[str] = [str(p) for p in chapter_content.find_all("p", text=True)]
        chapter_text: str = "".join(chapter_text_list)

        # Add the chapter's information to the dictionary.
        return {"chapter_url": chapter_url, "chapter_number": chapter_number, "chapter_title": chapter_title, "chapter_content": chapter_text}

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

            book_chapter = epub.EpubHtml(title=chapter_title, file_name=f"{chapter_number}.xhtml", lang="en")
            book_chapter.set_content(f"<html><body><h1>{chapter_title}</h1><p>{chapter_content}</p></body></html>")
            book.add_item(book_chapter)
            book.toc.append(book_chapter)
            book.spine.append(book_chapter)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Create the epub file.
        logger.info("Creating EPUB file...")
        epub.write_epub(f"{self.novel_title}.Chapters{self.start_chapter}-{self.end_chapter}.epub", book, {})

    def scrape(self) -> None:
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
        novelFull = NovelFull(args.url, args.start_page, args.end_page)
        novelFull.scrape()
