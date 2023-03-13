"""
Download and manage media.
"""
import configparser
import logging
import os.path
from datetime import datetime
from typing import Tuple
from urllib.parse import urlparse

import requests
import tweepy  # type: ignore
from tenacity import (
    after_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_fixed,
)

from modules import config, twitter

HTTP_GET_TIMEOUT = 5

log = logging.getLogger()


class DownloadFailed(Exception):
    """Generic module exception."""

    ...


def download_media(
    tweet: tweepy.models.Status, configuration: configparser.ConfigParser, force_download: bool = False
) -> Tuple[int, bool]:
    """
    Given a tweet, download all media it contains.

    :param tweet: Tweet to download
    :param configuration: initialized ConfigParser object
    :param force_download: do not check if the files to download already exist on disk
    :return: tuple with number of media files downloaded and bool value, False if no media was found in the tweet
    """
    tweet_media_count = 0
    urls_list = twitter.get_all_media_from_tweet(tweet)
    if not urls_list:
        return 0, False

    for index, (url, requires_size_info) in enumerate(urls_list):
        extension = _get_file_extension_from_url(url)
        dst_filename = _build_filename(tweet, index + 1, extension)
        dst_filepath, extra_filepath = _build_filepath(configuration, dst_filename, tweet)

        # If the file is already on disk, and download is not forced, abort download and return True
        if force_download:
            log.debug("Will not check disk for existing files")
        elif _check_file_already_on_disk(extra_filepath) or _check_file_already_on_disk(dst_filepath):
            log.debug("Assuming all media in this tweet is already on disk")
            return 0, True

        # Pictures require size information to download in high quality
        if requires_size_info:
            url = url + f"?format={extension}&name=large"
            log.debug(f"Adding size info to URL: {url}")

        log.info(f"Downloading {dst_filename}")
        content = _download_url(url)
        _write_to_disk(dst_filepath, content)
        log.debug(f"Written to disk {dst_filename}")
        tweet_media_count += 1

    return tweet_media_count, True


def _build_filename(tweet: tweepy.models.Status, media_count: int, extension: str) -> str:
    """
    Build the destination filename given the tweet's details and the index number of the object in the tweet's media.
    The file name is formatted as follows:
        {user}_{date}_{ID}_{file_number}.{extension}
    Example:
        koirakoirana_2022-08-09_1557022684373983234_1.jpg

    :param tweet: tweet to process
    :param media_count: media file number
    :param extension: file extension
    :return: destination filename
    """
    source_user = tweet.user.screen_name
    tweet_time = datetime.strftime(tweet.created_at, "%Y-%m-%d")
    tweet_id = tweet.id_str
    return f"{source_user}_{tweet_time}_{tweet_id}_{media_count}.{extension}"


def _build_filepath(
    configuration: configparser.ConfigParser, filename: str, tweet: tweepy.models.Status
) -> Tuple[str, str]:
    """
    Build the download filepath.

    :param configuration: initialized ConfigParser object
    :return: final destination filepath and extra path if a subdirectory with the author's name exists (empty otherwise)
    """
    directory = config.get_download_directory(configuration)
    if not os.path.isdir(directory):
        log.error(f"Specified download path {directory} is not a valid directory")
        raise DownloadFailed(f"Failed to validate path {directory}")

    download_filepath = os.path.join(directory, filename)

    # If a subdirectory for the author already exists, return the extra path (directory/author/filename)
    username = tweet.user.screen_name
    if os.path.isdir(os.path.join(directory, username)):
        log.debug(f"Found subdirectory {username}")
        extra_path = os.path.join(directory, username, filename)
        log.debug(f"Final download path is {download_filepath}, but will also check {extra_path}")
    else:
        log.debug(f"Final download path is {download_filepath}")
        extra_path = ""

    return download_filepath, extra_path


def _check_file_already_on_disk(filepath: str) -> bool:
    """
    Check if the file already exists on disk and its size is greater than 0 B.

    :param filepath: destination file path
    :return: True if the file exists, False otherwise
    """
    if not filepath or not os.path.isfile(filepath):
        return False

    # If the file exists and its size is 0, allow overwrites (possibly a failed download)
    if os.path.getsize(filepath) > 0:
        log.debug(f"File {filepath} already on disk.")
        return True
    else:
        log.warning(f"File {filepath} is on disk but has size 0, downloading again.")
        return False


@retry(
    stop=(stop_after_attempt(5) | stop_after_delay(60)),
    wait=wait_fixed(3),
    retry=retry_if_exception_type(DownloadFailed),
    reraise=True,
    after=after_log(log, logging.WARNING),
)
def _download_url(url: str) -> bytes:
    """
    Make a HTTP GET request.

    :param url: URL to download
    :return: response content as bytes
    :raise DownloadFailed: on HTTP GET failure
    """
    try:
        response = requests.get(url, timeout=HTTP_GET_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadFailed(f'Failed to GET "{url}": {e}')
    return response.content


def _get_file_extension_from_url(url: str) -> str:
    """
    Given a file URL, extract the extension of the file.

    :param url: file's URL
    :return: file's extension
    """
    parsed_url = urlparse(url)
    split_path = os.path.splitext(parsed_url.path)

    # Get the extension but remove the leading '.' for easier handling
    extension = split_path[1][1:]
    log.debug(f"Found '{extension}' file extension in URL {url}")
    return extension


def _write_to_disk(filepath: str, content: bytes):
    """
    Write downloaded binary content to disk

    :param filepath: destination filepath
    :param content: binary content
    :raise DownloadFailed: on disk write failure
    """
    try:
        with open(filepath, "wb") as fd:
            fd.write(content)
    except IOError as e:
        log.error(f"Failed to write file {filepath} to disk: {e}")
        raise DownloadFailed(e)
