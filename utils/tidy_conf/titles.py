from tidy_conf.yaml import load_title_mappings
from tqdm import tqdm


def tidy_titles(data):
    """Tidy up conference titles by replacing misspellings and alternative names."""
    spellings, alt_names = load_title_mappings()
    for i, q in tqdm(enumerate(data.copy()), total=len(data)):
        if "conference" in q:
            low_conf = q["conference"].lower().strip()
            # Replace common misspellings
            for spelling in spellings:
                if spelling.lower() in low_conf:
                    # Find the index in the lower case string and replace it in the original string
                    index = low_conf.index(spelling.lower())
                    q["conference"] = q["conference"][:index] + spelling + q["conference"][index + len(spelling) :]

            # Replace alternative names
            for key, values in alt_names.items():
                if key.lower().strip() == low_conf:
                    if "alt_name" not in q:
                        q["alt_name"] = values[0].strip()
                    continue
                for value in values:
                    if value.lower().strip() == low_conf:
                        if "alt_name" not in q and q["conference"].strip() != key:
                            q["alt_name"] = q["conference"].strip()
                        q["conference"] = key.strip()
            data[i] = q
    return data
