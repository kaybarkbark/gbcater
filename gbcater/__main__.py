from .cartridge import folder_to_csv
from pathlib import Path

# TODO: A CLI with click

folder_to_csv(Path("/home/k/Documents/all_games"), Path("/home/k/all_games.csv"))
