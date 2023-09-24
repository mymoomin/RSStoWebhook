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

- Let people add comics easily, and let people other than me approve them.
- (tentative) Let people add roles through a website that is automatically synced with the available comics.
- Check RSS feeds for new items by recency and not by order.
- Detect broken RSS feeds.

### Architectural

- Add automated tests
- Possibly refactor to personal taste
- Link the comics collections/databases in some way
- Add better logging, whether through tracing or just refactoring
- Think about transactions and state and when to recover from errors
- Check the current rate-limiting rules
