import logging
import yaml
from configparser import ConfigParser
from dataclasses import dataclass
from datetime import datetime, timedelta
from MySQLdb import Connection
from typing import Dict, List, Set
from . import mysql, config

# Timestamp format used by PhotoPrism
PHOTOPRISM_TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'

# Tagger's label.
# This label is assigned to all images that have been processed by this module so that they are not modified a second
# time. This allows for the user to correct any mismatch without having their changes overwritten later.
IMAGE_PROCESSED_BY_TAGGER_LABEL = 'hermes-conrad-was-here'

# Slug of the album to use to store recent pictures
RECENT_ALBUM_SLUG = 'recent'

log = logging.getLogger()


class PhotoPrismException(Exception):
    """ Generic exception thrown by this module. """
    ...


@dataclass
class Label:
    """ Represent a PhotoPrism label, with its name (slug) and database record ID. """
    id: str
    slug: str


def label_known_artists(connection: Connection, configuration: ConfigParser):
    """
    Scan the tag map file and update the pictures in PhotoPrism with the specified labels.
    The tag map file consists in a YAML dictionary with Twitter username as key and a list of labels to associate with
    their picture as value. For example:
        nasahqphoto:
          - photo
          - topic-space

    Note that the label name may not reflect its slug (ie. 'fandom:toh' becomes 'fandom-toh' in the database). Search
    for the label in PhotoPrism, its slug will be shown in the search bar.

    :param connection: initialized MySQLdb connection to database
    :param configuration: initialized ConfigParser object
    """
    log.info('Running autotagger on PhotoPrism database')

    tagmap_filepath = config.get_tagmap_file(configuration)
    tagmap = _load_tagmap_file(tagmap_filepath)
    available_labels = _get_all_available_labels(connection)
    processed_by_tagger_label = _get_tagger_label(available_labels)

    # Go through the artists in tagmap file and check all their pictures
    for twitter_user, required_labels_for_user in tagmap.items():
        _label_pictures_for_user(
            connection, twitter_user, available_labels, required_labels_for_user, processed_by_tagger_label
        )


def update_recent_pictures_album(connection: Connection, configuration: ConfigParser):
    """
    Find all the recent media (items added to PhotoPrism between now and the time specified in the configuration) and
    add them to the 'Recent' album

    :param connection: initialized MySQLdb connection to database
    :param configuration: initialized ConfigParser object
    """
    log.info('Updating recent media album')

    # Find the recent album UID
    recent_album_uid = _get_album_uid(connection, RECENT_ALBUM_SLUG)

    # Find UIDs of recent pictures
    delta_hours = config.get_photoprism_utility_config(configuration)['recent_media_hours_delta']
    search_limit = datetime.now() - timedelta(hours=int(delta_hours))
    picture_uids = _get_picture_uids_after_timestamp(connection, search_limit)
    log.info(f'Adding {len(picture_uids)} media items to album')

    # Replace the recent media in album
    _delete_all_media_in_album(connection, recent_album_uid)
    _add_media_to_album(connection, recent_album_uid, picture_uids)


def _add_label_to_picture(connection: Connection, picture_id: str, label: Label):
    """
    Assign the specified label to the picture and update the counter in the 'labels' table.

    :param connection: initialized MySQLdb connection to database
    :param picture_id: PhotoPrism ID of the picture to search for
    :param label: Label tuple to assign to the picture
    """
    log.debug(f'Adding label {label.slug} with ID {label.id} to picture {picture_id}')
    query = (
        'BEGIN NOT ATOMIC '
        'INSERT INTO photos_labels (photo_id, label_id, label_src, uncertainty) '
        f"VALUES ({picture_id}, {label.id}, 'manual', 0); "
        'UPDATE labels SET photo_count = photo_count + 1 '
        f'WHERE id = {label.id}; '
        'END'
    )
    mysql.execute_query(connection, query)


