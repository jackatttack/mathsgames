"""
Install or update Maths Games in Pythonista.

Run it again at any time to update: the game code is replaced with the
latest version from GitHub, and your saved settings are kept.

    Installs to:  Documents/Maths Games/
    Launcher:     Documents/Maths Games/maths_games.py

Options (for testing):
    --from-folder PATH   install from a local copy instead of GitHub
    --target PATH        install somewhere other than Documents/Maths Games
    --no-open            do not open the launcher afterwards
"""

import argparse
import io
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile


REPOSITORY = "jackatttack/mathsgames"
REF = "main"
APP_FOLDER = "Maths Games"
LAUNCHER = "maths_games.py"

# Files the app writes while you play. Updates never replace or remove them.
PLAYER_FILES = ("settings.json",)


def default_target():
    return os.path.join(os.path.expanduser("~/Documents"), APP_FOLDER)


def download_release(work_dir):
    """Download the repository zip, unpack it, return the release folder."""
    url = "https://codeload.github.com/{}/zip/refs/heads/{}".format(
        REPOSITORY, REF
    )
    print("Downloading {} ...".format(REPOSITORY))

    with urllib.request.urlopen(url) as response:
        data = response.read()

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        archive.extractall(work_dir)
        top = archive.namelist()[0].split("/")[0]

    return os.path.join(work_dir, top)


def save_player_files(target):
    """Read every player file under target into memory, by relative path."""
    saved = {}

    if not os.path.isdir(target):
        return saved

    for folder, _, files in os.walk(target):
        for name in files:
            if name in PLAYER_FILES:
                path = os.path.join(folder, name)
                with open(path, "rb") as handle:
                    saved[os.path.relpath(path, target)] = handle.read()

    return saved


def restore_player_files(target, saved):
    for relative, data in saved.items():
        path = os.path.join(target, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)


def install_from(release, target):
    """Replace every top-level item the release ships; leave anything else.

    Returns (shipped names, saved player files).
    """
    os.makedirs(target, exist_ok=True)
    saved = save_player_files(target)
    shipped = sorted(
        name for name in os.listdir(release) if not name.startswith(".")
    )

    for name in shipped:
        source = os.path.join(release, name)
        destination = os.path.join(target, name)

        if os.path.isdir(destination) and not os.path.islink(destination):
            shutil.rmtree(destination)
        elif os.path.exists(destination):
            os.remove(destination)

        if os.path.isdir(source):
            shutil.copytree(
                source, destination,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        else:
            shutil.copy2(source, destination)

    restore_player_files(target, saved)
    return shipped, saved


def read_version(folder):
    try:
        with open(os.path.join(folder, "VERSION")) as handle:
            return handle.read().strip()
    except OSError:
        return "unknown version"


def open_launcher(path):
    """Open the launcher in Pythonista's editor; quietly skip elsewhere."""
    try:
        import editor
        editor.open_file(path)
    except Exception:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install or update Maths Games")
    parser.add_argument("--from-folder")
    parser.add_argument("--target")
    parser.add_argument("--no-open", action="store_true")
    args, _ = parser.parse_known_args(argv)

    target = os.path.abspath(args.target or default_target())
    work_dir = tempfile.mkdtemp(prefix="mathsgames_install_")

    try:
        if args.from_folder:
            release = os.path.abspath(args.from_folder)
        else:
            release = download_release(work_dir)

        version = read_version(release)
        shipped, saved = install_from(release, target)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    launcher = os.path.join(target, LAUNCHER)

    print("")
    print("Installed Maths Games ({}) to:".format(version))
    print("    " + target)
    print("Updated {} item(s); kept {} saved settings file(s).".format(
        len(shipped), len(saved)
    ))
    print("Play: run {}. Run the installer again any time to update.".format(
        LAUNCHER
    ))

    if not args.no_open:
        open_launcher(launcher)

    return 0


if __name__ == "__main__":
    main()