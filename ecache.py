#!/usr/bin/python3
# (C) 2015 Thomas Bell
# MIT License

"""Standardised, platform-independent, adaptable caching made for web resources.
"""

import os
import sys
import json
import appdirs
import hashlib
from urllib.error import HTTPError
from urllib.request import Request, urlopen

__version_info__ = (1, 0, 1)
__version__ = ".".join(map(str, __version_info__))

class Cache:
    """An app-specific cache manager.
    
        cache_dir: Accepts a directory path or an (NAME, AUTHOR) tuple for 
            platform-independent per-user caching. Creates the directory if 
            it does not exist.
        user_agent: The user agent to be used when making web requests. 
            Defaults to 'python-ecache/1.0'.
    """
    def __init__(self, cache_dir=appdirs.user_cache_dir("python-ecache", "bell345"), 
                       user_agent="python-ecache/1.0", verbose=False):

        if isinstance(cache_dir, tuple):
            cache_dir = appdirs.user_cache_dir(*cache_dir)

        self.cache_dir = cache_dir
        self.user_agent = user_agent
        self.verbose = verbose
        if not os.path.isdir(self.cache_dir):
            os.mkdir(self.cache_dir)
    
    # Retrieves the file path for a resource with a given unique ID/URL.
    def get_cache_path(self, id):
        hash = hashlib.sha1(id.encode()).hexdigest()
        return os.path.join(self.cache_dir, hash[0], hash)
    
    # Opens the cached file location given a unique ID/URL for reading/writing.
    # Supports the same options as open(), but with a unique ID/URL 
    # instead of a filename.
    def open(self, id, *args, **kwargs):
        cache_path = self.get_cache_path(id)
        if not os.path.isdir(os.path.dirname(cache_path)):
            os.mkdir(os.path.dirname(cache_path))
        return open(cache_path, *args, **kwargs)
    
    # Opens the manifest associated with the cached file location given a 
    # unique ID/URL for reading/writing.
    # Supports the same options as open(), but with a unique ID/URL 
    # instead of a filename.
    def open_mf(self, id, *args, **kwargs):
        mf_path = self.get_cache_path(id) + ".json"
        if not os.path.isdir(os.path.dirname(mf_path)):
            os.mkdir(os.path.dirname(mf_path))
        return open(mf_path, *args, **kwargs)
    
    # Retrieves a resource from the cache given a unique ID/URL.
    def get(self, id):
        if self.verbose: print("Retrieving cache resource: " + id)
        with self.open(id, "rb") as fp:
            return fp.read()
    
    # Saves a resource to the cache given a unique ID/URL and the 
    # content to be saved.
    def save(self, id, content):
        if self.verbose: print("Saving cache resource: " + id)
        with self.open(id, "wb") as fp:
            fp.write(content)
    
    # Removes a resource from the cache given a unique ID/URL.
    def remove(self, id):
        path = self.get_cache_path(id)
        os.remove(path)
    
    # Fetches a remote resource using the given URL.
    # If a fresh copy is available in the cache, it is returned instead 
    # of the remote resource.
    # Utilises the ETag/If-None-Match, Last-Modified/If-Modified-Since 
    # and Cache-Control HTTP headers.
    def fetch(self, url):
        if not os.path.isdir(self.cache_dir):
            os.mkdir(self.cache_dir)
        
        cache_path = self.get_cache_path(url)
        cache_mf = cache_path + ".json"
        manifest = {}
        
        req = Request(url)
        req.add_header("User-Agent", self.user_agent)
        
        if os.path.isfile(cache_path) and os.path.isfile(cache_mf):
            with self.open_mf(url) as mf:
                try:
                    manifest = json.load(mf)
                except:
                    pass
            
            if "etag" in manifest:
                req.add_header("If-None-Match", 
                    manifest["etag"])
            if "last-modified" in manifest:
                req.add_header("If-Modified-Since", 
                    manifest["last-modified"])
        
        try:
            res = urlopen(req)
        except HTTPError as e:
            if os.path.isfile(cache_path):
                return self.get(url)
            else:
                print("Could not load cache URL {}.".format(url))
                raise

        manifest["url"] = url
        if res.getheader("Cache-Control") != "no-cache":
            if res.getheader("ETag"):
                manifest["etag"] = res.getheader("ETag")
            if res.getheader("Last-Modified"):
                manifest["last-modified"] = res.getheader("Last-Modified")
        
        content = res.read()
        if "etag" in manifest or "last-modified" in manifest:
            with self.open_mf(url, "w") as fp:
                json.dump(manifest, fp)
            
            self.save(url, content)
        
        return content