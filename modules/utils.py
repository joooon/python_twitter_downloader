import logging
import re
from typing import Dict

# Expected filename format for downloaded media
FILENAME_REGEX = "(?P<account>\w+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<id>\d*)_(?P<media_count>\d).(?P<extension>\w+)"
COMPILED_FILENAME_REGEX = re.compile(FILENAME_REGEX)

log = logging.getLogger()


def groupdict_from_filename(filename: str) -> Dict[str, str]:
    """
    Parse the given filename and return a dictionary with the extracted groups if it matches FILENAME_REGEX.
    Example return value:
      {'account': 's_thegardener',
       'date': '2022-02-07',
       'id': '1490761491066552320',
       'media_count': '3',
       'extension': 'jpg'}

    :param filename: filename to parse, ie. 's_thegardener_2022-02-07_1490761491066552320_3.jpg'
    :return: account name
    :raise ValueError: if the filename failed to match the regular expression
    """
    matched = COMPILED_FILENAME_REGEX.match(filename)
    if not matched:
        raise ValueError(f'Failed to parse file {filename}')

    return matched.groupdict()
