# LRC Downloader 🎵

Downloads synchronized `.lrc` files for tracks from multiple sources.

## Installation

Install [Python](https://www.python.org/downloads/), then copy and paste this into the command prompt (Win + R -> cmd):

```bash
git clone https://github.com/desired-god/desiredlrcs.git
cd desiredlrcs
pip install -r requirements.txt
```

## Usage

(Win + R -> cmd)

```bash
cd desiredlrcs
python desiredlrcs.py
```

A GUI will open — select your folder with audio files (or playlists with audio files inside) and click "Start Download".

In Russia you might need a [vpn](https://t.me/SnowfallVPN_bot?start=partner_8627656179/) to use it

## Dependencies

- mutagen — reading FLAC tags
- requests — HTTP requests to lyrics sources

## Lyrics Sources

- lrclib.net
- lrc.red
- ChartLyrics
- AZLyrics
- LyricsOnDemand
- Lyrics.ovh
- NetEase Cloud Music