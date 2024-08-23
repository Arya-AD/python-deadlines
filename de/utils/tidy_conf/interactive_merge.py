import re
import sys
from collections import defaultdict

import pandas as pd
from thefuzz import process

sys.path.append(".")
import contextlib

from tidy_conf.schema import get_schema
from tidy_conf.utils import query_yes_no
from tidy_conf.yaml import load_title_mappings
from tidy_conf.yaml import update_title_mappings


def fuzzy_match(df_yml, df_remote):
    """Fuzzy merge conferences from two pandas dataframes on title.

    Loads known mappings from a YAML file and uses them to harmonise conference titles.
    Updates those when we find a Fuzzy match.

    Keeps temporary track of rejections to avoid asking the same question multiple
    times.
    """
    # Load known title mappings
    _, known_mappings = load_title_mappings(reverse=True)
    _, known_rejections = load_title_mappings(path="utils/tidy_conf/data/.tmp/rejections.yml")
    regex_year = re.compile(r"\b\s+(19|20)\d{2}\s*\b")
    df_remote.loc[:, "conference"] = (
        df_remote.conference.str.replace(regex_year, "", regex=True).str.strip().replace(known_mappings)
    )
    df_yml.loc[:, "conference"] = (
        df_yml.conference.str.replace(regex_year, "", regex=True).str.strip().replace(known_mappings)
    )
    new_mappings = defaultdict(list)
    new_rejections = defaultdict(list)

    # Make Title the index
    df_remote = df_remote.set_index("conference", drop=False)
    df_remote.index.rename("title_match", inplace=True)

    df = df_yml.copy()

    # Get closest match for titles
    df["title_match"] = df["conference"].apply(
        lambda x: process.extract(x, df_remote["conference"], limit=1),
    )

    # Get first match if it's over 90
    for i, row in df.copy().iterrows():
        if isinstance(row["title_match"], str):
            continue
        if len(row["title_match"]) == 0:
            continue
        title, prob, _ = row["title_match"][0]
        if prob == 100:
            title = title
        elif prob >= 70:
            if (title in known_rejections and i in known_rejections[title]) or (
                i in known_rejections and title in known_rejections[i]
            ):
                title = i
            else:
                if not query_yes_no(f"Do '{row['conference']}' and '{title}' match? (y/n): "):
                    # Code for non-matching case
                    new_rejections[title].append(i)
                    new_rejections[i].append(title)
                    title = i
                else:
                    new_mappings[i].append(title)
        else:
            title = i
        df.loc[i, "title_match"] = title

    update_title_mappings(new_mappings)
    update_title_mappings(new_rejections, path="utils/tidy_conf/data/.tmp/rejections.yml")

    df.set_index("title_match", inplace=True)

    # Update missing data in existing records
    df_new = df.combine_first(df_remote)

    df_new.loc[df_new["cfp"].isna(), "cfp"] = "TBA"

    return df_new, df_remote


