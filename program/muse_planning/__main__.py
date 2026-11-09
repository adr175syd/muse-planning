"""Allow `python3 -m muse_planning` from the program/ directory."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
