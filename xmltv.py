#!/usr/bin/python3

import gzip
import random
import traceback
import xml.dom.minidom as MD
from urllib.parse import urljoin
from urllib.error import HTTPError
from time import timezone as curr_tz
from datetime import datetime, date, time, timedelta

from util import *

class TVChannel:
    def __init__(self, element, programs=[]):
        self.element = element
        self.id = element.getAttribute("id")
        self.display_name = inner_text(element.getElementsByTagName("display-name")[0])
        self.base_url = inner_text(random.choice(element.getElementsByTagName("base-url")))
        self.dates = [inner_text(e) for e in element.getElementsByTagName("datafor")]

        self.programs = {}

    def fetch(self, d, cache):
        if isinstance(d, str):
            d = datestr_to_date(d)

        iso = d.isoformat()
        if iso not in self.programs:
            self.programs[iso] = []

        if len(self.programs[iso]) == 0:
            if len(self.dates) > 0 and iso not in self.dates:
                return None
            try:
                content = cache.fetch(urljoin(self.base_url, "{}_{}.xml.gz".format(self.id, iso)))
                decomp = gzip.decompress(content)
                dom = MD.parseString(decomp).documentElement
            except HTTPError as e:
                if e.code == 404:
                    return None
                else:
                    print("Error when retrieving program info: ")
                    abort(traceback.format_exc())
            except Exception as e:
                print("Error when retrieving program info: ")
                abort(traceback.format_exc())

            self.programs[iso] = [TVProgram(e) for e in dom.getElementsByTagName("programme")]

    def matches(self, query):
        query = query.lower()
        return self.id.lower().find(query) != -1 or self.display_name.lower().find(query) != -1

    def __str__(self):
        return "{}: {}".format(self.id, self.display_name)

class TVProgram:
    def parseTimestamp(ts, ignore_timezone=False):
        timestamp = ""
        timezone = -curr_tz
        if ts == None or len(ts) == 0:
            return None

        if " " in ts:
            timestamp, timezone = ts.split(" ")
            sign = -1 if timezone[0] == "-" else 1
            hours = int(timezone[1:3])
            minutes = int(timezone[3:5])
            timezone = sign * (hours*60 + minutes)*60
        else:
            timestamp = ts

        now = datetime.now()
        spec = { "year": now.year, "month": now.month,   "day": 1,
                 "hour": 0,        "minute": 0,          "second": 0 }

        def consume(length, name):
            nonlocal spec
            nonlocal timestamp
            if len(timestamp) < length:
                return True
            spec[name] = int(timestamp[:length])
            timestamp  = timestamp[length:]
            return False

        def calc():
            d = datetime(spec["year"], spec["month"], spec["day"],
                         spec["hour"], spec["minute"], spec["second"])
            if not ignore_timezone:
                d += timedelta(0, timezone + curr_tz, 0)
            return d

        if consume(4,   "year"): return calc()
        if consume(2,  "month"): return calc()
        if consume(2,    "day"): return calc()
        if consume(2,   "hour"): return calc()
        if consume(2, "minute"): return calc()
        if consume(2, "second"): return calc()
        return calc()


    def __init__(self, element):
        def get_tag(tag, el=element):
            res = el.getElementsByTagName(tag)
            if len(res) == 0:
                return el
            else: return res[0]
        def text_tag(tag, default=None, el=element):
            tags = el.getElementsByTagName(tag)
            if len(tags) == 0:
                return default
            return inner_text(tags[0]) or default
        list_tag = lambda tag, el=element: [inner_text(e) for e in el.getElementsByTagName(tag)]

        now = datetime.now()
        self.element     = element
        self.title       = text_tag("title", default="???")
        self.sub_title   = text_tag("sub-title")
        self.description = text_tag("desc")
        self.actors      = list_tag("actor", el=get_tag("credits"))
        self.director    = text_tag("director", el=get_tag("credits"))
        d = text_tag("date")
        self.date        = TVProgram.parseTimestamp(d) if d else now
        self.categories  = list_tag("category")
        self.rating      = text_tag("value", el=get_tag("rating"))

        self.start       = TVProgram.parseTimestamp(element.getAttribute("start"), ignore_timezone=True) or now
        self.end         = TVProgram.parseTimestamp(element.getAttribute("stop"), ignore_timezone=True) or now
        self.channel     = element.getAttribute("channel")

    def __str__(self):
        return "{} [{} - {}]".format(self.title.upper(), self.start.strftime("%H:%M"), self.end.strftime("%H:%M"))
    
    def __eq__(self, other):
        return other.element == self.element

    def info(self):
        s = ""
        if self.start != self.end:
            s += "[{} - {}]\n".format(self.start.strftime("%H:%M"), self.end.strftime("%H:%M"))
        s += self.title.upper()

        sub_stuff = []
        if self.sub_title: sub_stuff.append(self.sub_title)
        if self.date and self.date != self.start: sub_stuff.append(self.date.strftime("%Y"))

        if len(sub_stuff) > 0: s += " (" + ", ".join(sub_stuff) + ")"
        if self.description: s += "\n\n" + self.description

        attrs = {}
        if self.director: attrs["Directed by"] = self.director
        if self.actors: attrs["Featuring"] = ", ".join(self.actors)
        if self.categories: attrs["Tags"] = ", ".join(self.categories)
        if self.rating: attrs["Rated"] = self.rating

        if len(attrs.keys()) > 0:
            s += "\n\n"
            for key in attrs:
                s += "{}: {}\n".format(key, attrs[key])

        return s

def parse_channels(channel_url, cache):
    try:
        content = cache.fetch(channel_url)
        decomp = gzip.decompress(content)
        dom = MD.parseString(decomp).documentElement
    except Exception as e:
        print("Error when fetching channel info: ")
        abort(traceback.format_exc())

    channels = {}
    for e in dom.getElementsByTagName("channel"):
        channels[e.getAttribute("id")] = TVChannel(e)

    return channels

def get_program_listings(channels, start, end):
    listings = {}
    s = start.date().isoformat()
    e = end.date().isoformat()
    for c in channels:
        listings[c.id] = []
        if s in c.programs:
            listings[c.id] += [p for p in c.programs[s] if p.end > start and p.start < end]
        if e in c.programs and start.date() != end.date():
            listings[c.id] += [p for p in c.programs[e] if p.end > start and p.start < end]
        listings[c.id].sort(key=lambda p: p.start)

    if sum([len(listings[id]) for id in listings]) == 0:
        return None
    return listings