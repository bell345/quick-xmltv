#!/usr/bin/python3

import re
import shutil
from time import sleep
from math import floor, ceil
from urllib.error import HTTPError
from abc import ABCMeta, abstractmethod
from datetime import datetime, date, time, timedelta

from getch import getch
from util import *
from xmltv import get_program_listings

def ask_channels(channels, selection=[]):
    def final_choice(chan=None, retry=True):
        items = ["[F]inish", "[L]ist"]
        if chan != None: items.append("[C]ontinue")
        if retry: items.append("[R]etry")
        prompt = ", ".join(items) + "? "
        choice = sensible_input(prompt).lower()[0]

        if choice == "c" and chan != None:
            if chan.id in selection:
                print("Channel has already been selected!")
            else: selection.append(chan.id)
            return ask_channels(channels, selection)
        elif choice == "r" and retry:
            return ask_channels(channels, selection)
        elif choice == "f":
            if chan != None:
                if chan.id in selection:
                    print("Channel has already been selected!")
                else: selection.append(chan.id)
            return [channels[id] for id in selection]
        elif choice == "l":
            for id in selection:
                print(str(channels[id]))
            print("[*] {}".format(str(chan)))
            return final_choice(chan)
        else:
            print("Invalid choice.")
            return final_choice(chan)

    clear()
    query = sensible_input("Type a channel ID, or a search query (^C to quit): ")
    print("")

    matches = [channels[id] for id in channels if channels[id].matches(query) and id not in selection]

    if len(matches) == 0:
        print("No matches found.")
        return final_choice()
    elif len(matches) == 1:
        print("Single match found: {}".format(str(matches[0])))
        return final_choice(matches[0])
    else:
        print("{} matches:".format(len(matches)))
        for i, chan in enumerate(matches):
            print("[{}] {}".format(i, str(chan)))

        choice = sensible_input("Select [0-{}], [R]etry? ".format(len(matches)-1))
        if choice[0].lower() == "r":
            return ask_channels(channels, selection)

        try:
            index = int(choice)
        except ValueError:
            print("Invalid selection.")
            return ask_channels(channels, selection)
        except IndexError:
            print("Invalid selection.")
            return ask_channels(channels, selection)

        return final_choice(matches[index], retry=False)

def print_epg(channels, start, end, highlight=None):
    ANSI_RE     = re.compile(r'(\033\[.*?[\x40-\x7e])')
    escs        = lambda s, end=None: sum(map(len, ANSI_RE.findall(s[:end])))
    align       = lambda dt, align=60*30: datetime.fromtimestamp(floor(dt.timestamp() / align) * align)
    timestr     = lambda dt: dt.strftime("%H:%M")
    time_to_pos = lambda dt, length: min(int((max(dt - start, ZERODELTA).seconds / gap.seconds) * length), length)

    def cover(full, sub, start, bound=True, overwrite=True, fill=False, fillchar=" "):
        start = max(start, 0)
        end = start + (len(sub) if overwrite else 0)
        prefix = full[:start]
        if len(prefix) < start and fill:
            prefix += fillchar * (start - len(prefix) - 1)
        s = prefix + sub + full[end:]
        if bound: s = s[:len(full)]
        return s

    def insert(full, sub, start, **kwargs):
        return cover(full, sub, start, overwrite=False, **kwargs)

    def fillto(s, start, fillto, fillchar=" ", bound=True):
        i = s.find(fillto, start)
        if i == -1:
            i = len(s)
        s = cover(s, (i - start) * fillchar, start, bound)
        return s

    columns, rows = shutil.get_terminal_size((80, 24))
    SZ = 5 # len("00:00")
    ZERODELTA = timedelta(0)

    if isinstance(start, str): start = iso_to_datetime(start)
    if isinstance(end, str): end = iso_to_datetime(end)
    start = align(start)
    end = align(end)
    gap = end - start

    listings = get_program_listings(channels, start, end)
    if not listings:
        abort("No programs found.")

    # end = align(max([max(listings[id], key=lambda p:p.end) for id in listings], key=lambda p:p.end).end)
    # end = align(max([max([p.end for p in listings[id]]) for id in listings]))

    datestr = start.date().isoformat()
    firstcol_len = max([len(c.id) for c in channels])
    firstcol_len = max(len(datestr), firstcol_len) + 1

    prefix = ansi.BWHITE + " " * (firstcol_len - len(datestr) - 1) + datestr + " " + ansi.RESET
    time_scale = ""
    remaining = max(columns - firstcol_len, SZ)

    divisions = (gap.seconds / (60 * 15))
    while divisions * (SZ + 4) > remaining:
        divisions /= 2

    spacing = floor(remaining / divisions - SZ)
    for i in range(int(divisions)):
        time_scale += timestr(start + (gap / divisions) * i) + " " * spacing
    # time_scale += timestr(start + (gap / divisions) * int(divisions))
    i = time_to_pos(datetime.now(), remaining)
    i = max(0, min(i, columns - firstcol_len - 1))
    part = ansi.BLACK + ansi.BG_WHITE
    time_scale = insert(insert(time_scale, part, i, bound=False), ansi.RESET, i + len(part) + 1, bound=False)
    print(prefix + time_scale)

    for ch in channels:
        id = ch.id
        prefix = ansi.BWHITE + " " * (firstcol_len - len(id) - 1) + id + " " + ansi.RESET
        remaining = columns - firstcol_len
        s = " " * remaining
        highlight_i = -1
        def calci(prog, s): i = time_to_pos(prog.start, remaining); return i + escs(s, i)

        for prog in listings[id]:
            i = calci(prog, s)
            if prog == highlight:
                highlight_i = i
            part = "| " + prog.title
            s = fillto(cover(s, part, i), i + len(part), "|")

        if highlight_i != -1:
            sub = ansi.BLACK + ansi.BG_WHITE
            s = insert(s, sub, highlight_i, bound=False)
            next_i = s.find("|", highlight_i + len(sub) + 1)
            if next_i != -1:
                s = insert(s, ansi.RESET, next_i, bound=False)

        s += ansi.RESET
        print(prefix + s)

