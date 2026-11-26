"""The program's own state, kept between runs in bridge/cache/ (vs. results in outputs/).

    data = read_json("topics.json", default={})
    write_json("topics.json", data)

A cache can always be rebuilt, so a missing or unreadable file reads as
`default` instead of failing. Writes are atomic: a crash or two processes
writing at once never leave a half-written file.
"""

import json
import os
import tempfile

from h2_bridge.constants import CACHE_DIR


def cache_path(name):
    """Path of cache file `name` (e.g. "topics.json"), creating bridge/cache/ if needed."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / name


def read_json(name, default):
    """The cache file's data, or `default` if it's missing or unreadable."""
    try:
        with open(cache_path(name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(name, data):
    """Replace the cache file with `data`, atomically (temp file in the same folder, then rename)."""
    path = cache_path(name)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
