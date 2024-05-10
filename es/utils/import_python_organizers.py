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
from tidy_conf.utils import fill_missing_required
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
    # Load current conferences
    target_file = Path(base, "_data", "conferences.yml")
    csv_location = Path(base, "utils", "conferences")

    # If no year is provided, use the current year
    if year is None:
        year = datetime.now(tz=timezone.utc).year

    # Load the existing conference data
    df_yml = load_conferences()
    df_new = pd.DataFrame(columns=df_yml.columns)
    df_csv = pd.DataFrame(columns=df_yml.columns)

    # Parse your csv file and iterate through year by year
    for y in range(year, datetime.now(tz=timezone.utc).year + 10):
        try:
            df = load_remote(year=y)
        except urllib.error.HTTPError:
            break

        if df_yml[df_yml["year"] == y].empty:
            df_csv = pd.concat([df_new, df], ignore_index=True)
        else:
            df_merged, df_remote = fuzzy_match(df_yml[df_yml["year"] == y], df)
            df_merged["year"] = y
            df_merged = df_merged.drop(["conference"], axis=1)
            df_merged = merge_conferences(df_merged, df_remote)

            df_new = pd.concat([df_new, df_merged], ignore_index=True)

            merged, _ = fuzzy_match(df, df_yml[df_yml["year"] == y])
            df_csv = pd.concat([df_csv, merged], ignore_index=True)

    # Write the new data to the YAML file
    df_new = fill_missing_required(df_new)
    write_df_yaml(df_new, target_file)

    # Write the new data to the CSV file
    df_csv.loc[:, "Location"] = df_csv.place
    df_csv.loc[:, "Country"] = (
        df_csv.place.str.split(",")
        .str[-1]
        .str.strip()
        .apply(lambda x: iso3166.countries_by_name.get(x.upper(), iso3166.Country("", "", "", "", "")).alpha3)
    )
    write_csv(df_csv, year, csv_location)


if __name__ == "__main__":
    # Make argparse to get year and base

    import argparse

    parser = argparse.ArgumentParser(description="Import Python Organizers")
    parser.add_argument("--year", type=int, help="Year to import")

    main(year=parser.parse_args().year)
