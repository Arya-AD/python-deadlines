from pathlib import Path

import yaml
from tqdm import tqdm


def auto_add_sub(data):
    """Automatically add a subfield to the data based on the conference name.

    This function uses a list of keywords to match the conference name to a subfield.
    """
    keywords = load_subs()
    for i, q in tqdm(enumerate(data.copy()), total=len(data)):
        if "sub" not in q:
            for key, value in keywords.items():
                if any(word in q["conference"].lower() for word in value):
                    data[i]["sub"] = key
                    break
    return data


def load_subs():
    with Path("utils", "tidy_conf", "data", "subs.yml").open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data
