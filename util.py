#!/usr/bin/python3

import os
import sys
import shutil
import threading
import traceback
from time import sleep
from datetime import time, date, datetime, timedelta

class ansi:
    RESET      = "\033[0m"

    BLACK      = "\033[30m"
    RED        = "\033[31m"
    GREEN      = "\033[32m"
    YELLOW     = "\033[33m"
    BLUE       = "\033[34m"
    MAGENTA    = "\033[35m"
    CYAN       = "\033[36m"
    WHITE      = "\033[37m"

    BBLACK      = "\033[30;1m"
    BRED        = "\033[31;1m"
    BGREEN      = "\033[32;1m"
    BYELLOW     = "\033[33;1m"
    BBLUE       = "\033[34;1m"
    BMAGENTA    = "\033[35;1m"
    BCYAN       = "\033[36;1m"
    BWHITE      = "\033[37;1m"

    BG_BLACK   = "\033[40m"
    BG_RED     = "\033[41m"
    BG_GREEN   = "\033[42m"
    BG_YELLOW  = "\033[43m"
    BG_BLUE    = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN    = "\033[46m"
    BG_WHITE   = "\033[47m"

def abort(msg):
    print(str(msg))
    sys.exit(1)

def sensible_input(prompt):
    try:
        return input(prompt)
    except KeyboardInterrupt:
        print("^C")
        exit(0)

def inner_text(el):
    if el.nodeType == el.TEXT_NODE:
        return el.data

    s = ""
    for e in el.childNodes:
        s += inner_text(e)

    return s

def clear():
    cmd = "cls" if os.name == "nt" else "clear"
    # for clearing scrollback
    os.system(cmd)
    os.system(cmd)
    print("\033[3J\033c", end='')

def timestr_to_delta(timestr):
    if isinstance(timestr, timedelta):
        return timestr
    if ":" not in timestr:
        return timedelta(0, float(timestr))
    time_parts = timestr.split(":")
    return timedelta(0, (int(time_parts[0])*60 + int(time_parts[1]))*60 + int(time_parts[2] if len(time_parts) > 2 else 0))

def datestr_to_date(datestr):
    if isinstance(datestr, date):
        return datestr
    date_parts = datestr.split("-")
    return date(int(date_parts[0]), int(date_parts[1]), int(date_parts[2] if len(date_parts) > 2 else 0))

def timestr_to_time(timestr):
    if isinstance(timestr, time):
        return timestr
    time_parts = timestr.split(":")
    return time(int(time_parts[0]), int(time_parts[1]), int(time_parts[2] if len(time_parts) > 2 else 0))

def iso_to_datetime(iso):
    if isinstance(iso, datetime):
        return iso
    if "T" in iso:
        d, t = iso.split("T")
    elif " " in iso:
        d, t = iso.split(" ")

    return datetime.combine(datestr_to_date(d), timestr_to_time(t))

class Progress:
    def __init__(self, msg="Loading", rate=.2, max_length=3, char='.', overwrite=False, fill=True):
        self.msg = msg
        self.rate = rate
        self.max_length = max_length
        self.char = char
        self.overwrite = overwrite
        self.fill = fill

        self.event = threading.Event()
        self.thread = threading.Thread(target=self.worker)

    def worker(self):
        timer = 0
        update_rate = 0.01
        ellipsis = 1
        while True:
            if timer >= self.rate:
                timer = 0
                ellipsis = (ellipsis + 1) % (self.max_length + 1)
                msg = "{}{}{}".format(self.msg, self.char*ellipsis, ' '*(self.max_length-ellipsis))
                spacing = shutil.get_terminal_size((80, 24))[0] - len(msg)
                print("{}{}\r".format(msg, spacing * " " if self.fill else ""), end='')

            if self.event.is_set():
                if not self.overwrite:
                    print("")
                break

            timer += update_rate
            sleep(update_rate)

    def stop(self):
        self.event.set()
        self.thread.join()

    def __enter__(self):
        self.thread.start()

    def __exit__(self, type, value, traceback):
        self.stop()
