#!/usr/bin/env python3

import sys
import gnupg

from pprint import pp
from gitbolt import get_git


def main_cli(args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]
    print(args)
    gpg = gnupg.GPG()
    pp(gpg.list_keys())
    git = get_git()
    print(git.version)


if __name__ == "__main__":
    main_cli()