def _add_media_to_album(connection: Connection, album_uid: str, picture_uids: Set[str]):
    """
    Add all specified picture UIDs to the specified album

    :param connection: initialized MySQLdb connection to database
    :param album_uid: UID of the destination album
    :param picture_uids: set of UIDs of the pictures to add
    """
    if not picture_uids:
        log.debug(f'No images to add to album {album_uid}, aborting query')
        return

    log.debug(f'Adding {len(picture_uids)} media items to album {album_uid}')

    # Prepare all VALUES for the INSERT INTO operation
    now_timestamp = datetime.now().strftime(PHOTOPRISM_TIMESTAMP_FORMAT)
    sql_values = []
    for picture_uid in picture_uids:
        sql_values.append(f"('{picture_uid}', '{album_uid}', 0, 0, 0, '{now_timestamp}', '{now_timestamp}')")
    sql_values = ', '.join(sql_values)

    query = (
        'INSERT INTO photos_albums '
        '(photo_uid, album_uid, photos_albums.order, hidden, missing, created_at, updated_at) '
        f'VALUES {sql_values}'
    )
    mysql.execute_query(connection, query)


def _create_tagmap_file(filepath: str):
    """
    Create an empty tag map file.

    :param filepath: path to blacklist file
    """
    comment = (
        '# Specify the username and the tags you want applied to their media.\n'
        '# Example:\n'
        '#   nasahqphoto:\n'
        '#     - photo\n'
        '#     - topic-space'
    )
    log.info(f'Creating new tag map file {filepath}')
    try:
        with open(filepath, 'w') as fd:
            fd.write(comment)
    except IOError as e:
        log.error(f'Failed to write tag map file: {e}')
        raise


def _delete_all_media_in_album(connection: Connection, album_uid: str):
    """
    Remove the association between media and the specified album.

    :param connection: initialized MySQLdb connection to database
    :param album_uid: UID of the album to empty
    """
    log.debug(f'Deleting all media in ablum {album_uid}')
    query = f"DELETE FROM photos_albums WHERE album_uid = '{album_uid}'"
    mysql.execute_query(connection, query)


def _get_album_uid(connection: Connection, album_slug: str) -> str:
    """
    Search the album table of PhotoPrism and return the UID of the specified album.

    :param connection: initialized MySQLdb connection to database
    :param album_slug: slug of the album to lookup in the database

    :return: UID of the specified album

    :raise PhotoPrismException: if the query doesn't return exactly one record.
    """
    log.debug(f'Looking up UID of PhotoPrism album with slug {album_slug}')
    query = f"SELECT album_uid FROM albums WHERE album_slug = '{album_slug}'"
    result = mysql.execute_query(connection, query)
    result_rows = result.fetch_row(0)

    if not result_rows:
        log.error(f"No PhotoPrism album with slug '{album_slug}' found in database. Please create it manually")
        raise PhotoPrismException(f"Unable to find PhotoPrism album with slug '{album_slug}'")
    elif len(result_rows) > 1:
        log.error(f"Unexpected multiple results for album slug '{album_slug}': {', '.join(result_rows)}")
        raise PhotoPrismException(f"Expecting exactly one UID for album '{album_slug}', got {len(result_rows)}")

    album_uid = result_rows[0][0].decode('utf-8')
    log.debug(f'Found UID {album_uid} for album {album_slug}')
    return album_uid


def _get_all_available_labels(connection: Connection) -> List[Label]:
    """
    Query the database table 'label' for all available PhotoPrism labels and their IDs.

    :param connection: initialized MySQLdb connection to database

    :return: list of Label tuples found in database
    """
    log.debug(f'Fetching available labels from DB')
    query = 'SELECT id, label_slug FROM labels'
    result = mysql.execute_query(connection, query)

    try:
        return [Label(row[0].decode('utf-8'), row[1].decode('utf-8')) for row in result.fetch_row(0)]
    except UnicodeDecodeError as e:
        log.error(f'Failed to decode value with UTF-8: {e}')
        raise


