# Design

## Overview

RSStoWebhook is a service that pings people on discord when a webcomic updates.
It currently posts to its own server, either as soon as an update is seen or once a day, and to threads in the Sleepless Domain server for certain comics.
People subscribe to comics by using 42 or roleypoly to add a role, and are notified by getting pinged.
The message that pings them contains a link to the comic and the title of the page, and its avatar is a character from the comic.
People can add a comic by asking me to do so.

## Issues

### Functional

- Adding comics is a manual process that annoys me so I'm often slow to do it.
- If I stop paying attention to the service then new comics can't be added.
- People need to use 42 to add roles, and look up roles in a 118-line alphabetical list.
- The Property of Hate can't be checked due to weird RSS feed layout (not reverse chronological).
- Not following Discord's API rules will break the service, but not all API rules are documented so I don't know what they are, and things will just crash at random.
- When an RSS feed breaks, I often don't notice for a long time.

### Architectural

- The service has no tests other than me checking.
- The design of the code frustrates me slightly, but this is possibly unimportant
- The instant, daily, and SD threads comics posting are unrelated, using 3 separate MongoDB collections. This occasionally causes weird issues, but not that often.
- The logging is hard to follow. Loading the feeds, checking for updates, and posting new comics are separate steps, and I do a given step for every comic before moving onto the next. However, bugs are usually only visible over multiple steps, so they're hard to find in log messages. Also, I don't get notified on bugs.
- Errors in certain steps can introduce inconsistent database steps
- The rate limiting is manual because automatic limiting didn't work. But limiting has changed in the meantime so my manual system might be wrong.

## Goals

### Functional

- [ ] Let people add comics easily, and let people other than me approve them.
- [ ] (tentative) Let people add roles through a website that is automatically synced with the available comics.
- [x] Check RSS feeds for new items at any position in the feed.
- [ ] Detect broken RSS feeds.

### Architectural

- [x] Add automated tests
- [x] Possibly refactor to personal taste
- [x] Link the comics collections/databases in some way
- [ ] Add better logging, whether through tracing or just refactoring
- [ ] Think about transactions and state and when to recover from errors
- [x] Check the current rate-limiting rules

## Progress

### Functional

- Decided that the goal is to let people add comics through a discord bot, since that'll be easier to implement and also less of a context-shift for users
- Wrote a bot that would let people add roles with a slash command, but haven't yet deployed it anywhere (possibly AWS Lambda?)
- Changed how RSS feeds are checked to work with comics that add entries in different places, and also that give every entry the same link
- Added tracking in the database for connection errors, but haven't yet added automatic reporting when errors reach a certain limit

### Architectural

- Added a lot of automated tests, with 100% branch coverage, and regression tests for almost all of of the old bugs
- Fully reworked checking for new updates, and tracking updates to post to the daily webhook
- Checked the rate-limiting rules, might rework how the script rate limits to better conform to them but at the moment it looks like it just about does already
- There is now one combined collection for regular, thread, and daily comic tracking
- The DB is now only updated if all new entries for a comic are successfully posted. I should think about if I want to handle that differently though - perhaps mark entries that fail in case I need to handle them somehow?
- Updated code to use the correct rate-limiting rules, and also combined all new entries for each comic into one longer message, which means that I never hit the 30 messages/minute rate-limit in practice

## Future work (next sprint/branch)

Writen on 2023-10-13

I would consider this successful if any one of these proposed features were successfully implemented, and that would probably be a good point at which to merge from `dev` to `main`, if the feature is implemented atomically. Ideally 100% test coverage would be maintained the whole way.

- Implement actual logging,
  - Use either the `logging` module or some kind of tracing solution (OpenTelemetry and Sentry both seem cool)
  - Use one of the several logging handlers that post to Discord. This is necessary to enable mods on the RSS server to see critical events.
  - Possibly use `ContextVar`s to track which comic is being checked at any point? This might require re-architecturing to put checking each comic in one async task
  - Possibly start adding JSON metadata to log messages to help Logtail understand things better, maybe even enabling a dashboard with alerts for certain events (questionable)
- Actually work on integrating things into Discord.
  - Users should be able to:
    - Propose new comics
    - Subscribe and unsubscribe from comics
    - Switch to daily/possibly other modes
  - Server mods should be able to:
    - Add new comics
    - Update or remove existing comics
    - See important failures (broken RSS feeds, broken RSS entries, rate-limiting issues)
    - Reset the error count/list of errors, if I keep using that approach
  - The bot should automatically
    - Put all comics we track in an alphabetised list, possibly with markdown links to each comic's site
    - Keep the list and the options in the subscribe/unsubscibe command in sync with the database
- Consider using the RSS feeds to update information about them. Each RSS feed almost always (with the main exception of Awful Hospital) has an up-to-date record of:
  - The comic's homepage URL
  - The name of the comic (sometimes inaccurate because it's "[Name of Comic] Updates")
  - The RSS feed's own URL (this one is less common)
  - Often a favicon or other picture that is a logo for the comic (less common)
- Work out what architecture to use for the bot, and how to integrate it into the rest of the code
  - Should it be in the same codebase?
  - If so, should it be in the same package or just the same repository?
  - Should it be a long-running process or a lambda?
  - Should it depend on Discord.py?
  - Should it depend on any web framework at all?
- Possibly add better documentation
  - At minimum, everything relevant from the `/scripts` directory of the original implementation should be here
  - Probably the archive of 700 RSS feeds from 100 comics should not be on GitHub
  - It probably isn't a goal for any randomer to be able to read the docs and set up their own working version of this service, but it might be neat?
  - Even without that, it might be good to be able to publish this on PyPI, possibly so that a Discord bot could use the important parts as a library
- Possibly libarify the code
  - Things like the rate limiter or some of the various database-poking tools might be usable in other contexts
  - It's weird that the logic for [adding new comics to the database](/src/rss_to_webhook/db_operations.py) doesn't reuse anything I've already written
- Move everything in the current `/src/rss_to_webhook/scripts` folder to somewhere public and testable (possibly [`/src/rss_to_webhook/db_operations.py`](/src/rss_to_webhook/db_operations.py))
- Think about adding a `__main__.py` at the package route, and possibly adding [entry points](https://packaging.python.org/en/latest/specifications/entry-points/). This should help with logging and also making the code cleaner and easier to use.
- Think about performance, but not too hard. This is fun and easy to make progress/get stuck on, but for now the scripts are high-performance enough that the server is entirely free to run even on Heroku's paid tier, and the tests take 1.62 seconds to run.
  - Request only a subset of properties from MongoDB. For regular checks, we don't need to actually see the values of `dailies`, `error_count`, or `errors`, and for daily checks we don't need to see `thread_id`, `last_entries`, `feed_hash`, `etag`, `last_modified`, `error_count`, or `errors`.
  - Speed up the tests and remove low-value ones. This is very possible and easy, even while maintaining 100% code coverage, but for now it is also unnecessary.
