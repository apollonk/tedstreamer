#!/usr/bin/env python2
# -*- coding: utf8 -*-

"""
    ted.py: Browse and stream TED talks on the command line
"""

#==============================================================================
# This Script retrieves, lists and streams TED talks from the
# TED website, including subtitles.
#==============================================================================

#==============================================================================
#    Copyright 2014 Apollon Koutlidis <apollon@planewalk.net>
#
#    Subtitles code and some other bits are from Joe Di Castro's
#    ted-talks-download, with thanks 
#    (https://github.com/joedicastro/ted-talks-download)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#==============================================================================

__author__ = "Apollon Koutlidis - apollon@planewalk.net"
__license__ = "GNU General Public License version 3"
__date__ = "04/01/2014"
__version__ = "0.2"

try:
    import pycurl
    import re
    import sys
    import os
    import subprocess
    import time
    import json
    import urllib2
    import optparse
    import platform
except ImportError:
    # Checks the installation of the necessary python modules
    print((os.linesep * 2).join(["An error found importing one module:",
          str(sys.exc_info()[1]), "You need to install it", "Stopping..."]))
    sys.exit(-2)


class Ted:
    """Class representing the interface to the TED website"""

    def __init__(self):
        self.talks = []
        self.webpage = ''

    def search_talks(self,term):
        """
           Searches the TED website for a specific term and updates the
           talks dictionary
        """

        url = 'http://www.ted.com/search?cat=ss_talks&q=' + term
        self.webpage = urllib2.urlopen(url).readlines()
        p = re.compile('^.*h5 class="title"..a href="(?P<url>.*)">(?P<title>.*)./a.', re.IGNORECASE)
        for line in self.webpage:
            if p.match(line):
                m = p.search(line)
                self.talks.append(Talk(m.group('title'),m.group('url')))

    def print_talks(self):
        """Print list of talks currently in the list"""

        index = 0
        for talk in self.talks:
            sys.stdout.write(str(index)+": "+talk.title+"\n")
            index += 1

    def stream_talk(self, opts, index=0):
        """Start streaming a TED talk by its index in the list"""
        self.talks[index].stream(opts)

class Talk:
    """Class representing a single TED Talk"""

    def __init__(self,title,url):
        self.title = title
        self.url = url
        self.contents = ''

    def stream(self, opts):
        """Interface to the stream object"""
        sys.stdout.write("Will now stream "+self.title+"\n")
        stream = TedStream(self.url, opts)
        stream.start_stream()

