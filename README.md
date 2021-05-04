# deadbeef-playlist

This is a Python library for reading and writing playlists in the "DBPL" binary
format, created by my absolute favorite desktop audio player
[DeaDBeeF](https://github.com/DeaDBeeF-Player/deadbeef).

I created it to be able to edit paths to audio files in the playlist, although
it's possible to change any tracks properties.

## Installation

It's available in Pypi:
```
pip install dbpl
```

## Example

Let's imagine you have a large `.dbpl` playlist with hundreds of items, and you want
to change tracks paths from `/data/music` to `/Volumes/music`. Write a script
named `script.py`:

```python
from dbpl import Playlist
from argparse import ArgumentParser

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--input', required=True, help='input file')
    parser.add_argument('--output', required=True, help='output file')
    args = parser.parse_args()

    playlist = Playlist(args.input)
    for t in playlist.tracks:
        uri = t.get_uri()
        uri = uri.replace('/data/music', '/Volumes/music')
        t.set_uri(uri)
    playlist.save(args.output)
```

## License

BSD-2c