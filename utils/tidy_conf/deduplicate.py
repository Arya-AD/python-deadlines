def merge_near_duplicates(group):
    # Fill missing values with the next value then take the first row
    group = group.fillna(method="bfill")
    return group.iloc[0]


def deduplicate(df):
    merged_df = df.groupby("conference").apply(merge_near_duplicates)
    merged_df = merged_df.reset_index(drop=True)
    return merged_df
