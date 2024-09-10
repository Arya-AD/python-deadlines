from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pandas as pd
from tidy_conf import load_conferences


# Filter conferences where CFP closes within the next 10 days
def filter_conferences(df, days=10):
    now = datetime.now(tz=timezone(timedelta(hours=2))).date()
    deadline_threshold = now + timedelta(days=days)

    df["cfp"] = df["cfp_ext"].where(df["cfp_ext"].notna(), df["cfp"])

    # Convert 'cfp' to datetime, errors='coerce' will handle 'TBA' and invalid dates
    df["cfp"] = pd.to_datetime(df["cfp"], errors="coerce").dt.date

    # Filter the DataFrame
    filtered_df = df[((df["cfp"] >= now) & (df["cfp"] <= deadline_threshold))]

    print(filtered_df)

    return filtered_df


# Create a markdown link for each conference
def create_markdown_links(df):
    base_url = "https://pythondeadlin.es/conference/"
    markdown_links = []

    for _, conf in df.iterrows():
        # Replace spaces with hyphens and convert to lowercase for URL
        conf_name_slug = conf["conference"].lower().replace(" ", "-")
        url = f"{base_url}{conf_name_slug}-{conf['year']}/"
        markdown_link = f"[{conf['conference']}]({url})"
        markdown_links.append(markdown_link)

    return markdown_links


# Main function
def main(days=15):
    df = load_conferences()

    upcoming_cfp_conferences = filter_conferences(df, days)

    markdown_links = create_markdown_links(upcoming_cfp_conferences)

    print(f"Conferences with CFP closing within the next {days} days:")
    for link in markdown_links:
        print(link)

    print("\n\n", ", ".join(markdown_links))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Print upcoming conferences with CFP closing within the next 10 days")
    parser.add_argument("--days", type=int, default=15, help="Number of days to look ahead for CFP closing")
    args = parser.parse_args()

    main(args.days)
