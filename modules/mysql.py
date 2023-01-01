import logging
from configparser import ConfigParser
from MySQLdb import Connection, MySQLError, _mysql
from .config import get_photoprism_db_config

log = logging.getLogger()


def connect(configuration: ConfigParser) -> Connection:
    """

    :param configuration:
    :return:
    """
    try:
        auth_dict = get_photoprism_db_config(configuration)
        log.debug(f"Attempting SQL connection with parameters: {', '.join([f'{k}={v}' for k, v in auth_dict.items()])}")
    except MySQLError as e:
        log.error(f'Failed to connect to SQL server: {e}')
        raise
    port = int(auth_dict.pop('port'))  # 'port' must be an integer
    return _mysql.connect(port=port, **auth_dict)


def execute_query(connection: Connection, query: str) -> _mysql.result:
    """

    :param connection:
    :param query:
    :return:
    """
    try:
        log.debug(f'Executing query "{query}"')
        connection.query(query)
    except MySQLError as e:
        log.error(f'Failed to query database: {e}')
        log.error(f'Query was: "{query}"')
        raise

    return connection.store_result()