def merge_conferences(df_yml, df_remote):
    """Merge two dataframes on title and interactively resolve conflicts."""
    df_new = get_schema()
    columns = df_new.columns.tolist()

    with contextlib.suppress(KeyError):
        df_yml = df_yml.drop(["conference"], axis=1)
    with contextlib.suppress(KeyError):
        df_remote = df_remote.drop(["conference"], axis=1)

    replacements = {
        "United States of America": "USA",
        "United Kingdom": "UK",
        "Czech Republic": "Czechia",
    }

    df_merge = pd.merge(left=df_yml, right=df_remote, how="outer", on="title_match", validate="one_to_one")
    for i, row in df_merge.iterrows():
        df_new.loc[i, "conference"] = i
        for column in columns:
            cx, cy = column + "_x", column + "_y"
            # print(i,cx,cy,cx in df_merge.columns and cy in df_merge.columns,column in df_merge.columns,)
            if cx in df_merge.columns and cy in df_merge.columns:
                rx, ry = row[cx], row[cy]
                for orig, replacement in replacements.items():
                    if isinstance(rx, str):
                        rx = rx.replace(orig, replacement)
                    if isinstance(ry, str):
                        ry = ry.replace(orig, replacement)
                # Prefer my sponsor info if exists
                if column == "sponsor" and not pd.isnull(rx):
                    ry = rx
                # Some text processing
                if isinstance(rx, str) and isinstance(ry, str):
                    # Remove whitespaces
                    rx, ry = str.strip(rx), str.strip(ry)
                    # Look at strings with extra information
                    if rx.split(" ")[0] == ry.split(" ")[0] and rx.split(" ")[-1] == ry.split(" ")[-1]:
                        if len(ry) > len(rx):
                            df_new.loc[i, column] = rx
                            ry = rx
                        else:
                            df_new.loc[i, column] = ry
                            rx = ry
                    # Partial strings such as CFP
                    if rx.startswith(ry):
                        ry = rx
                    elif ry.startswith(rx):
                        rx = ry
                    if rx.endswith(ry):
                        rx = ry
                    elif ry.endswith(rx):
                        ry = rx
                if rx == ry:
                    # When both are equal just assign
                    df_new.loc[i, column] = rx
                elif pd.isnull(rx) and ry:
                    # If one is empty use the other
                    df_new.loc[i, column] = ry
                elif rx and pd.isnull(ry):
                    # If one is empty use the other
                    df_new.loc[i, column] = rx
                elif type(rx) != type(ry):
                    # Use non-string on different types
                    if str(rx).strip() == str(ry).strip():
                        if isinstance(rx, str):
                            df_new.loc[i, column] = ry
                            rx = ry
                        elif isinstance(ry, str):
                            df_new.loc[i, column] = rx
                            ry = rx
                    else:
                        if query_yes_no(f"For {i} in column '{column}' would you prefer '{ry}' or keep '{rx}'?"):
                            df_new.loc[i, column] = ry
                        else:
                            df_new.loc[i, column] = rx
                elif column == "cfp_ext":
                    # Skip cfp_ext
                    continue
                elif column == "cfp" and rx != ry:
                    if "TBA" in rx:
                        df_new.loc[i, column] = ry
                    elif "TBA" in ry:
                        df_new.loc[i, column] = rx
                    else:
                        # Extract a time signature from the cfp
                        cfp_time_x = cfp_time_y = ""
                        if " " in rx and " " not in ry:
                            cfp_time_y = " " + rx.split(" ")[1]
                        elif " " not in rx and " " in ry:
                            cfp_time_x = " " + ry.split(" ")[1]

                        # Check if the cfp_ext is the same and if so update the cfp
                        if rx + cfp_time_x == row["cfp_ext_x"]:
                            df_new.loc[i, "cfp"] = ry + cfp_time_y
                            df_new.loc[i, "cfp_ext"] = rx + cfp_time_x
                            continue
                        if ry + cfp_time_y == row["cfp_ext_y"]:
                            df_new.loc[i, "cfp"] = rx + cfp_time_x
                            df_new.loc[i, "cfp_ext"] = ry + cfp_time_y
                            continue
                        if rx + cfp_time_x == row["cfp_ext_y"]:
                            df_new.loc[i, "cfp"] = ry + cfp_time_y
                            df_new.loc[i, "cfp_ext"] = rx + cfp_time_x
                            continue
                        if ry + cfp_time_y == row["cfp_ext_x"]:
                            df_new.loc[i, "cfp"] = rx + cfp_time_x
                            df_new.loc[i, "cfp_ext"] = ry + cfp_time_y
                            continue
                        # Give a choice
                        if query_yes_no(
                            (
                                f"For {i} in column '{column}' would you prefer "
                                f"'{ry + cfp_time_y}' or keep '{rx + cfp_time_x}'?"
                            ),
                        ):
                            df_new.loc[i, column] = ry + cfp_time_y
                        else:
                            # Check if it's an extension of the deadline and update both
                            if query_yes_no("Is this an extension?"):
                                rrx, rry = int(rx.replace("-", "").split(" ")[0]), int(
                                    ry.replace("-", "").split(" ")[0],
                                )
                                if rrx < rry:
                                    df_new.loc[i, "cfp"] = rx + cfp_time_x
                                    df_new.loc[i, "cfp_ext"] = ry + cfp_time_y
                                else:
                                    df_new.loc[i, "cfp"] = ry + cfp_time_y
                                    df_new.loc[i, "cfp_ext"] = rx + cfp_time_x
                            else:
                                df_new.loc[i, column] = rx + cfp_time_x
                elif column == "place" and rx != ry:
                    # Special Place stuff
                    rxx = ", ".join((rx.split(",")[0].strip(), rx.split(",")[-1].strip())) if "," in rx else rx
                    ryy = ", ".join((ry.split(",")[0].strip(), ry.split(",")[-1].strip())) if "," in ry else ry

                    # Chill on the TBA
                    if rxx == ryy or rxx in ["TBD", "TBA", "None"]:
                        df_new.loc[i, column] = ryy
                    elif ryy in ["TBD", "TBA", "None"]:
                        df_new.loc[i, column] = rxx
                    elif rx in ry:
                        # If one is a substring of the other use the longer one
                        df_new.loc[i, column] = ry
                    elif ry in rx:
                        df_new.loc[i, column] = rx
                    elif rxx in ryy:
                        df_new.loc[i, column] = ryy
                    elif ryy in rxx:
                        df_new.loc[i, column] = rxx
                    else:
                        if query_yes_no(f"For {i} in column '{column}' would you prefer '{ryy}' or keep '{rxx}'?"):
                            df_new.loc[i, column] = ryy
                        else:
                            df_new.loc[i, column] = rxx
                else:
                    # For everything else give a choice
                    if query_yes_no(f"For {i} in column '{column}' would you prefer '{ry}' or keep '{rx}'?"):
                        df_new.loc[i, column] = ry
                    else:
                        df_new.loc[i, column] = rx
            elif column in df_merge.columns:
                # Sorry for this code, it's the new Pandas "non-empty merge" stuff...
                df_new[column] = (
                    df_new[column].copy()
                    if df_merge[column].empty
                    else (
                        df_merge[column].copy()
                        if df_new[column].empty
                        else df_new[column].combine_first(df_merge[column])
                    )
                )

    # Fill in missing CFPs with TBA
    df_new.loc[df_new.cfp.isna(), "cfp"] = "TBA"
    return df_new