def _get_label_ids_for_picture(connection: Connection, picture_id: str) -> Set[str]:
    """
    Find the label IDs associated with the specified picture ID.

    :param connection: initialized MySQLdb connection to database
    :param picture_id: PhotoPrism ID of the picture to search for

    :return: set of IDs of labels associated with the picture
    """
    log.debug(f'Fetching label IDs for picture {picture_id}')
    query = f'SELECT label_id FROM photos_labels WHERE photo_id = {picture_id}'
    result = mysql.execute_query(connection, query)
    try:
        return {row[0].decode('utf-8') for row in result.fetch_row(0)}
    except UnicodeDecodeError as e:
        log.error(f'Failed to decode label_id value with UTF-8: {e}')
        raise


def _get_picture_ids_for_user(connection: Connection, twitter_user: str) -> Set[str]:
    """
    Search the PhotoPrism database for all the pictures associated with the specified user. The search is pretty dumb
    and relies on the naming convention of the Twitter scanner. It expect the picture's file name to start with the
    username we are looking for.

    :param connection: initialized MySQLdb connection to database
    :param twitter_user: Twitter user to search for

    :return: set of picture IDs associated with the user
    """
    log.debug(f'Fetching picture IDs for user {twitter_user}')
    query = f"SELECT id FROM photos WHERE photo_name LIKE '{twitter_user}%'"
    result = mysql.execute_query(connection, query)
    try:
        return {id_num[0].decode('utf-8') for id_num in result.fetch_row(0)}
    except UnicodeDecodeError as e:
        log.error(f'Failed to decode ID value with UTF-8: {e}')
        raise


def _get_picture_uids_after_timestamp(connection: Connection, timestamp: datetime) -> Set[str]:
    """
    Search the PhotoPrism database for all the pictures that have been added to the database after the specified
    timestamp. Note that this function returns the pictures' UID and NOT their ID.

    :param connection: initialized MySQLdb connection to database
    :param timestamp: oldest picture (in terms of DB record creation) to be returned

    :return: set of picture UIDs added after the specified timestamp
    """
    sql_timestamp = timestamp.strftime(PHOTOPRISM_TIMESTAMP_FORMAT)
    log.debug(f'Fetching picture UIDs added to PhotoPrism after {sql_timestamp}')
    query = f"SELECT photo_uid FROM photos WHERE created_at > '{sql_timestamp}'"
    result = mysql.execute_query(connection, query)
    try:
        return {uid_num[0].decode('utf-8') for uid_num in result.fetch_row(0)}
    except UnicodeDecodeError as e:
        log.error(f'Failed to decode ID value with UTF-8: {e}')
        raise


def _get_tagger_label(available_labels: List[Label]) -> Label:
    """
    Check if IMAGE_PROCESSED_BY_TAGGER_LABEL exists in the DB, we don't create it here to avoid messing too much with
    the database.

    :param available_labels: list of Label tuples as returned by _get_all_available_labels()

    :return: Label tuple for the tagger

    :raise TaggerException: if the tagger label doesn't exist in the database
    """
    for label in available_labels:
        if label.slug == IMAGE_PROCESSED_BY_TAGGER_LABEL:
            log.debug(f'Found tagger label {label.slug} in database')
            return label

    log.error(f'Tagger label {IMAGE_PROCESSED_BY_TAGGER_LABEL} not found, please create it manually')
    raise PhotoPrismException(f'Required label {IMAGE_PROCESSED_BY_TAGGER_LABEL} not found in database')


def _label_picture(
        connection: Connection,
        picture_id: str,
        expected_labels: List[Label],
        processed_by_tagger_label: Label,
) -> bool:
    """
    Ensure the specified picture has all the expected labels associated to it. Skip processing if the picture is labeled
    with IMAGE_PROCESSED_BY_TAGGER_LABEL.

    :param connection: initialized MySQLdb connection to database
    :param picture_id: PhotoPrism ID of the picture to process
    :param expected_labels: list of Label tuples to associate with the picture
    :param processed_by_tagger_label: Label tuple representing IMAGE_PROCESSED_BY_TAGGER_LABEL

    :return: False if the picture is already tagged with IMAGE_PROCESSED_BY_TAGGER_LABEL, True otherwise
    """
    current_label_ids = _get_label_ids_for_picture(connection, picture_id)

    # Skip pictures already processed by this script
    if processed_by_tagger_label.id in current_label_ids:
        log.debug(f'Skipping image {picture_id} (already tagged)')
        return False

    # Find all labels that need to be applied to the picture
    missing_labels = []
    for label in expected_labels:
        if label.id not in current_label_ids:
            missing_labels.append(label)

    if not missing_labels:
        log.debug(f'Image {picture_id} has no missing labels')
        return True

    for label in missing_labels:
        _add_label_to_picture(connection, picture_id, label)

    return True


