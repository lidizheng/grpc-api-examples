import asyncio
import binascii
import hashlib
import itertools
import logging
import threading
import time
from typing import Sequence, Set, Text

import grpc
from proto import scraping_pb2, scraping_pb2_grpc
from pyquery import PyQuery as pq
from aiofile import AIOFile

SCRAPER_POOL = ['127.0.0.1:10000']
ENTRY_PAGE = 'https://www.google.com'
BATCH_SIZE = 5
OUTPUT_FOLDER = 'current/data'


class ScrapingState:
    """Stateful objects for scraping."""

    def __init__(self):
        self._visited_links = set()
        self._pending_links = []
        # No longer needs lock

    def has_pending_links(self) -> bool:
        """Return True if there is any pending link."""
        return len(self._pending_links) > 0

    def get_pending_link(self) -> Text:
        """Get one pending link."""
        return self._pending_links.pop(0)

    def new_links(self, links: Sequence[Text]):
        """Insert new links, update pending links."""
        new_links_set = set(links)
        unique_new_links = new_links_set - self._visited_links
        self._pending_links.extend(list(unique_new_links))
        self._visited_links |= new_links_set
        logging.info('Visited links [%d] pending links [%d]', len(
            self._visited_links), len(self._pending_links))


class ScrapingRequestIterator:
    """Request iterator for scraping streaming call."""

    def __init__(self):
        # Server may push back, so buffer is necessary.
        self._links = []
        self._link_ready = asyncio.Condition()

    async def insert(self, link: Text):
        """Inserts a new link to the buffer list."""
        async with self._link_ready:
            self._links.append(link)
            self._link_ready.notify()

    def __iter__(self):
        return self

    async def __anext__(self):
        """Assembles a request if new link available."""
        while True:
            async with self._link_ready:
                if len(self._links):
                    return scraping_pb2.ScrapingRequest(
                        target=self._links.pop(0)
                    )
                await self._link_ready.wait()


def strip_links(page_content: Text) -> Sequence[Text]:
    """Parse links from HTML."""
    elements = pq(page_content)('a')
    return [elements.eq(i).attr['href'] for i in range(len(elements))]


class ScraperController:

    def __init__(self, scraper_url: Text, state: ScrapingState):
        logging.info('Connecting to scraper server [%s]', scraper_url)
        # Create gRPC Channel
        self._channel = grpc.insecure_channel(scraper_url)
        self._stub = scraping_pb2_grpc.ScraperStub(self._channel)

        # Create request iterator.
        self._request_iterator = ScrapingRequestIterator()
        self._response_iterator = self._stub.scrape(self._request_iterator)

        # Create response consumer.
        self._consumer_task = asyncio.create_task(
            self._async_parse_response(state)
        )

    async def _async_parse_response(self, state: ScrapingState):
        async for response in self._response_iterator:
            # Add the new links to the loop.
            state.new_links(strip_links(
                response.page.content
            ))

            # Write the result to a permenant storage system.
            output_file = "%s/%s.html" % (
                OUTPUT_FOLDER,
                binascii.crc32(response.page.url.encode('utf-8')),
            )
            async with AIOFile(output_file, 'w') as af:
                await af.write(response.page.content)  # Non-blocking file IO.

    async def scrape_next(self, link):
        logging.info('Parsing next [%s]', link)
        await self._request_iterator.insert(link)

    async def close(self):
        await self._channel.cancel()


async def scraping():
    # Initialize stateful objects.
    state = ScrapingState()
    state.new_links([ENTRY_PAGE])

    # Create a sequence of controllers.
    controllers = (
        ScraperController(scraper_url, state)
        for scraper_url in SCRAPER_POOL
    )
    controller_loop = itertools.cycle(controllers)

    while True:
        if state.has_pending_links():
            controller = next(controller_loop)
            await controller.scrape_next(state.get_pending_link())
        else:
            logging.info('No pending links found, sleeping...')
            asyncio.sleep(1)


def main():
    logging.basicConfig(level=logging.INFO)
    asyncio.run(scraping())


if __name__ == "__main__":
    main()
