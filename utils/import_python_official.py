import re
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from urllib import request

import pandas as pd
from icalendar import Calendar
from tidy_conf import fuzzy_match
from tidy_conf import load_conferences
from tidy_conf import merge_conferences
from tidy_conf.date import create_nice_date
from tidy_conf.utils import fill_missing_required
from tidy_conf.yaml import load_title_mappings
from tidy_conf.yaml import write_df_yaml


def ics_to_dataframe():
    """Parse an .ics file and return a DataFrame with the event data."""
    # Open the .ics file and parse it into a Calendar object
    with request.urlopen(
        "https://www.google.com/calendar/ical/j7gov1cmnqr9tvg14k621j7t5c@group.calendar.google.com/public/basic.ics",
    ) as file:
        calendar = Calendar.from_ical(file.read())

    link_desc = re.compile(r".*<a .*?href=\"? ?((?:https|http):\/\/[\w0-9\.\/\-\?= ]+)\"?.*?>(.*?)[#0-9 ]*<\/?a>.*")

    # Initialize a list to hold event data
    event_data = []

    # Iterate over each event in the Calendar
    for component in calendar.walk():
        if component.name == "VEVENT":
            # Extract event details
            conference = str(component.get("summary"))
            start = component.get("dtstart").dt
            end = component.get("dtend").dt - timedelta(days=1)
            # If the event is all day, the date might be of type 'date' (instead of 'datetime')
            # Adjust format accordingly
            start = start.strftime("%Y-%m-%d")
            end = end.strftime("%Y-%m-%d")
            year = int(start[:4])

            description = re.sub(
                r"(?:\\s|&nbsp;|\\|\'|<br />|<br>|</[^a][^>]*>|<[^a/][^>]*>)+",
                " ",
                "<a "
                + "<a ".join(
                    str(component.get("description"))
                    .replace("\n", "")
                    .replace("”", '"')
                    .replace("“", '"')
                    .replace("&amp;", "&")
                    .replace("&quot;", '"')
                    .replace("&apos;", "'")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .split("<a ")[1:],
                ),
            )

            try:
                m = re.match(link_desc, description)
                link = m.group(1).strip()
                conference2 = m.group(2).strip()
            except AttributeError:
                continue

            if conference2 != "":
                conference = conference2
            location = str(component.get("location"))

            # Append this event's details to the list
            event_data.append([conference, year, "TBA", start, end, link, location])

    # Convert the list into a pandas DataFrame
    df = pd.DataFrame(event_data, columns=["conference", "year", "cfp", "start", "end", "link", "place"])

    return df


def main(year=None, base=""):
    """Import Python conferences from a Google Calendar .ics file."""
    # If no year is provided, use the current year
    if year is None:
        year = datetime.now(tz=timezone.utc).year

    target_file = Path(base, "_data", "conferences.yml")

    # Load the existing conference data
    df_yml = load_conferences()
    df_yml = df_yml.loc[pd.to_datetime(df_yml["start"]).dt.date > datetime.now(tz=timezone.utc).date()]
    df_new = pd.DataFrame(columns=df_yml.columns)

    # Parse your .ics file and only use future events in the current year
    df = ics_to_dataframe()
    df = df.loc[pd.to_datetime(df["start"]).dt.date > datetime.now(tz=timezone.utc).date()]
    # df = df.loc[df["year"] == year]

    _, reverse_titles = load_title_mappings(reverse=False)

    # Fuzzy match the new data with the existing data
    for y in range(year, year + 10):
        df_merged, df_remote = fuzzy_match(df_yml[df_yml["year"] == y], df.loc[df["year"] == y])
        df_merged["year"] = year
        diff_idx = df_merged.index.difference(df_remote.index)
        df_missing = df_merged.loc[diff_idx, :].sort_values("start")
        df_merged = df_merged.drop(["conference"], axis=1)
        df_merged = merge_conferences(df_merged, df_remote)

        # Concatenate the new data with the existing data
        df_new = pd.concat([df_new, df_merged], ignore_index=True)
        for _index, row in df_missing.iterrows():
            reverse_title = f"""{reverse_titles.get(row["conference"], [row["conference"]])[0]} {row["year"]}"""
            dates = f'{create_nice_date(row)["date"]} ({row["timezone"] if isinstance(row["timezone"], str) else "UTC"}'
            link = f'<a href="{row["link"]}">{row["conference"]}</a>'
            out = f""" * name of the event: {reverse_title}
 * type of event: conference
 * focus on Python: yes
 * approximate number of attendees: Unknown
 * location (incl. country): {row["place"]}
 * dates/times/recurrence (incl. time zone): {dates})
 * HTML link using the format <a href="http://url/">name of the event</a>: {link}"""
            with Path("missing_conferences.txt").open("a") as f:
                f.write(out + "\n\n")
            Path(".tmp").mkdir(exist_ok=True, parents=True)
            with Path(".tmp", f"{reverse_title}.ics".lower().replace(" ", "-")).open("w") as f:
                f.write(
                    f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:{reverse_title}
DTSTART;VALUE=DATE:{row["start"].strftime("%Y%m%d")}
DTEND;VALUE=DATE:{row["end"].strftime("%Y%m%d")}
DESCRIPTION:<a href="{row.link}">{ reverse_title }</a>
LOCATION:{ row.place }
END:VEVENT
END:VCALENDAR""",
                )

    # Fill in missing required fields
    df_new = fill_missing_required(df_new)

    # Write the new data to the YAML file
    write_df_yaml(df_new, target_file)


if __name__ == "__main__":
    # Make argparse to get year and base

    import argparse

    parser = argparse.ArgumentParser(description="Import Python Organizers")
    parser.add_argument("--year", type=int, help="Year to import")

    main(year=parser.parse_args().year)
