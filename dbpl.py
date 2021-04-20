import os
import struct

from enum import Enum


class Flag(Enum):
    DDB_IS_SUBTRACK = 1 << 0 # file is not single-track, might have metainfo in external file
    DDB_IS_READONLY = 1 << 1 # check this flag to block tag writing (e.g. in iso.wv)
    DDB_HAS_EMBEDDED_CUESHEET = 1 << 2

    DDB_TAG_ID3V1 = 1 << 8
    DDB_TAG_ID3V22 = 1 << 9
    DDB_TAG_ID3V23 = 1 << 10
    DDB_TAG_ID3V24 = 1 << 11
    DDB_TAG_APEV2 = 1 << 12
    DDB_TAG_VORBISCOMMENTS = 1 << 13
    DDB_TAG_CUESHEET = 1 << 14
    DDB_TAG_ICY = 1 << 15
    DDB_TAG_ITUNES = 1 << 16

    DDB_TAG_MASK = 0x000fff00


class Track:
    def __init__(self):
        self.uri = None
        self.decoder = None
        self.num = None
        self.startsample = None
        self.endsample = None
        self.duration = None
        self.filetype = None
        self.replaygain_albumgain = None
        self.replaygain_albumpeak = None
        self.replaygain_trackgain = None
        self.replaygain_trackpeak = None
        self.flags = 0
        self.meta = {}


class Playlist:
    def __init__(self):
        self.major_version = None
        self.minor_version = None
        self.tracks_count = None
        self.tracks = []
        self.meta = {}


def read(file):
    playlist = Playlist()

    with open(file, 'rb') as f:
        magic = f.read(4)
        if magic != b'DBPL':
            raise ValueError('invalid magic value')

        # uint8_t
        playlist.major_version, playlist.minor_version = struct.unpack('BB', f.read(2))

        if playlist.major_version != 1:
            raise ValueError('invalid major version')

        if playlist.minor_version < 1:
            raise ValueError('invalid minor version')

        # uint32_t
        tracks_count = struct.unpack('I', f.read(4))[0]

        for i in range(tracks_count):
            track = Track()

            if playlist.minor_version <= 2:
                # uint16_t
                uri_len = struct.unpack('H', f.read(2))[0]
                track.uri = f.read(uri_len)

                # uint8_t
                decoder_len = struct.unpack('B', f.read(1))[0]
                if decoder_len >= 20:
                    raise ValueError('invalid decoder length')

                if decoder_len:
                    track.decoder = f.read(decoder_len)

                # int16_t
                track.num = struct.unpack('h', f.read(2))[0]

            # int32_t
            track.startsample, track.endsample = struct.unpack('ii', f.read(8))

            # float
            track.duration = struct.unpack('f', f.read(4))[0]

            if playlist.minor_version <= 2:
                # legacy filetype support, they say
                # uint8_t
                filetype_len = struct.unpack('B', f.read(1))[0]
                if filetype_len:
                    track.filetype = f.read(filetype_len)

                # floats
                ag, ap, tg, tp = struct.unpack('ffff', f.read(16))
                if ag != 0:
                    track.replaygain_albumgain = ag
                if ap != 0 and ap != 1:
                    track.replaygain_albumpeak = ap
                if tg != 0:
                    track.replaygain_trackgain = tg
                if tp != 0 and tp != 1:
                    track.replaygain_trackpeak = tp

            if playlist.minor_version >= 2:
                # uint32_t
                track.flags = struct.unpack('I', f.read(4))[0]
            elif track.startsample > 0 or track.endsample > 0 or track.num > 0:
                track.flags |= Flag.DDB_IS_SUBTRACK

            # int16_t
            nm = struct.unpack('h', f.read(2))[0]
            for j in range(nm):
                # uint16_t
                value_len = struct.unpack('H', f.read(2))[0]
                if value_len >= 20000:
                    raise ValueError('invalid key length')

                key = f.read(value_len)

                value_len = struct.unpack('H', f.read(2))[0]
                if value_len >= 20000:
                    f.seek(value_len, os.SEEK_CUR)
                else:
                    value = f.read(value_len)
                    if key[0] == ':':
                        value = int(value)
                        if key == ':STARTSAMPLE':
                            track.startsample = value
                        elif key == ':ENDSAMPLE':
                            track.endsample = value
                        else:
                            track.meta[key] = value
                    else:
                        track.meta[key] = value

            playlist.tracks.append(track)

        assert tracks_count == len(playlist.tracks)

        # playlist metadata
        # int16_t
        nm = struct.unpack('H', f.read(2))[0]
        for i in range(nm):
            # int16_t
            key_len = struct.unpack('h', f.read(2))[0]
            if key_len < 0 or key_len >= 20000:
                raise ValueError('invalid length')

            key = f.read(key_len)

            # int16_t
            value_len = struct.unpack('h', f.read(2))[0]
            if value_len < 0 or value_len >= 20000:
                f.seek(value_len, os.SEEK_CUR)
            else:
                value = f.read(value_len)
                playlist.meta[key] = value

    return playlist