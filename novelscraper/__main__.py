import sys
from argparse import ArgumentParser, Namespace

from loguru import logger

from novelscraper.scrapers import NovelFull, WuxiaWorld


def main():
    # Create the argument parser and it's subparsers.
    parser: ArgumentParser = ArgumentParser()
    subparsers = parser.add_subparsers(help="available scrapers")

    # Add the flags to the main parser.
    parser.add_argument(
        "-v",
        "--verbosity",
        action="count",
        help="verbosity level",
        default=3,
        required=False,
    )

    # Create the parser for the "novelfull" command.
    novelfull_cmd_parser: ArgumentParser = subparsers.add_parser(
        "novelfull", help="downloads novels from 'novelfull.com'"
    )
    novelfull_cmd_parser.set_defaults(function=NovelFull.run)
    novelfull_cmd_parser.add_argument(
        "url",
        type=str,
        help="URL that points to the novel to be scraped.",
    )
    novelfull_cmd_parser.add_argument(
        "-s",
        "--start-page",
        type=int,
        required=False,
        help="starting page, defines which page to start scraping from. If not specified will scrape from first to EndingPage page or until there are no pages left.",
    )
    novelfull_cmd_parser.add_argument(
        "-e",
        "--end-page",
        type=int,
        required=False,
        help="ending page, defines on which page to stop scraping. If not specified will scrape from StartingPage until there are no pages left.",
    )

    # Create the parser for the "wuxiaworld" command.
    wuxiaworld_cmd_parser: ArgumentParser = subparsers.add_parser(
        "wuxiaworld", help="downloads novels from 'wuxiaworld.com'"
    )
    wuxiaworld_cmd_parser.set_defaults(function=WuxiaWorld.run)
    wuxiaworld_cmd_parser.add_argument(
        "url",
        type=str,
        help="URL that points to the novel to be scraped.",
    )
    wuxiaworld_cmd_parser.add_argument(
        "-s",
        "--start-chapter",
        type=int,
        required=False,
        help="starting chapter, defines which chapter to start scraping from. If not specified will scrape from first to EndingChapter chapter or until there are no chapters left.",
    )
    wuxiaworld_cmd_parser.add_argument(
        "-e",
        "--end-chapter",
        type=int,
        required=False,
        help="ending chapter, defines on which chapter to stop scraping. If not specified will scrape from StartingChapter until there are no chapters left.",
    )

    # Parse the given arguments and run the corresponding function.
    args: Namespace = parser.parse_args()

    # Configure the logger based on given arguments.
    logger.remove()
    logger.add(
        sys.stdout,
        level=50 - int(args.verbosity) * 10,
        colorize=True,
        format="[<yellow>{time:HH:mm:ss!UTC}</yellow>][<level>{level}</level>] <level>{message}</level>",
    )

    if len(sys.argv) > 1:
        args.function(args)
    else:
        print(
            "No arguments were given. Try running 'novelscraper --help' first to see the available commands."
        )


if __name__ == "__main__":
    main()