class EPGFrameInterface(metaclass=ABCMeta):
    """ This function is called when the screen is ready to be redrawn:
        when this method is called, the terminal has been cleared.
    """
    @abstractmethod
    def update(self):
        raise NotImplementedError("update() is required to be implemented")

    """ This function is called when a single input character, or multi-byte
        control character, has been received from the user.
        Parameters:
            ch: A string that represents the raw input received from the user.
                Can contain multiple bytes. Ctrl-C and Ctrl-D are captured.
    """
    @abstractmethod
    def listener(self, ch):
        raise NotImplementedError("listener() is required to be implemented")

class EPGMainFrame(EPGFrameInterface):
    def update(self):
        print_epg(self.channels, self.start, self.end, self.highlight)
        print("")
        print(self.info)

    def listener(self, ch):
        matches = lambda c: ch.lower().startswith(c.lower())
        check = lambda x: any(map(matches, x)) if type(x) != str else matches(x)

        listing = self.listings[self.highlight.channel]
        i = listing.index(self.highlight) if self.highlight in listing else -1
        j = self.find_chindex()

        if check(self.LEFT):
            if i == -1: self.reset()
            elif i != 0: self.highlight = listing[i-1]
            else: self.time_travel(self.BACKWARDS)
            self.curr_time = self.bound(self.highlight.start)

        elif check(self.RIGHT):
            if i == -1: self.reset()
            elif i != len(listing)-1: self.highlight = listing[i+1]
            else: self.time_travel(self.FORWARDS)
            self.curr_time = self.bound(self.highlight.start)

        elif check(self.UP):
            if j == -1: self.reset()
            elif j != 0:
                self.highlight = self.find_closest(self.channels[j-1].id)

        elif check(self.DOWN):
            if j == -1: self.reset()
            elif j != len(self.channels)-1:
                self.highlight = self.find_closest(self.channels[j+1].id)

        elif check('\r'): # enter/return
            self.info = self.highlight.info()

        elif check('q'):
            exit(0)

        elif check('o'):
            pass

        elif check('r'):
            self.curr_time = datetime.now()
            self.find_closest(self.highlight.channel)

        self.update()


