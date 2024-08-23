import sys

sys.path.append(".")
from import_python_official import main as official_updater
from import_python_organizers import main as organizer_updater
from sort_yaml import sort_data

if __name__ == "__main__":
    official_updater()
    sort_data(skip_links=True)
    organizer_updater()
    sort_data()
