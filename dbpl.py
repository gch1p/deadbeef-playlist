from __future__ import annotations
from typing import List, Optional
from struct import pack, unpack
from enum import Enum

import os


class Flag(Enum):
    IS_SUBTRACK = 1 << 0  # file is not single-track, might have metainfo in external file
    IS_READONLY = 1 << 1  # check this flag to block tag writing (e.g. in iso.wv)
    HAS_EMBEDDED_CUESHEET = 1 << 2

    TAG_ID3V1 = 1 << 8
    TAG_ID3V22 = 1 << 9
    TAG_ID3V23 = 1 << 10
    TAG_ID3V24 = 1 << 11
    TAG_APEV2 = 1 << 12
    TAG_VORBISCOMMENTS = 1 << 13
    TAG_CUESHEET = 1 << 14
    TAG_ICY = 1 << 15
    TAG_ITUNES = 1 << 16

    TAG_MASK = 0x000fff00


class Track:
    uri = Optional[str]
    decoder = Optional[str]
    num = Optional[int]
    startsample = Optional[int]
    endsample = Optional[int]
    duration = Optional[float]
    filetype = Optional[str]
    replaygain_albumgain = Optional[int]
    replaygain_albumpeak = Optional[int]
    replaygain_trackgain = Optional[int]
    replaygain_trackpeak = Optional[int]
    flags: int
    meta: dict

    def __init__(self):
        self.uri = ''
        self.decoder = ''
        self.num = 0
        self.startsample = 0
        self.endsample = 0
        self.duration = 0
        self.filetype = ''
        self.replaygain_albumgain = 0
        self.replaygain_albumpeak = 0
        self.replaygain_trackgain = 0
        self.replaygain_trackpeak = 0
        self.flags = 0
        self.meta = {}

    def get_uri(self) -> str:
        return self.meta[':URI'] if ':URI' in self.meta else self.uri

    def set_uri(self, uri) -> None:
        self.uri = uri
        self.meta[':URI'] = uri

    def get_startsample(self) -> int:
        return self.meta[':STARTSAMPLE'] if ':STARTSAMPLE' in self.meta else self.startsample

    def set_startsample(self, value) -> None:
        self.startsample = value
        self.meta[':STARTSAMPLE'] = value

    def get_endsample(self) -> int:
        return self.meta[':ENDSAMPLE'] if ':ENDSAMPLE' in self.meta else self.endsample

    def set_endsample(self, value) -> None:
        self.endsample = value
        self.meta[':ENDSAMPLE'] = value

    def get_writable_meta(self) -> dict:
        meta = {}
        for key, value in self.meta.items():
            if key[0] != '_' and key[0] != '!':
                meta[key] = value
        return meta

    def pack(self) -> bytes:
        buf = bytearray()

        uri_b = self.get_uri().encode()
        buf.extend(pack('H', len(uri_b)))
        buf.extend(uri_b)

        if self.decoder:
            decoder_b = self.decoder.encode()
            buf.append(len(decoder_b))
            buf.extend(decoder_b)
        else:
            buf.append(0)

        buf.extend(pack('h', self.num))
        buf.extend(pack('i', self.get_startsample()))
        buf.extend(pack('i', self.get_endsample()))
        buf.extend(pack('f', self.duration))

        ft_b = self.filetype.encode()
        buf.append(len(ft_b))
        if len(self.filetype):
            buf.extend(ft_b)

        buf.extend(pack('f', self.replaygain_albumgain))
        buf.extend(pack('f', self.replaygain_albumpeak))
        buf.extend(pack('f', self.replaygain_trackgain))
        buf.extend(pack('f', self.replaygain_trackpeak))
        buf.extend(pack('I', self.flags))

        meta = self.get_writable_meta()
        buf.extend(pack('h', len(meta)))

        for key, value in meta.items():
            value = str(value).encode()
            key = key.encode()
            key_len, value_len = len(key), len(value)

            buf.extend(pack('H', key_len))
            if key_len:
                buf.extend(key)

            buf.extend(pack('H', value_len))
            if value_len:
                buf.extend(value)

        return bytes(buf)


