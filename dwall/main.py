#!/usr/bin/env python

import subprocess
import shlex
import os
from pathlib import Path
from sys import argv
import pyheif
import base64
from io import BytesIO, StringIO
import re
from xml.dom.minidom import parseString
from dataclasses import dataclass, field
from PIL import Image

try:
    WALLPAPER_NAME = argv[1]
    Path("/home/user/.config/dwall/theme").write_text(WALLPAPER_NAME)

except IndexError:
    WALLPAPER_NAME = Path("/home/user/.config/dwall/theme").read_text().strip()


DWALL_PATH = os.environ["DWALL_PATH"]


def main():
    hour = get_hour()
    img_path = img_path_builder(hour)

    if not Path(img_path).exists():
        install_heic()

    set_wallpaper(img_path)


# TODO use python's own library
def get_hour():
    cmd = "date +%H"
    cmd = shlex.split(cmd)

    hour = subprocess.check_output(cmd)
    hour = hour.decode()
    hour = int(hour)

    return hour


# DONE
def set_wallpaper(img_path):
    func_ified = wayland_ified

    try:
        os.environ["WAYLAND_DISPLAY"]

    except KeyError:
        func_ified = x_ified

        try:
            os.environ["DISPLAY"]

        except KeyError:
            raise NoDisplayError()

    pkill_cmd, cmd, env = func_ified()

    lex_and_run(pkill_cmd)
    lex_and_run(cmd % img_path, env)


def install_heic():
    heic_path = heic_path_builder()

    try:
        heic_container = pyheif.open_container(heic_path)
    except FileNotFoundError:
        print(f'No file exists in the path: "{heic_path}"')
        exit(1)

    timetable = extract_timetable(heic_container)
    images = extract_images(heic_container)
    link_wallpaper(timetable, images)


def extract_images(heic_container):
    images = heic_container.top_level_images

    for i, image in enumerate(images):
        image = image.image.load()

        images[i] = image = Image.frombytes(
            image.mode,
            image.size,
            image.data,
            "raw",
            image.mode,
            image.stride,
        )

    return images


def extract_timetable(heic_container):
    primary_image = heic_container.primary_image.image.load()
    data = primary_image.metadata[0]["data"]

    try:
        bplist = h24_decoder(data)
    except AttributeError:
        bplist = solar_decoder(data)

    ps = subprocess.Popen(
        shlex.split("plistutil --format xml"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    plist, _ = ps.communicate(input=bplist)

    plist = parseString(plist.decode("utf-8"))

    array = plist.getElementsByTagName("array")[0]
    dicts = array.getElementsByTagName("dict")

    timetable = []

    for dict_ in dicts:
        hour = dict_.getElementsByTagName("real").item(0)
        hour = hour.firstChild.nodeValue
        hour = int(round(float(hour) * 24))
        # hour = float(hour) * 24

        index = dict_.getElementsByTagName("integer").item(0)
        index = index.firstChild.nodeValue
        index = int(index)

        timetable.append(Time(hour, index))

    timetable.sort()

    return timetable


def _decoder(pattern, data):
    matcher = re.compile(pattern)
    match = re.search(matcher, data)
    bplist = match.group(1)
    bplist = base64.b64decode(bplist)

    return bplist


def h24_decoder(data):
    pattern = rb"apple_desktop:h24=\"([^\"]*)\""
    return _decoder(pattern, data)


def solar_decoder(data):
    pattern = rb"apple_desktop:solar=\"([^\"]*)\""
    return _decoder(pattern, data)


def link_wallpaper(timetable, images):
    if len(timetable) == 1:
        hour = timetable[0].hour
        path = img_path_builder(hour)

        images[0].save(path, "JPEG")

    for i, time_ in enumerate(timetable):
        hour = time_.hour
        index = time_.index

        path = img_path_builder(hour)

        images[index].save(path, "JPEG")

        cursor = (hour + 1) % 24
        next_time = timetable[(i + 1) % len(timetable)].hour

        while cursor != next_time:
            ln_path = img_path_builder(cursor)

            ln_cmd = f"ln -s {path} {ln_path}"
            cursor = (cursor + 1) % 24

            lex_and_run(ln_cmd)


# DONE
def img_path_builder(hour):
    return f"{DWALL_PATH}/jpg/{WALLPAPER_NAME}-{hour}.jpg"


def heic_path_builder():
    return f"{DWALL_PATH}/heic/{WALLPAPER_NAME}.heic"


# TODO
def x_ified():
    return wayland_ified()


# DONE
def wayland_ified():
    pkill_cmd = "pkill swaybg"

    cmd = """
    riverctl spawn 'swaybg --image "%s" --mode fill --output "*"'
    """

    env = {
        "XDG_RUNTIME_DIR": os.environ["XDG_RUNTIME_DIR"],
        "WAYLAND_DISPLAY": os.environ["WAYLAND_DISPLAY"],
    }

    return (pkill_cmd, cmd, env)


# DONE
def lex_and_run(cmd, env=None):
    cmd = shlex.split(cmd)

    if env != None:
        subprocess.run(
            cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    else:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@dataclass(init=True, eq=True, order=True, frozen=True)
class Time:
    hour: int = field(init=True, compare=True)
    index: int = field(init=True)


# DONE
class NoDisplayError(Exception):
    def __init__(self, message="No display server is running"):
        self.message = message
        super().__init__(self.message)


if __name__ == "__main__":
    main()
