import tweepy
from configparser import ConfigParser
from modules.config import get_auth_pairs


def get_authenticated_api(configuration: ConfigParser) -> tweepy.API:
    """
    Load Twitter credentials and initialize the tweepy API.

    :param configuration: initialized ConfigParser object.
    :return: authenticated tweepy API object.
    """
    auth_pair, token_pair = get_auth_pairs(configuration)
    auth = tweepy.OAuth1UserHandler(*auth_pair)
    auth.set_access_token(*token_pair)
    return tweepy.API(auth)
