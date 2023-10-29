"""Calls other modules from the command line."""


import typer
from dotenv import load_dotenv

from rss_to_webhook import check_feeds_and_update

load_dotenv()

app = typer.Typer()
app.command("post-updates")(check_feeds_and_update.main)


@app.callback()
def main() -> None:
    # TODO: Add better help
    """Do various things."""


if __name__ == "__main__":  # pragma: no cover
    app()
