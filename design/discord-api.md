# Discord API

This is a summary of all features of the Discord API that are relevant for this program.

## Webhooks

Webhooks are identified by their URL, which is in the form `https://discord.com/api/webhooks/{webhook.id}/{webhook.token}`.
Calls to a webhook don't need authentication, because the webhook's token is part of the URL.
Webhooks come in three types, but we only need to care about "incoming" webhooks, and will ignore the other two.
They can only post in one channel, which can changed with an API call but we treat as static, but they can post in any thread within that channel.
A webhook has an avatar and a name, but these can both be overridden on a per-message basis.
We only use the [Execute Webhook](https://discord.com/developers/docs/resources/webhook#execute-webhook) API endpoint.

### Execute Webhook

This posts a message from the given webhook, and so is a `POST` request to the webhook's URL.
Actual docs are [here](https://discord.com/developers/docs/resources/webhook#execute-webhook).

#### Query params

- `wait`: Should the request should wait for server confirmation of the message being sent before returning.
  - Always set to `true` here
  - When true, the success response is a 200 and returns the body of the new message
- `thread_id`: Which thread to post in. If not present, posts in the channel. Must be a real thread.

#### Body params (JSON)

All of these are theoretically optional, but `embeds` is always required in this program.
The others (other than `content`) are completely optional but no-one's actually made use of the optionality, so they are in practice always present.
A parameter being `None` is always the same as it not being present.
These parameters are encapsulated in the [`Message`](/src/rss_to_webhook/discord_types.py) `TypedDict`.

- `username`: The username the webhook will appear to have, overriding the default one.
- `avatar_url`: Same but for the avatar. Must be a valid URL
- `allowed_mentions`: Filters which roles and people can be mentioned. We don't need this because the only dynamic content that isn't meant to ping people is inside the embed, and mentions there don't actually ping.
- `content`: The content of the message. Here, it's the role to ping for comic updates, and is `None` only when posting to a thread on the main server
- `embeds`: A list of up to 10 Embed JSON objects/Python dictionaries.

#### The `Embed` Object

An [`Embed`](/src/rss_to_webhook/discord_types.py) `TypedDict`/JSON object represents a Discord embed, which you might recognise as the cards with info and possibly a coloured line down the left-hand side that you see when you post certain links.
Every property is optional, but for the purposes of this program, every property that we use is always required.
In this program, an embed represents a new page of a webcomic.
Actual docs are [here](https://discord.com/developers/docs/resources/channel#embed-object)

- `color`: The colour of the the strip on the left of the embed. An integer representation of a hexcode. Must be between `0` and `0xFFFFFF`. If it is a float, it is rounded to an integer.
- `title`: The clickable text. The page's title if present, and the name of the comic otherwise.
- `link`: The URL of the page. Makes the title of the embed a hyperlink when present. If the page doesn't have a `<link>`, this is a serious issue that will currently break the bot when it tries to post the update. Minor issues like an incorrect URL scheme will be fixed before they reach this point though. This is the only issue that is currently auto-fixed, which is entirely due to Jeph Jacques being bad at RSS (see [13a7171](https://github.com/mymoomin/RSStoWebhook/commit/13a7171be8f19164902a36e1f5abd587f852a303))
- `description`: Non-clickable text that appears below the title. This is both useless functionally and redundant information, but I think it looks nice. Might remove it in the future

#### Rate Limits

Theoretically, Discord shows you rate limits in the HTTP response whenever you call an API endpoint, using the semi-standard `X-RateLimit-*` headers.
For webhooks, this appears to suggest a limit of 5 posts every 2.0 or so seconds.
This is automatically managed based on the headers, which is best practice, because this rate limit can change.
This rate limit is scoped per webhook.

However, there is also a secret rate limit that's documented only in [this tweet](https://twitter.com/lolpython/status/967621046277820416) and some scattered StackOverflow answers.
This hidden rate limit is 30 messages each minute, scoped per channel.
When this rate limit is hit, Discord sends the normal "The resource is being rate limited." JSON error message, but the "retry_after" is fake, and sleeping that long will just get the webhook immediately rate-limited again.
Given that it can't be recovered from, if this is encountered the program will immediately abort.

This rate limit is also managed automatically based on a per-webhook counter implemented to follow the limits as-documented in the tweet, under the assumption that only one webhook will post to each channel.
In practice, it only seems to kick in after the 32nd message, but keeping it at 30 seems like the safest option.
This program also adds a fuzz factor, an additional 1-second delay past the 60-second window, because when I tested using exactly 60 seconds, I got a mysterious error after 90 messages that was either rate-limiting related or the wind.
I've never replicated this error, but better safe than sorry.

Both rate limits are handled by the [`RateLimiter`](/src/rss_to_webhook/check_feeds_and_update.py) class, which should probably be either in its own module or in a `discord_utils` module.

#### Errors

- Rate limit exceeded:
  - Status: `429 TOO MANY REQUESTS`
  - Body:

```json
{
  "message": "You are being rate limited.",
  "retry_after": some_float,
  "global": false
}
```

- `webhook.id` doesn't match any known webhook:
  - Status: `404 Not Found`
  - Body: `{'message': 'Unknown Webhook', 'code': 10015}`

- Impossible `webhoook.id`:
  - Status: `400 Bad Request`
  - Body: `{'webhook_id': ['Value "{value}" is not snowflake.']}`

- Missing `webhook.token` without trailing slash:
  - Status: `405 Method Not Allowed`
  - Body: `{'message': '405: Method Not Allowed', 'code': 0}`

- Missing `webhook.token` with trailing slash:
  - Status: `404 Not Found`
  - Body: `{'message': '404: Not Found', 'code': 0}`

- Incorrect `webhook.token`:
  - Status: `401 Unauthorized`
  - Body: `{'message': 'Invalid Webhook Token', 'code': 50027}`

- `thread_id` doesn't match any thread in the webhook's channel:
  - Status: `400 Bad Request`
  - Body `{'message': 'Unknown Channel', 'code': 10003}`
- `content` and `embeds` are both empty:
  - Status: `400 Bad Request`
  - Body: `{'message': 'Cannot send an empty message', 'code': 50006}`

All further errors give the status `400 Bad Request` and have the body `{'message': 'Invalid Form Body', 'code': 50035, 'errors': {dict_of_errors}}`, or `{'message': 'Invalid Form Body', 'code': 50035, 'errors': {'embeds': {'0': {dict_of_errors}}}}` if the value is inside an embed.

- Invalid `?wait=`: `'wait': {'_errors': [{'code': 'BOOLEAN_TYPE_CONVERT', 'message': 'Must be either true or false.'}]}`
- Invalid `?thread_id`: `'thread_id': {'_errors': [{'code': 'NUMBER_TYPE_COERCE', 'message': 'Value "{value}" is not snowflake.'}]}`
- `content` too long: `'content': {'_errors': [{'code': 'BASE_TYPE_MAX_LENGTH', 'message': 'Must be 2000 or fewer in length.'}]}`
- For `embeds`
  - Empty embed: `{'code': 'LIST_ITEM_VALUE_REQUIRED', 'message': 'List item values of ModelType are required'}`
  - Wrong type in embed: `{'code': 'MODEL_TYPE_CONVERT', 'message': 'Expected an object/dictionary.'}`
  - Too many embeds: `{'code': 'BASE_TYPE_MAX_LENGTH', 'message': 'Must be 10 or fewer in length.'}`
  - Embed value is the wrong type: `{'code': '{TYPE}_TYPE_CONVERT', 'message': 'Could not interpret "{value}" as {type}.'}`
- For `color` (body will contain `'color': {'_errors': [{list-of-errors}]`)
  - Value below `0x000000` to `0xFFFFFF`: `{'code': 'NUMBER_TYPE_MIN', 'message': 'int value should be greater than or equal to 0.'}`
  - Value above `0xFFFFFF`: `{'code': 'NUMBER_TYPE_MAX', 'message': 'int value should be less than or equal to 16777215.'}`
  - Value not an int or float: `{'code': 'NUMBER_TYPE_COERCE', 'message': 'Value "{value}" is not int.'}`
- For fields meant to contain a URL (body will contain `'{field_name}': {'_errors': [{list-of-errors}]`)
  - Invalid scheme: `{'code': 'URL_TYPE_INVALID_SCHEME', 'message': 'Scheme "ttps" is not supported. Scheme must be one of (\'http\', \'https\').'}`
  - URL too long: `{'code': 'BASE_TYPE_MAX_LENGTH', 'message': 'Must be 2048 or fewer in length.'}`
  - Otherwise invalid URL: `{'code': 'URL_TYPE_INVALID_URL', 'message': 'Not a well formed URL.'}`
  
    The things that I have worked out aren't allowed are:
    - No dot in netloc
    - Any component of the netloc longer than 63 character
    - 2 consecutive dots in netloc
    - spaces in the URL
    Any futher things that arent' allowed will be added as time passes.
