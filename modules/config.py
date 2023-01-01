"""
Handle configuration file.
"""
import configparser
import logging
from typing import Dict, Tuple

DEFAULT_CONFIG_FILE = 'config.ini'
REQUIRED_CONFIG_STRUCT = {
    'auth': ['consumer_key', 'consumer_secret'],
    'token': ['access_token', 'access_token_secret'],
    'file': ['download_directory', 'blacklist_file', 'tags_file'],
    'directory': ['create_dir_after_files'],
    'photoprism_db': ['host', 'port', 'database', 'user', 'password'],
    'photoprism_utility': ['recent_media_hours_delta']
}

log = logging.getLogger()


class ConfigException(Exception):
    """ Generic configuration exception. """
    ...


def _load_configuration(config_file: str) -> configparser.ConfigParser:
    """
    Read the configuration file and return an initialized ConfigParser object.

    :param config_file: path to configuration file.
    :return: ConfigParser object.
    """
    log.info(f'Loading configuration from {config_file}')
    config = configparser.ConfigParser()
    config.read(config_file)
    _validate_configuration(config)
    return config


def _validate_configuration(config: configparser.ConfigParser):
    """
    Assert the configuration file contains REQUIRED_CONFIG_STRUCT.

    :param config: initialized ConfigParser object.
    :raise ConfigException: on validation failure.
    """
    for section in REQUIRED_CONFIG_STRUCT:
        if section not in config:
            log.error(f"Missing required section '{section}' in configuration file.")
            raise ConfigException(f"Section '{section}' missing")

    for section in REQUIRED_CONFIG_STRUCT:
        for key in REQUIRED_CONFIG_STRUCT[section]:
            if not config[section].get(key):
                log.error(f"Missing required key '{key}' in section '{section}' in configuration file.")
                raise ConfigException(f"Key '{key}' missing")


def get_auth_pairs(config: configparser.ConfigParser) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    """
    Return the authentication keys and the oAuth token.

    :param config: initialized ConfigParser object
    :return: tuple of authentication pair and token pair tuples.
    """
    auth_pair = (config['auth']['consumer_key'], config['auth']['consumer_secret'])
    token_pair = (config['token']['access_token'], config['token']['access_token_secret'])
    log.debug('Successfully loaded authentication and token pairs.')
    return auth_pair, token_pair


def get_blacklist_file(config: configparser.ConfigParser) -> str:
    """
    Return the path to the blacklist YAML file

    :param config: initialized ConfigParser object
    :return: path to blacklist file
    """
    return config['file']['blacklist_file']


def get_configuration(from_file: str = DEFAULT_CONFIG_FILE) -> configparser.ConfigParser:
    """
    Return configuration loaded from target file.

    :param from_file: configuration file to read
    :return: ConfigParser object
    """
    return _load_configuration(from_file)


def get_download_directory(config: configparser.ConfigParser) -> str:
    """
    Retrieve the destination directory for downloads from config.

    :param config: initialized ConfigParser object
    :return: user-specified path
    """
    return config['file']['download_directory']


def get_min_media_for_directory(config: configparser.ConfigParser) -> int:
    """
    Retrieve the minimum amount of media files downloaded from a certain account before creating a directory

    :param config: initialized ConfigParser object
    :return: user-specified number
    """
    return int(config['directory']['create_dir_after_files'])


def get_photoprism_db_config(config: configparser.ConfigParser) -> Dict[str, str]:
    """
    Return a dictionary with PhotoPrism SQL database connection details.

    { 'host': 'localhost',
      'port': 3306,
      'db': 'photoprism',
      'user': 'photoprism',
      'passwd': 'password' }

    :param config: initialized ConfigParser object
    :return: dictionary with configuration values
    """
    return dict(config['photoprism_db'])


def get_photoprism_utility_config(config: configparser.ConfigParser) -> Dict[str, str]:
    """
    Return a dictionary with parameters for the PhotoPrism utility script.

    :param config: initialized ConfigParser object
    :return: dictionary with configuration values
    """
    return dict(config['photoprism_utility'])


def get_tagmap_file(config: configparser.ConfigParser) -> str:
    """
    Return the path to the tags YAML file

    :param config: initialized ConfigParser object
    :return: path to blacklist file
    """
    return config['file']['tags_file']
