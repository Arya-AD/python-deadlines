import re
import sys
import urllib
from datetime import datetime
from datetime import timezone
from pathlib import Path

import iso3166
import pandas as pd

sys.path.append(".")
from tidy_conf import fuzzy_match
from tidy_conf import load_conferences
from tidy_conf import merge_conferences
from tidy_conf.deduplicate import deduplicate
from tidy_conf.schema import get_schema
from tidy_conf.utils import fill_missing_required
from tidy_conf.yaml import load_title_mappings
from tidy_conf.yaml import write_df_yaml


def load_remote(year):
    url = f"https://raw.githubusercontent.com/python-organizers/conferences/main/{year}.csv"

    # Read data and rename columns
    df = pd.read_csv(url)
    df = map_columns(df)

    # Only return valid cfps
    # return df.dropna(subset=['cfp'])
    return df


def map_columns(df, reverse=False):
    """Map columns to the schema."""
    cols = {
        "Subject": "conference",
        "Start Date": "start",
        "End Date": "end",
        "Tutorial Deadline": "tutorial_deadline",
        "Talk Deadline": "cfp",
        "Website URL": "link",
        "Proposal URL": "cfp_link",
        "Sponsorship URL": "sponsor",
    }

    df["place"] = df["Location"]

    if reverse:
        cols = {v: k for k, v in cols.items()}

    return df.rename(columns=cols)


def write_csv(df, year, csv_location):
    """Write the CSV files for the conferences."""
    df["cfp"] = df["cfp"].str.slice(stop=10).str.replace("TBA", "")
    df["tutorial_deadline"] = df["tutorial_deadline"].str.slice(stop=10).str.replace("TBA", "")
    df = map_columns(df, reverse=True)
    for y in range(year, datetime.now(tz=timezone.utc).year + 10):
        if y in df["year"].unique():
            df.loc[
                df["year"] == y,
                [
                    "Subject",
                    "Start Date",
                    "End Date",
                    "Location",
                    "Country",
                    "Venue",
                    "Tutorial Deadline",
                    "Talk Deadline",
                    "Website URL",
                    "Proposal URL",
                    "Sponsorship URL",
                ],
            ].fillna("").astype(str).sort_values(by="Start Date").to_csv(Path(csv_location, f"{y}.csv"), index=False)


def main(year=None, base=""):
    """Import Python conferences from a csv file Github."""
    # If no year is provided, use the current year
    if year is None:
        year = datetime.now(tz=timezone.utc).year

    # Load current conferences
    _data_path = Path(base, "_data")
    _utils_path = Path(base, "utils")
    _tmp_path = Path(base, ".tmp")
    _tmp_path.mkdir(exist_ok=True, parents=True)
    _data_path.mkdir(exist_ok=True, parents=True)
    target_file = Path(_data_path, "conferences.yml")
    csv_location = Path(_utils_path, "conferences")
    cache_file = Path(_tmp_path, ".conferences_py_orgs.csv")

    # Load the existing conference data
    df_yml = load_conferences()
    df_schema = get_schema()
    df_new = pd.DataFrame(columns=df_schema.columns)
    df_csv = pd.DataFrame(columns=df_schema.columns)

    # Parse your csv file and iterate through year by year
    for y in range(year, datetime.now(tz=timezone.utc).year + 10):
        try:
            df = deduplicate(load_remote(year=y), "conference")
            df["year"] = y
        except urllib.error.HTTPError:
            break
        df_csv = pd.concat([df_csv, df], ignore_index=True)

    # Load old ics dataframe from cached data
    try:
        # Load the old ics dataframe from cache
        df_csv_old = pd.read_csv(cache_file)
    except FileNotFoundError:
        df_csv_old = pd.DataFrame(columns=df_csv.columns)

    # Load and apply the title mappings, remove years from conference names
    _, known_mappings = load_title_mappings(reverse=True)
    df_csv = df_csv.replace(re.compile(r"\b\s+(19|20)\d{2}\s*\b"), "", regex=True).replace(known_mappings)

    # Store the new ics dataframe to cache
    df_cache = df_csv.copy()

    # Get the difference between the old and new dataframes
    df_diff = pd.concat([df_csv_old, df_csv]).drop_duplicates(keep=False)

    # Deduplicate the new dataframe
    df_csv = deduplicate(df_diff, "conference")

    if df_csv.empty:
        print("No new conferences found in Python organiser source.")
        return

    for y in range(year, datetime.now(tz=timezone.utc).year + 10):
        if df_csv.loc[df_csv["year"] == y].empty or df_yml[df_yml["year"] == y].empty:
            # Concatenate the new data with the existing data
            df_new = pd.concat(
                [df_new, df_yml[df_yml["year"] == y], df_csv.loc[df_csv["year"] == y]],
                ignore_index=True,
            )
            continue

        df_merged, df_remote = fuzzy_match(df_yml[df_yml["year"] == y], df_csv.loc[df_csv["year"] == y])
        df_merged["year"] = y
        df_merged = df_merged.drop(["conference"], axis=1)
        df_merged = deduplicate(df_merged)
        df_remote = deduplicate(df_remote)
        df_merged = merge_conferences(df_merged, df_remote)

        df_new = pd.concat([df_new, df_merged], ignore_index=True)

    # Write the new data to the YAML file
    df_new = fill_missing_required(df_new)
    write_df_yaml(df_new, target_file)

    # Write the new data to the CSV file
    df_csv.loc[:, "Location"] = df_csv.place
    try:
        df_csv.loc[:, "Country"] = (
            df_csv.place.str.split(",")
            .str[-1]
            .str.strip()
            .apply(lambda x: iso3166.countries_by_name.get(x.upper(), iso3166.Country("", "", "", "", "")).alpha3)
        )
    except AttributeError as e:
        df_csv.loc[:, "Country"] = ""
        print(f"Error: Country iso3 not found for {df_csv.place} - {e}")
    write_csv(df_csv, year, csv_location)

    # Save the new ics dataframe to cache
    df_cache.to_csv(cache_file, index=False)


if __name__ == "__main__":
    # Make argparse to get year and base

    import argparse

    parser = argparse.ArgumentParser(description="Import Python Organizers")
    parser.add_argument("--year", type=int, help="Year to import")

    main(year=parser.parse_args().year)
