# src/saves.py
"""Locate character saves under a game data root."""
import os, glob

def find_saves(root):
    pat = os.path.join(root, "DataStore", "*", "*_Character_*.cerimal")
    return [p for p in glob.glob(pat) if not os.path.basename(p).split(".cerimal")[-1].startswith(".bak")]

def default_root():
    # Standard LocalLow location for the game.
    local_low = os.path.join(os.path.expanduser("~"), "AppData", "LocalLow",
                             "Moon Studios", "NoRestForTheWicked")
    return local_low if os.path.isdir(local_low) else os.getcwd()