class EPG:
    UP, DOWN, RIGHT, LEFT = ['\033[A', '\xe0H'], ['\033[B', '\xe0P'], ['\033[C', '\xe0M'], ['\033[D', '\xe0K']
    MODE_EPG, MODE_OPTIONS, MODE_CHANNELS = 0,1,2
    mode = 0

    def __init__(self, channels, start, end, cache):
        self.channels = channels
        self.start = start
        self.end = end
        self.cache = cache

        self.columns, self.rows = shutil.get_terminal_size((80, 24))
        self.info = "-- QUICK XMLTV --".center(self.columns)
        self.highlight = None
        self.curr_time = datetime.now()

        self.reset()
        self.update()

    @property
    def listings(self):
        return get_program_listings(self.channels, self.start, self.end)

    def reset(self):
        listings = self.listings
        for id in listings:
            if len(listings[id]) == 0:
                continue
            self.highlight = listings[id][0]
            return

    def find_chindex(self, prog=None):
        prog = prog if prog is not None else self.highlight
        for i,ch in enumerate(self.channels):
            if ch.id == prog.channel:
                return i
        return -1

    def bound(self, dt):
        return max(min(dt, self.end), self.start)

    def find_closest(self, id, start=None, get_listings=None):
        start = start if start is not None else self.curr_time
        get_listings = get_listings if get_listings is not None else lambda: self.listings

        progs = None
        d = start.date()
        while not progs:
            try:
                self.fetch(d)
            except HTTPError:
                if progs: break
                else: return None
            progs = get_listings()[id]
            d -= timedelta(1, 0)
            enclosed = list(filter(lambda p: p.start <= start and p.end >= start, progs))
            if enclosed:
                return enclosed[-1]
        return min(progs, key=lambda p: abs(self.bound(p.start) - start))

    FORWARDS = 1
    BACKWARDS = -1
    _last_time_travel = 0
    def time_travel(self, dir=None, interval=timedelta(0, 60*30), timeout=0.1):
        dir = dir if dir is not None else self.FORWARDS

        now = datetime.now().timestamp()
        if self._last_time_travel + timeout > now:
            return
        self.end += interval * dir
        self.start += interval * dir
        self._last_time_travel = now

    def jump(self, dt):
        get_full_listings = lambda: get_program_listings(self.channels)
        self.curr_time = dt
        self.highlight = self.find_closest(self.highlight.channel, get_listings=get_full_listings)
        self.update_time()

    def _epg_update(self):
        print_epg(self.channels, self.start, self.end, self.highlight)
        print("")
        print(self.info)
        print("")
        print("Jump: ([R]ight now, [N]ext day, [P]revious day), [Q]uit: ")

    def _opt_update(self):
        pass

    def _chan_update(self):
        pass

    def fetch(self, d):
        try:
            for ch in self.channels:
                if d.isoformat() not in ch.programs:
                    with Progress("Loading program information for {}".format(ch.id)):
                        ch.fetch(d, self.cache)
        except HTTPError as e:
            print("Failed to load program information.")
            abort(e)

    def update_time(self):
        align = lambda dt, align=60*30: datetime.fromtimestamp(floor(dt.timestamp() / align) * align)
        while self.highlight.start >= align(self.end) or self.curr_time > align(self.end):
            self.time_travel(self.FORWARDS,  timeout=0)
        while self.highlight.end <= align(self.start) or self.curr_time < align(self.start):
            self.time_travel(self.BACKWARDS, timeout=0)

        for ch in self.channels:
            self.fetch(self.start.date())
            self.fetch(self.end.date())
            self.fetch(self.curr_time.date())
            if len(list(filter(lambda p: self.start >= p.start, self.listings[ch.id]))) == 0:
                self.fetch((self.start - timedelta(1, 0)).date())

    def update(self):
        self.update_time()
        clear()

        if self.mode == self.MODE_EPG: self._epg_update()
        elif self.mode == self.MODE_OPTIONS: self._opt_update()
        elif self.mode == self.MODE_CHANNELS: self._chan_update()

    def _epg_listener(self, ch):
        matches = lambda c: ch.lower().startswith(c.lower())
        check = lambda x: any(map(matches, x)) if type(x) != str else matches(x)
        day = timedelta(1, 0)

        listing = self.listings[self.highlight.channel]
        i = listing.index(self.highlight) if self.highlight in listing else -1
        j = self.find_chindex()

        if check(self.LEFT):
            if i == -1: self.reset()
            elif i != 0: self.highlight = listing[i-1]
            else: self.time_travel(self.BACKWARDS)
            self.curr_time = self.bound(self.highlight.start)

        elif check(self.RIGHT):
            if i == -1: self.reset()
            elif i != len(listing)-1: self.highlight = listing[i+1]
            else: self.time_travel(self.FORWARDS)
            self.curr_time = self.bound(self.highlight.start)

        elif check(self.UP):
            if j == -1: self.reset()
            elif j != 0:
                self.highlight = self.find_closest(self.channels[j-1].id)

        elif check(self.DOWN):
            if j == -1: self.reset()
            elif j != len(self.channels)-1:
                self.highlight = self.find_closest(self.channels[j+1].id)

        elif check('\r'): # enter/return
            self.info = self.highlight.info()

        elif check('q'):
            exit(0)

        elif check('o'):
            pass

        elif check('r'):
            self.jump(datetime.now())

        elif check('n'):
            self.jump(self.curr_time + day)

        elif check('p'):
            self.jump(self.curr_time - day)

        self.update()

    def _opt_listener(self, ch):
        pass

    def _chan_listener(self, ch):
        pass

    def listener(self):
        try:
            ch = getch()
        except KeyboardInterrupt:
            exit(0)

        if ch == "\033":
            try:
                next = getch()
                ch += next
                if next == "[":
                    next = getch()
                    while ord(next) not in range(64, 127):
                        ch += next
                        next = getch()
                    ch += next
            except KeyboardInterrupt:
                exit(0)
        elif ch == "\xe0":
            try:
                ch += getch()
            except KeyboardInterrupt:
                exit(0)

        if self.mode == self.MODE_EPG: self._epg_listener(ch)
        elif self.mode == self.MODE_OPTIONS: self._opt_listener(ch)
        elif self.mode == self.MODE_CHANNELS: self._chan_listener(ch)
