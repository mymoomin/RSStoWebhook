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
