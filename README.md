# Twitter Media Downloader
Automatically downloads all media files found in the user's liked tweets.

## Known issues and limitations
This script uses the API v1.1 of Twitter and it's only as smart as the API allows it to be. This means that we are bound to some limitations out of our control. Most interestingly:
* Only the 200 most recent likes are returned by the API;
* The returned list of liked tweets is chronologically sorted by publication date, which means that if you like a tweet posted in the not-so-near past it may not be included in the list. If you can't find your recently liked tweet media in the directory, you may need to download it manually (use `one_tweet.py`.)
* The API calls are rate-limited for both the [GET favorites/list](https://developer.twitter.com/en/docs/twitter-api/v1/tweets/post-and-engage/api-reference/get-favorites-list) and the [GET statuses/lookup](https://developer.twitter.com/en/docs/twitter-api/v1/tweets/post-and-engage/api-reference/get-statuses-lookup) calls.

## Getting started
### Configuration and Authentication
Go to [Twitter Developer](https://developer.twitter.com/en/portal/projects-and-apps) and create a new App. Copy the generated API key and secret in `config.ini` (these would be the "consumer" credentials). Also generate an access token and secret and add them to `config.ini`.

Set the path where you wish for your files to be downloaded into and the blacklist file (used to ignore certain statuses IDs, such as the ones containing no media, or the ones manually specified). The blacklist file will be generated automatically if it doesn't exist. Tweet IDs are added and removed by the script, but you can also add your own.

You can ignore the `tags_file` configuration key and the other sections if you don't plan to use the PhotoPrism integration.

### Running via CLI
You should have [pyenv](https://github.com/pyenv/pyenv) installed to manage the Python interpreter's version.

Run:
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python download.py --help
```
You can also download media in any tweet by supplying its ID to the `one_tweet.py` script. For example, for the URL https://twitter.com/koirakoirana/status/1557022684373983234:
```
python one_tweet.py 1557022684373983234
```


### Running with Docker
Run:
```
docker build -t twitter-downloader .
docker run --rm -v path/to/your/pics:/container/download/path twitter-downloader
```

## Options
```
$ ./download.py --help
usage: download.py [-h] [--debug] [--organize] [--disable-blacklist]

Download media of the tweets liked by the authenticating user.

options:
  -h, --help           show this help message and exit
  --debug              set logging to DEBUG level
  --organize           create and manage subdirectories
  --disable-blacklist  disable filtering of blacklisted tweets
```
The `--organize` flag groups media files from the same authors in subdirectories, when the number of media files is equal to or greater than `create_dir_after_files`.

## PhotoPrism integration
Use at your own risk. If it breaks, you get to keep both parts.

The `photoprism.py` script requires `requirements-photoprism.txt` to be installed and can help manage the media files in PhotoPrism. This is a script I've thrown together for kicks and I highly suggest you don't use it as it messes directly with the application's database.

Use the tagmap file (see `config.ini`)  to label media from a certain author with a predefined set of labels:
```yaml
nasahqphoto:
  - photo
  - topic-space
PBFcomics:
  - comic
```
If the tagmap file doesn't exist, an empty one will be created by the script.

The media files will be labeled when the script is run with `--tag` and PhotoPrism will keep them in separate logical folders. The `--update-recent` will update an album called "Recent" with the latest downloaded media.

Tested with [PhotoPrism Build 221105-7a295cab4](https://docs.photoprism.app/release-notes/#november-5-2022).
