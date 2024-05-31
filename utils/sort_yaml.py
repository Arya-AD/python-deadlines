#!/usr/bin/env python3

# Sort and Clean conference data.
import contextlib
import datetime
import sys
import time
from datetime import timezone
from pathlib import Path

import pytz
import yaml
from tqdm import tqdm

sys.path.append(".")
import operator

from tidy_conf import auto_add_sub, write_conference_yaml
from tidy_conf.date import clean_dates
from tidy_conf.latlon import add_latlon
from tidy_conf.links import check_link_availability
from tidy_conf.titles import tidy_titles
from tidy_conf.utils import Loader, get_schema, query_yes_no

dateformat = "%Y-%m-%d %H:%M:%S"
tba_words = ["tba", "tbd", "cancelled", "none", "na", "n/a", "nan", "n.a."]


def sort_by_cfp(data):
    """Sort by CFP date."""
    if "cfp" not in data:
        return "TBA"
    if data["cfp"].lower() in tba_words:
        return data["cfp"]
    if " " not in data["cfp"]:
        data["cfp"] += " 23:59:00"
    return pytz.utc.normalize(
        datetime.datetime.strptime(data["cfp"], dateformat).replace(
            tzinfo=pytz.timezone(
                data.get("timezone", "AoE")
                .replace("AoE", "Etc/GMT+12")
                .replace("UTC+", "Etc/GMT-")
                .replace("UTC-", "Etc/GMT+"),
            ),
        ),
    ).strftime(dateformat)


def sort_by_date(data):
    """Sort by starting date."""
    if "start" not in data:
        return "TBA"
    return str(data["start"])


def sort_by_date_passed(data):
    """Sort data by date passed."""
    right_now = datetime.datetime.now(tz=timezone.utc).replace(microsecond=0).strftime(dateformat)
    return sort_by_cfp(data) < right_now


def sort_by_name(data):
    """Sort by name."""
    return f'{data["conference"]} {data["year"]!s}'.lower()


def order_keywords(data):
    """Order the keywords in the data."""
    schema = get_schema().columns.tolist()
    new_dict = {}
    for key in schema:
        if key in data:
            new_dict[key] = data[key]
    return new_dict


def merge_duplicates(data):
    """Merge duplicates in the data."""
    filtered = []
    filtered_reduced = []
    for q in tqdm(data):
        q_reduced = f'{q.get("conference", None)} {q.get("year", None)} {q.get("place", None)}'
        if q_reduced not in filtered_reduced:
            filtered.append(q)
            filtered_reduced.append(q_reduced)
        else:
            index = filtered_reduced.index(q_reduced)
            for key, value in q.items():
                if value and key not in filtered[index]:
                    filtered[index][key] = value
                else:
                    if len(str(value)) > len(str(filtered[index][key])):
                        filtered[index][key] = value
    return filtered


def tidy_dates(data):
    """Clean dates in the data."""
    for i, q in tqdm(enumerate(data.copy()), total=len(data)):
        data[i] = clean_dates(q)
        # data[i] = create_nice_date(q)
    return data


def split_data(data):
    """Split the data into conferences, tba, expired, and legacy.

    The data is split based on the `cfp` field. If the `cfp` field is in the `tba_words` list, it is considered a TBA.
    Legacy is considered anything old with the `cfp` still being TBA.
    """
    conf, tba, expired, legacy = [], [], [], []
    for q in tqdm(data):
        if q["cfp"].lower() not in tba_words and " " not in q["cfp"]:
            q["cfp"] += " 23:59:00"
        if "cfp_ext" in q and " " not in q["cfp_ext"]:
            q["cfp_ext"] += " 23:59:00"
        if q.get("end", datetime.datetime.now(tz=timezone.utc).replace(microsecond=0).date()) < datetime.datetime.now(
            tz=timezone.utc,
        ).replace(microsecond=0).date() - datetime.timedelta(days=37):
            if q["cfp"].lower() == "tba":
                legacy.append(q)
            else:
                expired.append(q)
            continue

        try:
            if q["cfp"].lower() in tba_words:
                tba.append(q)
            else:
                conf.append(q)
        except KeyError:
            pass
    return conf, tba, expired, legacy


def check_links(data):
    """Check the links in the data iteratively."""
    for i, q in tqdm(enumerate(sorted(data, key=operator.itemgetter("year"), reverse=True)), total=len(data)):
        for key in ("link", "cfp_link", "sponsor", "finaid"):
            if key in q:
                new_link = check_link_availability(q[key], q["start"])
                if "https://web.archive.org" not in new_link:
                    time.sleep(0.5)

                q[key] = new_link
                data[i] = q
    return data


# Sort:
def sort_data(base="", prefix="", skip_links=False):
    """Sort and clean the conference data."""
    # Load different data files
    current = Path(base, "_data", "conferences.yml")
    out_current = Path(base, "_data", f"{prefix}conferences.yml")
    archive = Path(base, "_data", "archive.yml")
    out_archive = Path(base, "_data", f"{prefix}archive.yml")
    legacy = Path(base, "_data", "legacy.yml")
    out_legacy = Path(base, "_data", f"{prefix}legacy.yml")

    data = []

    for url in (current, archive, legacy):
        with url.open(encoding="utf-8") as stream, contextlib.suppress(yaml.YAMLError):
            if stream:
                data += yaml.load(stream, Loader=Loader)  # nosec B506 # noqa: S506

    for i, q in enumerate(data.copy()):
        data[i] = order_keywords(q)

    # Clean Dates
    data = tidy_dates(data)

    # Clean Titles
    data = tidy_titles(data)

    # Add Sub
    data = auto_add_sub(data)

    # Geocode Data
    data = add_latlon(data)

    # Merge duplicates
    data = merge_duplicates(data)

    # Check Links
    if not skip_links and query_yes_no("Check Links?"):
        data = check_links(data)

    for i, q in enumerate(data.copy()):
        data[i] = order_keywords(q)

    # Split data by cfp
    conf, tba, expired, legacy = split_data(data)

    # just sort:
    conf.sort(key=sort_by_cfp, reverse=True)
    # pretty_print("Date Sorting:", conf, tba, expired, legacy)
    conf.sort(key=sort_by_date_passed)
    # pretty_print("Date and Passed Deadline Sorting with tba:", conf, tba, expired)
    tba.sort(key=sort_by_date, reverse=True)

    write_conference_yaml(conf + tba, out_current)

    expired.sort(key=sort_by_date, reverse=True)
    expired.sort(key=sort_by_cfp, reverse=True)

    # pretty_print("New archive:", data)
    write_conference_yaml(expired, out_archive)

    legacy.sort(key=sort_by_name, reverse=True)

    # pretty_print("New legacy:", data)
    write_conference_yaml(legacy, out_legacy)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sort and clean conference data.")
    parser.add_argument("--skip_links", action="store_true", help="Skip checking links", default=False)
    args = parser.parse_args()

    sort_data(skip_links=args.skip_links)
