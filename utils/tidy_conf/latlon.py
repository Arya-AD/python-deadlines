import time
import urllib

import requests
from tqdm import tqdm


def add_latlon(data):
    """Add latitude and longitude to the data."""
    # Cache for locations
    cache = {}
    # Copy of data for unlocated conferences
    data_copy = []

    # Go through the data and check if the location is already in the cache
    for i, q in tqdm(enumerate(data), total=len(data)):
        if ("place" not in q) or ("online" in q["place"].lower()):
            # Ignore online conferences
            continue
        if "location" in q:
            # If location is already present, add it to the cache
            cache[q["place"]] = q["location"][0]
            # continue
        else:
            # Add to the copy if location is not present for speed
            data_copy.append((i, q))

    # Go through the copy and get the latitude and longitude
    for i, q in tqdm(data_copy):
        # Get a shorter location
        try:
            q["place"] = q["place"].split(",")[0].strip() + ", " + q["place"].split(",")[-1].strip()
        except IndexError:
            tqdm.write(f"IndexError: {q['place']}")

        # Check if the location is already in the cache
        places = [q["place"]]
        if "extra_places" in q:
            places += q["extra_places"]

        new_location = []
        for place in places:
            place = place.strip()
            if place in cache and cache[place] is not None:
                new_location += [
                    {
                        "title": f'{q["conference"]} {q["year"]}',
                        "latitude": cache[place]["latitude"],
                        "longitude": cache[place]["longitude"],
                    },
                ]

            else:
                headers = {"User-Agent": "Pythondeadlin.es Location Search/0.1 (https://pythondeadlin.es)"}
                # Get the location from Openstreetmaps
                url = "https://nominatim.openstreetmap.org/search" + "?format=json&q=" + urllib.parse.quote(place)
                response = requests.get(url, timeout=10, headers=headers)

                if response:
                    try:
                        response = response.json()
                        new_location += [
                            {
                                "title": f'{q["conference"]} {q["year"]}',
                                "latitude": float(response[0]["lat"]),
                                "longitude": float(response[0]["lon"]),
                            },
                        ]
                        cache[place] = new_location[-1]
                    except IndexError:
                        cache[place] = None
                        tqdm.write(f"No response from Openstreetmaps for {q['place']}")
                    time.sleep(2)
                else:
                    cache[place] = None
                    tqdm.write(f"No response from Openstreetmaps for {q['place']}")
        else:
            if new_location:
                data[i]["location"] = new_location
    return data
