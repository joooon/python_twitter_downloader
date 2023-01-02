#! /usr/bin/env python3
"""
Twitter downloader.

Connect to twitter, check the liked tweets of the authenticated user and download all pictures found.
"""
import argparse
import logging
from modules import auth, config, directory, media, twitter

# Logging setup
log = logging.getLogger()
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(module)s:%(lineno)d %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def parse_args():
    parser = argparse.ArgumentParser(description='Download media of the tweets liked by the authenticating user.')
    parser.add_argument('--debug', action='store_true', help='set logging to DEBUG level')
    parser.add_argument('--organize', action='store_true', help='create and manage subdirectories')
    parser.add_argument('--disable-blacklist', action='store_true', help='disable filtering of blacklisted tweets')
    return parser.parse_args()


def main(args: argparse.Namespace):
    downloaded_tweets = 0
    downloaded_media_count = 0
    new_blacklisted_tweets = []

    # Load configuration and connect to the Twitter API
    configuration = config.get_configuration()
    twitter_api = auth.get_authenticated_api(configuration)
    full_tweets_list = twitter.load_liked_tweets(twitter_api)

    # Filter blacklisted tweets
    if not args.disable_blacklist:
        tweets_list = twitter.filter_blacklisted_tweets(configuration, full_tweets_list)
        log.debug(f'{len(tweets_list)} tweets available after filtering')
    else:
        tweets_list = full_tweets_list

    # Process tweets one by one
    for tweet in tweets_list:
        log.debug(f'Processing tweet https://twitter.com/i/web/status/{tweet.id_str}')
        tweet_media_count, media_found = media.download_media(tweet, configuration)
        if tweet_media_count > 0:
            downloaded_tweets += 1
            downloaded_media_count += tweet_media_count
        elif not media_found and not args.disable_blacklist:
            new_blacklisted_tweets.append(tweet.id_str)
            log.debug(f'Blacklisted tweet ID {tweet.id_str}')

    log.info(f'Downloaded {downloaded_media_count} media files from {downloaded_tweets} of {len(tweets_list)} tweets.')

    # Update blacklist
    if not args.disable_blacklist:
        twitter.update_tweets_blacklist(configuration, new_blacklisted_tweets, full_tweets_list)

    # Move media to subdirectories if needed
    if args.organize:
        directory.organize_media(configuration)


if __name__ == '__main__':
    args = parse_args()
    if args.debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    try:
        main(args)
    except Exception as e:
        log.error(f'Uncaught error while processing request: {e}')
