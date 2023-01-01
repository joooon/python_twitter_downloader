import logging
import tweepy
import yaml
from configparser import ConfigParser
from modules.config import get_blacklist_file
from typing import Any, Dict, List, Optional, Tuple, Set

log = logging.getLogger()


def _create_blacklist_file(filepath: str, blacklist: Optional[List[str]] = None):
    """
    Create the blacklist file, with optionally the list of blacklisted tweet IDs.

    :param filepath: path to blacklist file
    :param blacklist: list of tweets IDs as string
    """
    blacklist = blacklist or []
    comment = '# Add your blacklisted tweet IDs in the list below, one per line'
    file_content = yaml.dump({'blacklisted_ids': blacklist})
    log.debug(f'Writing {filepath} with {len(blacklist)} blacklisted tweet IDs')
    try:
        with open(filepath, 'w') as fd:
            fd.write(f'{comment}\n{file_content}')
    except IOError as e:
        log.error(f'Failed to write blacklist file: {e}')
        raise


def _handle_media_type_video(media: Dict[str, Any]) -> str:
    """
    Media type 'video' requires us to select the URL with the highest bitrate.

    :param media: tweepy.models.Status.extended_entities dictionary
    :return: URL to video variant with the highest bitrate
    """
    variants_list = media['video_info']['variants']
    highest_quality_variant = variants_list.pop()
    log.debug(
        f"Considering video variant {highest_quality_variant['content_type']} "
        f"{highest_quality_variant.get('bitrate', '(no bitrate)')}: {highest_quality_variant['url']}"
    )

    # Discard video formats that don't specify a bitrate (mpeg) if any other format that does is available.
    while variants_list and not highest_quality_variant.get('bitrate'):
        log.debug(
            f"Discarding video variant {highest_quality_variant['content_type']} (no bitrate specified): "
            f"{highest_quality_variant['url']}"
        )
        highest_quality_variant = variants_list.pop()
        log.debug(
            f"Considering video variant {highest_quality_variant['content_type']} "
            f"{highest_quality_variant.get('bitrate', '(no bitrate)')}: {highest_quality_variant['url']}"
        )

    # Pick the variant with the highest bitrate
    for variant in variants_list:
        if variant.get('bitrate') and variant['bitrate'] > highest_quality_variant['bitrate']:
            log.debug(
                f"Promoting video variant {variant['content_type']} {variant['bitrate']} (better quality): "
                f"{variant['url']}"
            )
            highest_quality_variant = variant
        else:
            log.debug(
                f"Discarding video variant {variant['content_type']} "
                f"{variant.get('bitrate', '(no bitrate)')} (inferior quality): {variant['url']}"
            )

    if highest_quality_variant.get('bitrate'):
        log.debug(
            f"Using video variant {highest_quality_variant['url']} with bitrate={highest_quality_variant['bitrate']}"
        )
    else:
        log.debug(f"Using video variant {highest_quality_variant['url']} (no bitrate specified)")

    return highest_quality_variant['url']


def _handle_media_type_animated_gif(media: Dict[str, Any]) -> str:
    """
    Media type 'animated_gif' handling. There is a variants list but it contains only one element.

    :param media: tweepy.models.Status.extended_entities dictionary
    :return: URL to mp4 video
    """
    log.debug(f"Found media type {media['type']}")
    variant = media['video_info']['variants'][0]
    return variant['url']


def _load_blacklisted_tweets_file(filepath: str) -> List[str]:
    """
    Load the list of blacklisted tweets IDs.

    :param filepath: path to blacklist file
    :return: list of blacklisted tweet IDs
    """
    try:
        with open(filepath) as fd:
            file_content = yaml.safe_load(fd)
            return file_content['blacklisted_ids']
    except FileNotFoundError:
        log.info(f'Creating default blacklist file in {filepath}')
        _create_blacklist_file(filepath)
        return []
    except IOError as e:
        log.error(f'Failed to load blacklist file {filepath}: {e}')
        raise
    except yaml.YAMLError as e:
        log.error(f'Failed to parse blacklist file {filepath}: {e}')
        raise
    except KeyError as e:
        log.error(f'Blacklist file {filepath} is malformed: expected key {e}')
        log.error(f'Note: You can delete the file and a new one will be created on the next run')
        raise