class Playlist:
    MINOR_VERSION = 2
    MAJOR_VERSION = 1

    major_version: Optional[int]
    minor_version: Optional[int]
    tracks = List[Track]
    meta: dict
    
    def __init__(self, file: str):
        self.file = file
        self.major_version = None
        self.minor_version = None
        self.tracks = []
        self.meta = {}

        self.read()

    def add_track(self, track: Track) -> None:
        self.tracks.append(track)

    def pack(self) -> bytes:
        pass

    def read(self) -> None:
        with open(self.file, 'rb') as f:
            magic = f.read(4)
            if magic != b'DBPL':
                raise ValueError('invalid magic value')

            # uint8_t
            self.major_version, self.minor_version = unpack('BB', f.read(2))

            if self.major_version != 1:
                raise ValueError('invalid major version %d' % self.major_version)

            if self.minor_version < 1:
                raise ValueError('invalid minor version %d' % self.minor_version)

            # uint32_t
            tracks_count = unpack('I', f.read(4))[0]

            for i in range(tracks_count):
                track = Track()

                if self.minor_version <= 2:
                    # uint16_t
                    uri_len = unpack('H', f.read(2))[0]
                    track.uri = f.read(uri_len).decode()

                    # uint8_t
                    decoder_len = unpack('B', f.read(1))[0]
                    if decoder_len >= 20:
                        raise ValueError('invalid decoder length %d' % decoder_len)

                    if decoder_len:
                        track.decoder = f.read(decoder_len).decode()

                    # int16_t
                    track.num = unpack('h', f.read(2))[0]

                # int32_t
                ss, es = unpack('ii', f.read(8))
                track.set_startsample(ss)
                track.set_endsample(es)

                # float
                track.duration = unpack('f', f.read(4))[0]

                if self.minor_version <= 2:
                    # legacy filetype support, they say
                    # uint8_t
                    filetype_len = unpack('B', f.read(1))[0]
                    if filetype_len:
                        track.filetype = f.read(filetype_len).decode()

                    # floats
                    ag, ap, tg, tp = unpack('ffff', f.read(16))
                    if ag != 0:
                        track.replaygain_albumgain = ag
                    if ap != 0 and ap != 1:
                        track.replaygain_albumpeak = ap
                    if tg != 0:
                        track.replaygain_trackgain = tg
                    if tp != 0 and tp != 1:
                        track.replaygain_trackpeak = tp

                if self.minor_version >= 2:
                    # uint32_t
                    track.flags = unpack('I', f.read(4))[0]
                elif track.startsample > 0 or track.endsample > 0 or track.num > 0:
                    track.flags |= Flag.IS_SUBTRACK

                # int16_t
                meta_count = unpack('h', f.read(2))[0]
                for j in range(meta_count):
                    # uint16_t
                    value_len = unpack('H', f.read(2))[0]
                    if value_len >= 20000:
                        raise ValueError('invalid key length')

                    key = f.read(value_len).decode()

                    value_len = unpack('H', f.read(2))[0]
                    if value_len >= 20000:
                        f.seek(value_len, os.SEEK_CUR)
                    else:
                        value = f.read(value_len)
                        if key[0] == ':':
                            if key == ':STARTSAMPLE':
                                track.set_startsample(int(value))
                            elif key == ':ENDSAMPLE':
                                track.set_endsample(int(value))
                            else:
                                track.meta[key] = value.decode()
                        else:
                            track.meta[key] = value.decode()

                self.add_track(track)

            assert tracks_count == len(self.tracks)

            # playlist metadata
            # int16_t
            meta_count = unpack('H', f.read(2))[0]
            for i in range(meta_count):
                # int16_t
                key_len = unpack('h', f.read(2))[0]
                if key_len < 0 or key_len >= 20000:
                    raise ValueError('invalid length')

                key = f.read(key_len).decode()

                # int16_t
                value_len = unpack('h', f.read(2))[0]
                if value_len < 0 or value_len >= 20000:
                    f.seek(value_len, os.SEEK_CUR)
                else:
                    value = f.read(value_len)
                    self.meta[key] = value.decode()

    def save(self, file: str = None) -> None:
        if file is None:
            file = self.file

        with open(file, 'wb') as f:
            f.write(b'DBPL')
            f.write(pack('BB', Playlist.MAJOR_VERSION, Playlist.MINOR_VERSION))
            f.write(pack('I', len(self.tracks)))
            for track in self.tracks:
                f.write(track.pack())

            f.write(pack('h', len(self.meta)))
            for key, value in self.meta.items():
                value = str(value)
                key_len, value_len = len(key), len(value)

                f.write(pack('H', key_len))
                if key_len:
                    f.write(key.encode())

                f.write(pack('H', value_len))
                if value_len:
                    f.write(value.encode())