class TedStream:
    """Streaming class for TED talks"""

    def __init__(self, url, opts):
        self.url = url
        self.talk_vids = dict()
        self.sublang=opts.sublang
        self.quality=opts.quality
        self.player=opts.player

        self.subs = ''
        self.populate()

    def start_stream(self):
        """Start the stream"""

        self.__do_stream__(self.get_video(self.quality))

    def get_video(self, quality='standard'):
        """Retrieve the video URL for streaming"""

        return self.talk_vids[quality.lower()]

    def populate(self):
        """Retrieve properties and metadata for a TED talk"""

        # Get the webpage in an array of lines
        self.webpage = urllib2.urlopen(self.url).read()
        regex_intro = re.compile('introDuration%22%3A(\d+\.?\d+)%2C')
        regex_id = re.compile('talkId%22%3A(\d+)%2C')
        regex_url = re.compile('id="no-flash-video-download" href="(.+)"')
        regex_vids = re.compile('^<script.*,"htmlStreams":(?P<json>\[.+\])', re.IGNORECASE)
        regex_vid = re.compile('http://.+\/(.*\.mp4)')
        # Need to find the video URL from the page
        for line in self.webpage.split('\n'):
            if regex_vids.match(line):
                m = regex_vids.search(line)
                # Got it, parse the JSON into a quality:URL dict
                v = json.loads(m.group('json'))
                for video in v:
                    self.talk_vids[video['id'].lower()] = video['file']
        try:
            talk_intro = ((float(regex_intro.findall(self.webpage)[0])
                            + 1) * 1000)
            talk_id = int(regex_id.findall(self.webpage)[0])
            if self.sublang:
                self.subs = self.get_sub(talk_id,talk_intro,self.sublang)
        except IndexError:
            sys.stdout.write('Maybe this video is not available for download.\n')

    def __do_stream__(self,talk_url):
        """Start streaming a TED talk"""

        # Adjust subtitle option
        subopts = {
                    "mpv":"--sub",
                    "mplayer":"-sub",
                    "vlc":"--sub-file",
                    "cvlc":"--sub-file"
                  }
        subopt = subopts[ self.player ]

        if self.subs:
            with open("/tmp/__tedtalk_sub", 'w') as srt_file:
                srt_file.write(self.subs)
            subprocess.call([self.player, talk_url, subopt, 
                    "/tmp/__tedtalk_sub"])
        else:
            subprocess.call([self.player, talk_url])

    def get_sub(self, tt_id, tt_intro, sub):
        """Get TED Subtitle in JSON format & convert it to SRT Subtitle."""
    
        def srt_time(tst):
            """Format Time from TED Subtitles format to SRT time Format."""
            secs, mins, hours = ((tst / 1000) % 60), (tst / 60000), (tst / 3600000)
            right_srt_time = ("{0:02d}:{1:02d}:{2:02d},{3:3.0f}".
                              format(int(hours), int(mins), int(secs),
                                     divmod(secs, 1)[1] * 1000))
            return right_srt_time

        #sub = ("{0}.{1}.srt".format(tt_video[:-4], lang)
        srt_content = ''
        tt_url = 'http://www.ted.com/talks'
        sub_url = '{0}/subtitles/id/{1}/lang/{2}'.format(tt_url, tt_id, sub)
        # Get JSON sub
        json_file = urllib2.urlopen(sub_url).readlines()
   
        if json_file:
            for line in json_file:
                if line.find('captions') == -1 and line.find('status') == -1:
                    json_file.remove(line)
        else:
            print("Subtitle '{0}' not found.".format(sub))

        if json_file:
            try:
                json_object = json.loads(json_file[0])
                if 'captions' in json_object:
                    caption_idx = 1
                    if not json_object['captions']:
                        print("Subtitle '{0}' not available.".format(sub))
                    for caption in json_object['captions']:
                        start = tt_intro + caption['startTime']
                        end = start + caption['duration']
                        idx_line = '{0}'.format(caption_idx)
                        time_line = '{0} --> {1}'.format(srt_time(start),
                                                         srt_time(end))
                        text_line = '{0}'.format(caption['content'].
                                                 encode("utf-8"))
                        srt_content += '\n'.join([idx_line, time_line, text_line,
                                                  '\n'])
                        caption_idx += 1
                elif 'status' in json_object:
                    print("This is an error message returned by TED:{0}{0} - "
                          "{1}{0}{0}Probably because the subtitle '{2}' is not "
                          "available.{0}".format(os.linesep,
                                     json_object['status']['message'],
                                     sub))
            except ValueError:
                print("Subtitle '{0}' it's a malformed json file.".format(sub))
        return srt_content

def check_exec_posix(prog):
    """Check if the program is installed in a *NIX platform.

    Returns one value:

    (boolean) found - True if the program is installed

    """
    found = True
    try:
        subprocess.Popen([prog, '--help'], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
    except OSError:
        found = False
    return found

def options():
    """Defines the command line arguments and options for the script."""

    usage = """usage: %prog [Options] search_term [search term ...]

    e.g.:

    %prog zombie jesus"""
    desc = "Lists and streams TED Talks (with optional subtitles) from the command line."
    parser = optparse.OptionParser(usage=usage, version="%prog " + __version__,
                                   description=desc)

    parser.add_option("-s", "--sub", dest="sublang",
              help="use subtitle language SUBLANG, e.g. en,es,zh-cn... (default: no subtitles)",
              default=False)
    parser.add_option("-q", "--quality", dest="quality",
              help="set video quality to QUALITY, i.e. standard or high (default: high)",
              default='high')
    parser.add_option("-p", "--player", dest="player",
              help="set video player to PLAYER, i.e. mpv or mplayer (default: mpv)",
              default='mpv')
    parser.add_option("-f", "--first", action="store_true", dest="playfirst",
              help="Play first video found, no menus presented (default: False)",
              default=False)

    return parser

def main():
    """Main loop"""

    # first, parse the options & arguments
    (opts, args) = options().parse_args()

    if not args:
        options().print_help()
        sys.exit(1)

    #if not opts.sublang:
    #    opts.sublang='off'

    t = Ted()
    t.search_talks('+'.join(args))
    if opts.playfirst:
        t.stream_talk(opts)
    else:
        t.print_talks()
        t.stream_talk(opts, index=int(raw_input("Choose a video: ")))

if __name__ == "__main__":
    #WIN_OS = True if platform.system() == 'Windows' else False
    #if not WIN_OS:
    #    FOUND = check_exec_posix('mpv')
    #    if not FOUND:
    #        FOUND = check_exec_posix('mplayer')
    main()
