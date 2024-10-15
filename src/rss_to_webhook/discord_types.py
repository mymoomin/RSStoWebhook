"""TypedDicts for working with the Discord API."""

from typing import Required, TypedDict


class Embed(TypedDict):
    """A Discord embed object.

    Documentation can be found [here](https://discord.com/developers/docs/resources/channel#embed-object)
    """

    color: int  # valid hexcode
    title: str
    url: str  # Valid url
    description: str


class Message(TypedDict, total=False):
    """A Discord message.

    This is actually a representation of the JSON params to Discord's
    [Execute Webhook](https://discord.com/developers/docs/resources/webhook#execute-webhook)
    endpoint, as documented [here](https://discord.com/developers/docs/resources/webhook#execute-webhook-jsonform-params),
    rather than a Discord message object.

    `embeds` isn't required by Discord, but it would be a bug in this
    application if it were ever `None`, so it's marked as `Required` here.
    """

    content: str
    username: str
    avatar_url: str  # Valid url
    embeds: Required[list[Embed]]


class Extras(TypedDict, total=False):
    """Extra headers for `Message`s.

    These are the optional keys on `Message` as a separate dictionary. We do
    this because it means we can pass them around as a separate object and
    merge them with the list of embeds later.
    """

    content: str
    color: int
    username: str | None
    avatar_url: str | None
