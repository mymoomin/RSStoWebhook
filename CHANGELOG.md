# Changelog

All notable changes to the extension will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Package now executeable as a script. Try `rss-to-webhook --help` or `py -m rss_to_webhook --help`
  
### Fixed

- When an update for a comic is split across multiple messages, only the first message will ping the update role

## [0.0.3] - 2023-10-29

### Added

- Added tests against the real Discord API
- Added tests for [`check_feeds_and_update.py`](src/rss_to_webhook/check_feeds_and_update.py)'s option parsing

### Changed

- Upgraded urllib3 to 2.0.7
- Moved all example webhook URLs to use Discord API version 10
- Moved `HASH_SEED` from an environment variable to a constant
- Moved [`check_feeds_and_update.py`](src/rss_to_webhook/check_feeds_and_update.py)'s `if __name__ == "__main__"` block into its own function
