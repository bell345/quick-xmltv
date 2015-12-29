#!/usr/bin/python3

import re
import random
import appdirs
import argparse
from math import floor, ceil
from datetime import date, time, datetime, timedelta

from ecache import Cache
from util import *
from xmltv import *
from ui import *

__version__ = (1, 1, 0)
__version_info__ = ".".join(map(str, __version__))

APP_NAME    = "quick-xmltv"
APP_AUTHOR  = "bell345"
APP_VERSION = __version_info__
LICENSE = """The MIT License (MIT)
Copyright (c) 2015 Thomas Bell

Permission is hereby granted, free of charge, to any person obtaining a copy 
of this software and associated documentation files (the "Software"), to deal 
in the Software without restriction, including without limitation the rights to 
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies 
of the Software, and to permit persons to whom the Software is furnished to do 
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all 
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
SOFTWARE."""
def print_license():
    print(LICENSE)
    exit(0)

cache = Cache((APP_NAME, APP_AUTHOR), "{}/{}".format(APP_NAME, APP_VERSION))

def load_channels(channels, start, end):
    for chan in channels:
        with Progress("Loading channel {}".format(chan.id), overwrite=True):
            chan.fetch(start, cache)
            chan.fetch(end, cache)
    return channels

def main():
    parser = argparse.ArgumentParser(prog=APP_NAME,
            description="XMLTV parser to query online EPG guides.",
            epilog="(C) Thomas Bell 2015, MIT License. For more information, use with the --license option.")
    parser.add_argument("--version", action="version", version=APP_VERSION)
    parser.add_argument("--license", action="store_true",
            help="show license information and exit")

    parser.add_argument("-u", "--channel-url",
            default="http://xml.oztivo.net/xmltv/channels.xml.gz",
            help="URL used to retrieve the list of channels for querying.")
    parser.add_argument("channel", nargs="*",
            help="A channel ID to query. If not given, an interactive prompt is provided.")
    parser.add_argument("-d", "--date", default=datetime.now().date(), type=datestr_to_date,
            help="The date (YYYY-MM-DD) you wish to query. Defaults to today.")
    parser.add_argument("-t", "--time", default=datetime.now().time(), type=timestr_to_time,
            help="The time (HH:MM:SS) at which the query will begin. Defaults to now.")
    parser.add_argument("-r", "--range", default=timedelta(0, 60*60*2), type=timestr_to_delta,
            help="The duration (HH:MM:SS) the query will cover. Defaults to 2 hours.")
    args = parser.parse_args()

    if args.license:
        print_license()

    with Progress("Loading channels", overwrite=True):
        channels = parse_channels(args.channel_url, cache)

    valid_channels = []
    if len(args.channel) > 0:
        for id in args.channel:
            if id in channels:
                valid_channels.append(channels[id])
            else:
                print("Channel {} not found.".format(id))

    if len(valid_channels) == 0:
        valid_channels = ask_channels(channels)

    start = datetime.combine(args.date, args.time)
    end = start + args.range
    load_channels(valid_channels, start.date(), end.date())

    epg_navigation(valid_channels, start, end, cache)

if __name__ == "__main__":
    main()
