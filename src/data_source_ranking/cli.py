from __future__ import annotations

import typer

app = typer.Typer(help="Evidence-quality ranking prototype CLI.")


@app.callback()
def main() -> None:
    """Commands will be added as the ranking core is implemented."""


if __name__ == "__main__":
    app()

