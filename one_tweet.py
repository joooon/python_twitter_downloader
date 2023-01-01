#! /usr/bin/env python3
"""
Connect to twitter, download media from a specified tweet.
"""
import argparse
import logging
from modules import auth, config, media, twitter

# Logging setup
log = logging.getLogger()
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(module)s:%(lineno)d %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def parse_args():
    parser = argparse.ArgumentParser(description='Download media of the specified Twitter status')
    parser.add_argument('--debug', action='store_true', help='set logging to DEBUG level')
    parser.add_argument('status_id', metavar='TWITTER_ID', type=str, help='Twitter status ID')
    return parser.parse_args()


def main(args: argparse.Namespace):
    # Load configuration and connect to the Twitter API
    configuration = config.get_configuration()
    twitter_api = auth.get_authenticated_api(configuration)
    tweets_list = twitter.load_single_tweet(twitter_api, args.status_id)

    if not tweets_list:
        log.error(f'Unable to find Twitter status https://twitter.com/i/web/status/{args.status_id}')
        return

    tweet = tweets_list[0]
    log.debug(f'Processing tweet https://twitter.com/i/web/status/{tweet.id_str}')
    downloaded_media_count, media_found = media.download_media(tweet, configuration)
    log.info(f'Downloaded {downloaded_media_count} media files.')


if __name__ == '__main__':
    args = parse_args()
    if args.debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    main(args)
