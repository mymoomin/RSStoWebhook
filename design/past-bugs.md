# Past Bugs

This is a list of bugs that have happened in the past and are now fixed, but would ideally have regression tests. In the future this will hopefully just link to github issues. Once bugs have a regression test, they will be removed from the list.

- [ ] [99880a0](https://github.com/mymoomin/RSStoWebhook/commit/99880a040f5a3f365951836298555c06ea65a034) Incorrectly guessing rate limits
- [ ] [01fd62b](https://github.com/mymoomin/RSStoWebhook/commit/01fd62be50918775b68bedbb71c1f4b5ec148acf) Hidden rate limits
- [x] [0249766](https://github.com/mymoomin/RSStoWebhook/commit/0249766c715879891e3d21bb61bc537839020f5b) Missing title on embed when update has no `<title>`
- [ ] [4ca9b14](https://github.com/mymoomin/RSStoWebhook/commit/4ca9b140de34290797844104c93952bcf481fc5c) Undetected broken RSS feed
- [x] [#1](https://github.com/mymoomin/RSStoWebhook/issues/1) An update being posted, removed, then posted again creates multiple notifications
- [x] [#2](https://github.com/mymoomin/RSStoWebhook/issues/2) Updates posted in the wrong order
- [ ] [#3](https://github.com/mymoomin/RSStoWebhook/issues/3) Not all updates posted when the last-seen update is no longer in the feed
- [ ] [e33e902](https://github.com/mymoomin/RSStoWebhook/commit/e33e902cbf8d7a1ce4e5bb096386ca6e70469921) Updates missed when too many new updates are posted at once
- [ ] [f661a90](https://github.com/mymoomin/RSStoWebhook/commit/f661a902a2ce2be570a9b039e0dde596f52ea624) Spurious errors for failed SSL checks
- [ ] [b0939df](https://github.com/mymoomin/RSStoWebhook/commit/b0939df99bd28ed17d69e814cf51bb725fc97883) Crash when expected response headers are missing
- [x] [13a7171](https://github.com/mymoomin/RSStoWebhook/commit/13a7171be8f19164902a36e1f5abd587f852a303) Crash on bad URL scheme
- [ ] [192de2b](https://github.com/mymoomin/RSStoWebhook/commit/192de2b456810174aa09b6feac6a7b05f695a001) Blocked by Tumblr because of user agent presumably marked as malicious
- [ ] [c45d8b7](https://github.com/mymoomin/RSStoWebhook/commit/c45d8b7a8cdb3507f0a407f2e453e1ebde284e14) Blocked by other sites because of missing user agent
- [ ] [d2e8203](https://github.com/mymoomin/RSStoWebhook/commit/d2e82035639559aa25ec4ccfb79e8bf551e0d5d2) Spurious notifications when a feed's URL structure changes in a semantically-equivalent way
- [ ] [e22f170](https://github.com/mymoomin/RSStoWebhook/commit/e22f17071a57331d26e5b62ea7e5a3f1949660a9) Updates missed by overly-aggressively fuzzy-matching URLs
- [ ] [No Commit] When new pages for a comic couldn't be posted due to a webhook error, their caching headers would still be updated, so after the error was fixed the script thought that the feed was already up-to-date based on the caching headers, and no updates were posted.
