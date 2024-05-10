import sys

import yaml

sys.path.append(".")
import contextlib
from pathlib import Path

import pandas as pd
from tidy_conf.utils import get_schema

from .utils import ordered_dump


def write_conference_yaml(data: list[dict] | pd.DataFrame, url: str) -> None:
    """Write a list of dictionaries to a YAML file.

    Parameters
    ----------
    data : Union[List[Dict], pd.DataFrame]
        Data with conferences for YAML file.
    url : str
        Location of the YAML file.
    """
    if isinstance(data, pd.DataFrame):
        data = [{k: v for k, v in record.items() if pd.notnull(v)} for record in data.to_dict(orient="records")]
    with Path(url).open(
        "w",
    ) as outfile:
        for line in ordered_dump(
            data,
            dumper=yaml.SafeDumper,
            default_flow_style=False,
            explicit_start=True,
            allow_unicode=True,
        ).splitlines():
            outfile.write(line.replace("- conference:", "\n- conference:"))
            outfile.write("\n")


def load_conferences() -> pd.DataFrame:
    """Load the conferences from the YAML files.

    Returns
    -------
    pd.DataFrame
        DataFrame conforming with schema.yaml from conferences in _data.
    """
    schema = get_schema()

    data = Path("_data")

    # Load the YAML file
    with Path(data, "conferences.yml").open() as file:
        data = yaml.safe_load(file)
    with Path(data, "archive.yml").open() as file:
        archive = yaml.safe_load(file)
    with Path(data, "legacy.yml").open() as file:
        legacy = yaml.safe_load(file)

    # Convert the YAML data to a Pandas DataFrame
    return pd.concat(
        [schema, pd.DataFrame.from_dict(data), pd.DataFrame.from_dict(archive), pd.DataFrame.from_dict(legacy)],
        ignore_index=True,
    ).set_index("conference", drop=False)


def load_title_mappings(reverse=False, path="utils/tidy_conf/data/titles.yml"):
    """Load the title mappings from the YAML file."""
    path = Path(path)
    if not path.exists():
        # Check if the directory exists, and create it if it doesn't
        path.parent.mkdir(parents=True, exist_ok=True)

        # Check if the file exists, and create it if it doesn't
        if not path.is_file():
            with path.open("w") as file:
                yaml.dump({"spelling": [], "alt_name": {}}, file, default_flow_style=False, allow_unicode=True)
        return [], {}

    with path.open() as file:
        data = yaml.safe_load(file)
    spellings = data["spelling"]

    alt_names = data["alt_name"]
    if reverse:
        alt_names = {}
        for key, values in data["alt_name"].items():
            for value in values:
                alt_names[value] = key
    return spellings, alt_names


def update_title_mappings(data, path="utils/tidy_conf/data/titles.yml"):
    """Update the title mappings in the YAML file."""
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open(
            "w",
        ) as file:
            yaml.dump({"spelling": [], "alt_name": data}, file, default_flow_style=False, allow_unicode=True)
    else:
        with path.open() as file:
            title_data = yaml.safe_load(file)
        title_data["alt_name"].update(data)
        with path.open(
            "w",
        ) as file:
            yaml.dump(title_data, file, default_flow_style=False, allow_unicode=True)


def write_df_yaml(df, out_url):
    """Write a conference DataFrame to a YAML file with the right types."""
    with contextlib.suppress(KeyError):
        df = df.drop(["Country", "Venue"], axis=1)
    df["end"] = pd.to_datetime(df["end"]).dt.date
    df["start"] = pd.to_datetime(df["start"]).dt.date
    df["year"] = df["year"].astype(int)
    df["cfp"] = df["cfp"].astype(str)
    write_conference_yaml(df, out_url)