def _label_pictures_for_user(
        connection: Connection,
        twitter_user: str,
        available_labels: List[Label],
        required_labels_for_user: List[str],
        processed_by_tagger_label: Label
):
    """
    Assign all required labels to the pictures of the specified Twitter user.

    :param connection: initialized MySQLdb connection to database
    :param twitter_user: Twitter user to search for
    :param available_labels: list of Label tuples available in the database
    :param required_labels_for_user: list of Label tuples that should be assigned to all pictures
    :param processed_by_tagger_label: Label tuple representing IMAGE_PROCESSED_BY_TAGGER_LABEL
    """
    log.debug(f'Processing twitter user {twitter_user}')

    # Get the IDs of the labels that should be applied to the pictures
    expected_labels = []
    for label in available_labels:
        if label.slug in required_labels_for_user:
            expected_labels.append(label)
            required_labels_for_user.remove(label.slug)  # This is useful for logging in case of errors

    # Throw an error if one or more required label IDs do not exist in the database
    if required_labels_for_user:
        log.error(
            f'One or more required labels for user {twitter_user} are missing, cannot continue. '
            f"Please assign the following labels to at least one picture: {', '.join(required_labels_for_user)}"
        )
        return
    else:
        log.debug(
            f"Found required labels {', '.join([f'{label.slug} (id={label.id})' for label in expected_labels])} "
            f'for user {twitter_user}'
        )

    picture_ids = _get_picture_ids_for_user(connection, twitter_user)
    log.debug(f'Found {len(picture_ids)} pictures indexed for user {twitter_user}')

    # Scan all pictures and check their labels
    updated_pictures_count = 0
    for picture in picture_ids:
        if _label_picture(connection, picture, expected_labels, processed_by_tagger_label):
            _mark_picture_as_processed(connection, picture, processed_by_tagger_label)
            updated_pictures_count += 1

    if updated_pictures_count:
        log.info(f'Updated {updated_pictures_count} of {len(picture_ids)} pictures for user {twitter_user}')
    else:
        log.debug(f'Updated {updated_pictures_count} of {len(picture_ids)} pictures for user {twitter_user}')


def _load_tagmap_file(filepath: str) -> Dict[str, List[str]]:
    """
    Load the tag map file or create a new one if it doesn't exist.

    :param filepath: path to tag map file

    :return: contents of tag map file
    """
    try:
        with open(filepath) as fd:
            return yaml.safe_load(fd)
    except FileNotFoundError:
        log.info(f'Creating default tag map file in {filepath}')
        _create_tagmap_file(filepath)
        return {}
    except IOError as e:
        log.error(f'Failed to load tag map file {filepath}: {e}')
        raise
    except yaml.YAMLError as e:
        log.error(f'Failed to parse tag map file {filepath}: {e}')
        raise
    except KeyError as e:
        log.error(f'Tag map file {filepath} is malformed: expected key {e}')
        log.error(f'Note: You can delete the file and a new one will be created on the next run')
        raise


def _mark_picture_as_processed(connection: Connection, picture_id: str, processed_by_tagger_label: Label):
    """
    Assign the IMAGE_PROCESSED_BY_TAGGER_LABEL label to the specified picture

    :param connection: initialized MySQLdb connection to database
    :param picture_id: PhotoPrism ID of the picture to process
    :param processed_by_tagger_label: Label tuple representing IMAGE_PROCESSED_BY_TAGGER_LABEL
    """
    _add_label_to_picture(connection, picture_id, processed_by_tagger_label)
