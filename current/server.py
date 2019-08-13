import argparse
import itertools
import logging
import queue
import threading
import time
from concurrent import futures
from typing import Iterator, Text

import requests

import grpc
from proto import scraping_pb2, scraping_pb2_grpc


def download_web_page(link: Text):
    """Download the HTML for the specific link."""
    logging.info('Downloading [%s]', link)
    return requests.get(link).text


class Scrapper(scraping_pb2_grpc.ScraperServicer):

    def scrape(self,
               request_iterator: Iterator[scraping_pb2.ScrapingRequest],
               context: grpc.ServicerContext) -> Iterator[
                   scraping_pb2.ScrapingResponse]:
        for request in request_iterator:
            try:
                yield scraping_pb2.ScrapingResponse(page=scraping_pb2.WebPage(
                    url=request.target,
                    content=download_web_page(request.target),
                ))
            except requests.exceptions.MissingSchema as missing_schema_error:
                logging.error(
                    'Failed to parse [%s] due to [%s]',
                    request.target, missing_schema_error
                )


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default=":10000", nargs=1,
                        type=str, help='The port to listen on')
    args = parser.parse_args()

    # Must contain a ThreadPoolExecutor which has limited threads by default.
    server = grpc.server(futures.ThreadPoolExecutor())
    port = server.add_insecure_port(args.port)

    scraping_pb2_grpc.add_ScraperServicer_to_server(Scrapper(), server)

    server.start()
    logging.info('Scraper server start at :%d', port)

    try:
        time.sleep(86400)
    except InterruptedError:
        pass
    finally:
        server.stop(None)


if __name__ == "__main__":
    main()
