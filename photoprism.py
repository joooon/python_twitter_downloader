#! /usr/bin/env python3
"""
PhotoPrism utility

Connect to the PhotoPrism database and DO THINGS!!!!
"""
import argparse
import logging

from modules import config, mysql, photoprism

# Logging setup
log = logging.getLogger()
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(module)s:%(lineno)d %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


def parse_args():
    parser = argparse.ArgumentParser(description="Manage media indexed by PhotoPrism.")
    parser.add_argument("--debug", action="store_true", help="set logging to DEBUG level")
    parser.add_argument("--tag", action="store_true", help="create and manage media labels")
    parser.add_argument("--update-recent", action="store_true", help="update the recent media album")
    return parser.parse_args()


def main(args: argparse.Namespace):
    log.info("Starting PhotoPrism utility")
    configuration = config.get_configuration()
    db_connection = mysql.connect(configuration)

    if not (args.tag or args.update_recent):
        log.warning("No operation selected, exiting without taking any action")
        return

    # Update media labels
    if args.tag:
        photoprism.label_known_artists(db_connection, configuration)

    # Update Recent media album
    if args.update_recent:
        photoprism.update_recent_pictures_album(db_connection, configuration)


if __name__ == "__main__":
    args = parse_args()
    if args.debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    main(args)
