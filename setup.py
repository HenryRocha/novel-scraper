import pathlib

from setuptools import setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

setup(
    name="novelscraper",
    description="Novel Scraper is a CLI tool to help you download novels from different sources.",
    version="0.1.0",
    python_requires=">=3.7",
    install_requires=["requests", "beautifulsoup4", "ebooklib", "loguru"],
    entry_points="""
        [console_scripts]
        novelscraper=novelscraper.__main__:main
    """,
    author="Henry Rocha",
    keywords="novelscraper, scraper, novel, novels",
    long_description=README,
    long_description_content_type="text/markdown",
    license="MIT",
    url="https://github.com/HenryRocha/novel-scraper",
    author_email="henryrocha@protonmail.com",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
)
