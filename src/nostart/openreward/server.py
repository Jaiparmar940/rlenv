"""ORS server entry point: python -m nostart.openreward.server (port 8080)."""

from __future__ import annotations

from openreward.environments import Server

from nostart.openreward.env import NoStartEnv


def main() -> None:
    Server([NoStartEnv]).run()


if __name__ == "__main__":
    main()
