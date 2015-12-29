#!/usr/bin/python3

import re
import shutil
from getch import getch
from time import sleep
from math import floor, ceil
from urllib.error import HTTPError
from datetime import datetime, date, time, timedelta

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

    def cover(full, sub, start, bound=True, overwrite=True):
        start = max(start, 0)
        end = start + (len(sub) if overwrite else 0)
        s = full[:start] + sub + full[end:]
        if bound: s = s[:len(full)]
        return s
    def insert(full, sub, start, bound=True):
        return cover(full, sub, start, bound=bound, overwrite=False)
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

    firstcol_len = max([len(c.id) for c in channels]) + 1

    time_scale = " " * firstcol_len
    remaining = max(columns - firstcol_len, SZ)

    divisions = (gap.seconds / (60 * 15))
    while divisions * (SZ + 4) > remaining:
        divisions /= 2

    spacing = floor(remaining / divisions - SZ)
    for i in range(int(divisions)):
        time_scale += timestr(start + (gap / divisions) * i) + " " * spacing
    # time_scale += timestr(start + (gap / divisions) * int(divisions))
    i = time_to_pos(datetime.now(), remaining) + firstcol_len
    part = ansi.BLACK + ansi.BG_WHITE
    time_scale = insert(insert(time_scale, part, i, bound=False), ansi.RESET, i + len(part) + 1, bound=False)
    print(time_scale)
    
    for ch in channels:
        id = ch.id
        prefix = ansi.BWHITE + id + " " * (firstcol_len - len(id)) + ansi.RESET
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

def epg_navigation(channels, start, end, cache):
    UP, DOWN, RIGHT, LEFT = '\033[A', '\033[B', '\033[C', '\033[D'
    INTERVAL = timedelta(0, 60*30) # 30 minutes
    listings = get_program_listings(channels, start, end)
    highlight = None
    columns, rows = shutil.get_terminal_size((80, 24))
    info = "-- QUICK XMLTV --".center(columns)

    def reset():
        nonlocal highlight
        for id in listings:
            if len(listings[id]) == 0:
                continue
            highlight = listings[id][0]

    reset()
    curr_time = highlight.start

    def find_chindex():
        for i,ch in enumerate(channels):
            if ch.id == highlight.channel:
                return i
        return -1
    def find_closest(id, start):
        return min(listings[id], key=lambda p: abs(p.start - start))

    def time_travel_back():
        nonlocal end
        nonlocal start
        end -= INTERVAL
        start -= INTERVAL
    def time_travel_forwards():
        nonlocal end
        nonlocal start
        end += INTERVAL
        start += INTERVAL
    
    def update():
        nonlocal listings
        while highlight.start > end:
            time_travel_forwards()
        while highlight.end < start:
            time_travel_back()

        for ch in channels:
            try:
                if start.date().isoformat() not in ch.programs:
                    with Progress("Loading program information for {}".format(ch.id)):
                        ch.fetch(start.date(), cache)
                if end.date().isoformat() not in ch.programs:
                    with Progress("Loading program information for {}".format(ch.id)):
                        ch.fetch(end.date(), cache)
            except HTTPError:
                pass

        clear()
        listings = get_program_listings(channels, start, end)
        print_epg(channels, start, end, highlight)
        print("")
        print(info)

    update()
    while True:
        try:
            ch = getch()
        except KeyboardInterrupt:
            exit(0)
        
        if ch == "\033":
            try:
                next = getch()
                if next == "[":
                    ch += next
                    next = getch()
                    while ord(next) not in range(64, 127):
                        ch += next
                        next = getch()
                    ch += next
                elif ord(next) in range(64, 96):
                    ch += next
            except KeyboardInterrupt:
                exit(0)

            listing = listings[highlight.channel]
            i = listing.index(highlight) if highlight in listing else -1
            j = find_chindex()
            if ch == LEFT:
                if i == -1: reset()
                elif i != 0: highlight = listing[i-1]
                else: time_travel_back()
                curr_time = highlight.start
            elif ch == RIGHT:
                if i == -1: reset()
                elif i != len(listing)-1: highlight = listing[i+1]
                else: time_travel_forwards()
                curr_time = highlight.start
            elif ch == UP:
                if j == -1: reset()
                elif j != 0:
                    next_ch = channels[j-1]
                    highlight = find_closest(next_ch.id, curr_time)
            elif ch == DOWN:
                if j == -1: reset()
                elif j != len(channels)-1:
                    next_ch = channels[j+1]
                    highlight = find_closest(next_ch.id, curr_time)
        else:
            if ord(ch) == 13: # enter/return
                info = highlight.info()

        update()
        