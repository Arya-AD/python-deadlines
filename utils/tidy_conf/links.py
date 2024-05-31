from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from tqdm import tqdm


def check_link_availability(url, start):
    """Checks if a URL is available.

    If not, tries to retrieve an archived version from the Wayback Machine.
    Can't use caching because we have different years for the same url.

    Automatically redirects to the final URL if it was redirected within the same domain.

    Automatically caches old (5+ years) URLs.

    TODO: Some URLs are not available, and not archived. We should add a way to handle this.
    """
    # If it's archived already, return the URL
    if url.startswith(("https://web.archive.org", "http://web.archive.org")):
        return url

    # Check if the URL is cached
    cache_file = Path("utils", "tidy_conf", "data", ".tmp", "no_archive.txt")
    cache_file_archived = Path("utils", "tidy_conf", "data", ".tmp", "archived_links.txt")

    # Create the cache file if it doesn't exist
    cache_file.touch()
    cache_file_archived.touch()

    # Read the cache file
    with cache_file.open(encoding="utf-8") as f:
        cache = f.read().split("\n")[:-1]
    with cache_file_archived.open(encoding="utf-8") as f:
        cache_archived = f.read().split("\n")[:-1]

    # Check if the URL is in the cache
    if url in cache and url not in cache_archived:
        tqdm.write(f"URL {url} is cached as not found. Returning original URL.")
        return url

    # If the URL is younger than 5 years, check if it's available
    if start > datetime.now(tz=timezone.utc).date() - timedelta(days=5 * 365):
        try:
            response = requests.get(url, allow_redirects=True, timeout=10)
            final_url = response.url
            # Check if the final URL is within the same domain as the original URL
            if urlparse(url).netloc == urlparse(final_url).netloc and final_url != url:
                # Don't cache the redirect if it suddenly has a query string
                tqdm.write(f"URL {url} was redirected within the same domain to: {final_url}")
                if "?" in final_url and "?" not in url:
                    tqdm.write("Warning: The final URL contains a query string, but the original URL does not.")
                else:
                    return final_url  # Use the final URL for the rest of the process
            elif response.status_code != 200:
                tqdm.write(
                    (
                        f"Link {url} is not available (status code: {response.status_code})."
                        "Trying to find an archived version..."
                    ),
                )
            else:
                if start > datetime.now(tz=timezone.utc).date():
                    attempt_archive_url(url, cache_file_archived)
                return url
        except requests.RequestException as e:
            tqdm.write(f"An error occurred: {e}. Trying to find an archived version...")

    # Try to get an archived version from the Wayback Machine or return original URL
    archive_url = f"https://archive.org/wayback/available?url={url}&timestamp={start.strftime('%Y%m%d%H%M%S')}"
    try:
        archive_response = requests.get(archive_url, timeout=10)
        # Make sure the status code is valid (200)
        if archive_response.status_code == 200:
            data = archive_response.json()
            # Get the "closest available" snapshot URL to a date
            if (
                data["archived_snapshots"]
                and data["archived_snapshots"]["closest"]
                and data["archived_snapshots"]["closest"]["available"]
            ):
                archived_url = data["archived_snapshots"]["closest"]["url"].replace(":80/", "/")
                if archived_url[4] == ":":
                    archived_url = archived_url[:4] + "s" + archived_url[4:]
                tqdm.write(f"Found archived version: {archived_url}")
                return archived_url
            tqdm.write("No archived version found.")
            attempt_archive_url(url, cache_file_archived)
            with cache_file.open("a") as f:
                f.write(url + "\n")
            return url

        tqdm.write("Failed to retrieve archived version.")
        return url
    except requests.RequestException as e:
        tqdm.write(f"An error occurred while retrieving the archived version: {e}")
        return url


def attempt_archive_url(url, cache_file):
    """Attempts to archive a URL using the Wayback Machine."""
    # Read the cache file
    cache_file = Path(cache_file)

    with cache_file.open(encoding="utf-8") as f:
        cache = f.read().split("\n")[:-1]

    # Check if the URL is in the cache
    if url in cache:
        tqdm.write(f"URL {url} was already archived.")
        return
    with cache_file.open("a") as f:
        f.write(url + "\n")

    try:
        tqdm.write(f"Attempting archive of {url}.")
        archive_response = requests.get("https://web.archive.org/save/" + url, timeout=7)
        if archive_response.status_code == 200:
            tqdm.write(f"Successfully archived {url}.")
    except requests.RequestException as e:
        tqdm.write(f"An error occurred while attempting to archive: {e}")