def get_all_media_from_tweet(tweet: tweepy.models.Status) -> List[Tuple[str, bool]]:
    """
    Given a tweet, return all media found in it.

    :param tweet: tweepy.models.Status object
    :return: dict of media URLs as key and size information for pictures as value
    """
    source_tweet = tweet.id_str
    source_user = tweet.user.screen_name

    if not hasattr(tweet, 'extended_entities'):
        warn_message = f'Unable to detect media for status https://twitter.com/i/web/status/{source_tweet}'

        if hasattr(tweet, 'text'):
            single_line_text = tweet.text.replace('\n', ' ')
            log.warning(f'{warn_message} - [{source_user}] {single_line_text}')
        elif hasattr(tweet, 'full_text'):
            single_line_text = tweet.full_text.replace('\n', ' ')
            log.warning(f'{warn_message} - [{source_user}] {single_line_text}')
        else:
            log.warning(warn_message)
        return []

    media_urls = []
    for media in tweet.extended_entities['media']:
        if media['type'] == 'animated_gif':
            media_urls.append((_handle_media_type_animated_gif(media), False))
        elif media['type'] == 'video':
            media_urls.append((_handle_media_type_video(media), False))
        elif media['type'] == 'photo':
            media_urls.append((media['media_url_https'], True))
        else:
            log.error(f"Unrecognized media type '{media['type']}' from tweet ID {source_tweet}")
            continue

    log.debug(f'Found {len(media_urls)} media URLs from tweet {source_user}/{source_tweet}')
    return media_urls


def filter_blacklisted_tweets(
        configuration: ConfigParser,
        tweets_list: tweepy.models.ResultSet
) -> List[tweepy.models.Status]:
    """
    Remove the tweets that have been blacklisted from the list of available tweets.

    :param configuration: initialized ConfigParser object
    :param tweets_list: list of all available tweets
    :return: filtered list of tweets
    """
    blacklist_file = get_blacklist_file(configuration)
    blacklisted_tweets = _load_blacklisted_tweets_file(blacklist_file)
    log.info(f'Found {len(blacklisted_tweets)} blacklisted tweets')

    filtered_list = []
    for tweet in tweets_list:
        if tweet.id_str in blacklisted_tweets:
            log.debug(f'Removing blacklisted tweet ID {tweet.id_str}')
        else:
            filtered_list.append(tweet)
    return filtered_list


def load_liked_tweets(api: tweepy.API, count: int = 200) -> tweepy.models.ResultSet:
    """
    Load liked tweets from the authenticating user.

    :param api: tweepy API object
    :param count: number of results to retrieve
    :return: list of tweepy.models.Status objects
    """
    # https://docs.tweepy.org/en/latest/api.html#tweepy.API.get_favorites
    tweets_list = api.get_favorites(count=count, tweet_mode='extended')
    log.info(f'Loaded {len(tweets_list)} tweets')
    return tweets_list


def load_single_tweet(api: tweepy.API, tweet_id: str) -> tweepy.models.ResultSet:
    """
    Load a single tweet given its ID and return a list containing the one tweet.

    :param api: tweepy API object
    :param tweet_id: ID of the twitter status to download
    :return: list of tweepy.models.Status objects (limited to the specified tweet)
    """
    # https://docs.tweepy.org/en/latest/api.html#tweepy.API.lookup_statuses
    tweets_list = api.lookup_statuses(id=[tweet_id], tweet_mode='extended')
    log.info(f'Loaded {len(tweets_list)} tweets')
    return tweets_list


def update_tweets_blacklist(
        configuration: ConfigParser,
        new_blacklisted_tweets: List[str],
        tweets_list: tweepy.models.ResultSet
):
    """
    Update the blacklist file given a list of new blacklisted tweets.

    :param configuration: initialized ConfigParser object
    :param new_blacklisted_tweets: list of tweet IDs to add to blacklist
    :param tweets_list: list of all available tweets
    """
    # Load all Tweet IDs
    tweet_ids_set: Set[str] = set()
    for tweet in tweets_list:
        tweet_ids_set.add(tweet.id_str)

    # Get the Tweet IDs from blacklist and filter out the ones that don't appear in the list returned by Twitter
    blacklist_file = get_blacklist_file(configuration)
    previous_blacklisted_tweets = _load_blacklisted_tweets_file(blacklist_file)
    valid_blacklisted_tweets = [t for t in previous_blacklisted_tweets if t in tweet_ids_set]

    # Return if there are no changes to the blacklist
    if (not new_blacklisted_tweets
            and len(valid_blacklisted_tweets) == len(previous_blacklisted_tweets)):
        log.debug("Blacklist doesn't need updating")
        return

    log.info(
        f'Will remove {len(previous_blacklisted_tweets) - len(valid_blacklisted_tweets)} '
        'expired Tweet IDs from blacklist'
    )

    # Merge the blacklists and write to file
    full_blacklist = list(set(valid_blacklisted_tweets + new_blacklisted_tweets))
    _create_blacklist_file(blacklist_file, full_blacklist)

    blacklisted_new = len(new_blacklisted_tweets)
    blacklisted_expired = len(previous_blacklisted_tweets) - len(valid_blacklisted_tweets)
    log.info(
        f'Saved blacklist file with {len(full_blacklist)} IDs '
        f'({blacklisted_new} added, {blacklisted_expired} removed)'
    )
