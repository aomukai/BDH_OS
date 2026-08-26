"""Search Unsplash through its official API and retain acquisition provenance.

This command only searches metadata.  A later downloader must call the selected
photo's ``download_location`` before fetching the hotlinked image URL, as required
by the Unsplash API guidelines.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.unsplash.com"


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def search(query: str, *, access_key: str, page: int, per_page: int, orientation: str | None) -> dict:
    parameters = {
        "query": query,
        "page": page,
        "per_page": per_page,
        "content_filter": "high",
    }
    if orientation:
        parameters["orientation"] = orientation
    request = Request(
        f"{API_ROOT}/search/photos?{urlencode(parameters)}",
        headers={
            "Authorization": f"Client-ID {access_key}",
            "Accept-Version": "v1",
            "User-Agent": "Ninereeds-image-registry/1.0",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def normalize(photo: dict, query: str) -> dict:
    user = photo.get("user") or {}
    links = photo.get("links") or {}
    urls = photo.get("urls") or {}
    return {
        "schema_version": "ninereeds_unsplash_search_candidate_v1",
        "query": query,
        "source": "unsplash",
        "source_id": photo["id"],
        "description": photo.get("description") or photo.get("alt_description"),
        "width": photo.get("width"),
        "height": photo.get("height"),
        "author": user.get("name"),
        "author_username": user.get("username"),
        "author_url": (user.get("links") or {}).get("html"),
        "landing_url": links.get("html"),
        "hotlinked_image_urls": {
            key: urls.get(key) for key in ("raw", "full", "regular", "small") if urls.get(key)
        },
        "download_location": links.get("download_location"),
        "license_url": "https://unsplash.com/license",
        "review_status": "unreviewed_metadata_candidate",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--per-page", type=int, default=20)
    parser.add_argument("--orientation", choices=("landscape", "portrait", "squarish"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--access-key-env", default="UNSPLASH_ACCESS_KEY")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    if not 1 <= args.per_page <= 30:
        parser.error("per-page must be between 1 and 30")
    load_env_file(args.env_file)
    access_key = os.environ.get(args.access_key_env, "").strip()
    if not access_key:
        raise SystemExit(
            f"missing {args.access_key_env}; create an Unsplash developer application and export its access key"
        )
    payload = search(
        args.query, access_key=access_key, page=args.page,
        per_page=args.per_page, orientation=args.orientation,
    )
    rows = [normalize(photo, args.query) for photo in payload.get("results", [])]
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
