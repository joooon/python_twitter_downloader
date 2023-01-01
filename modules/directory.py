import configparser
import logging
import os
from collections import defaultdict
from typing import Dict, List
from .config import get_download_directory, get_min_media_for_directory
from .utils import groupdict_from_filename

log = logging.getLogger()


def organize_media(configuration: configparser.ConfigParser):
    """
    Module's entry point. Scan the download directory and move media files to their own subdirectory (organized by
    author.)

    :param configuration: initialized ConfigParser object
    """
    # Scan download directory and build a dictionary counting how many media files have been found for the same author
    download_directory = get_download_directory(configuration)
    log.info(f'Organizing directory {download_directory}')
    media_count = _scan_directory(download_directory)

    # Create subdirectories for authors with enough media files
    threshold = get_min_media_for_directory(configuration)
    _create_new_directories(media_count, threshold, download_directory)

    # Find all existing subdirectories and move matching files
    available_directories = _get_all_subdirectories(download_directory)
    _move_files_to_subdirectory(download_directory, available_directories)


def _create_new_directories(media_count: Dict[str, int], threshold: int, download_directory: str):
    """
    Create new directories if an account has media files in the download directory greater than or equal the threshold.

    :param media_count: dictionary of account and media files count
    :param threshold: minimum number of media files in the download directory to create a subdirectory for the account
    :param download_directory: media files download directory
    """
    for account, media_files in media_count.items():
        if media_files >= threshold:
            new_directory = os.path.join(download_directory, account)
            try:
                os.mkdir(new_directory)
                log.info(f'Created new directory {new_directory} (found {media_files} files)')
            except FileExistsError:
                log.debug(f'Directory {new_directory} already exists')
        else:
            log.debug(f'Not enough media files to create directory {account} (found {media_files})')


def _get_all_subdirectories(download_directory: str) -> List[str]:
    """
    Scan the download directory and returns all available subdirectories.

    :param download_directory: media files download directory
    :return: list of subdirectory names found in download_directory
    """
    subdirectories = []
    with os.scandir(download_directory) as dir_iterator:
        for entry in dir_iterator:
            if entry.is_dir():
                subdirectories.append(entry.name)

    log.debug(f'Found {len(subdirectories)} existing subdirectories')
    return subdirectories


def _move_files_to_subdirectory(download_directory: str, available_directories: List[str]):
    """
    Moves all files that have a matching subdirectory

    :param download_directory: path to download directory
    :param available_directories: list of subdirectories found in download_directory
    """
    files_to_move = defaultdict(list)

    # First generate a list of files to be moved, we don't want to change the structure of the directory while we are
    # scanning it.
    with os.scandir(download_directory) as dir_iterator:
        for entry in dir_iterator:
            if not entry.is_file(follow_symlinks=False):
                continue

            try:
                account_name = groupdict_from_filename(entry.name)['account']
            except ValueError:
                continue

            if account_name in available_directories:
                files_to_move[account_name].append(entry.name)
                log.debug(f'File {entry.name} will be moved into subdirectory {account_name}')

    if not files_to_move:
        log.info('No files need to be moved')
        return

    # Move files
    for subdirectory in files_to_move:
        for filename in files_to_move[subdirectory]:
            full_filename_path = os.path.join(download_directory, filename)
            full_destination_path = os.path.join(download_directory, subdirectory, filename)
            try:
                log.info(f'Moving {filename} into {os.path.join(subdirectory, filename)}')
                os.rename(full_filename_path, full_destination_path)
                log.debug(f'Moved {full_filename_path} into {full_destination_path}')
            except OSError as e:
                log.error(f'Failed to move file {full_filename_path} to {full_destination_path}: {e}')


def _scan_directory(download_directory: str) -> Dict[str, int]:
    """
    Given the download directory, scan all its files and build a dictionary with Tweet's author's account name as key
    and media count as value.

    :param download_directory: path to download directory
    :return: dictionary with account name as key and media file count as value
    """
    media_count = defaultdict(lambda: 0)

    with os.scandir(download_directory) as dir_iterator:
        for entry in dir_iterator:
            if not entry.is_file(follow_symlinks=False):
                log.debug(f'{entry.name} is not a file')
                continue

            try:
                account_name = groupdict_from_filename(entry.name)['account']
                log.debug(f'Found account name {account_name} from file {entry.name}')
                media_count[account_name] += 1
            except ValueError:
                log.debug(f'Unable to find an account name in filename {entry.name}')

    return media_count
