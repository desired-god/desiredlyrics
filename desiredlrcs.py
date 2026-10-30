#!/usr/bin/env python3
import os
import sys
import threading
import time
import json
import re
import html
from concurrent.futures import ThreadPoolExecutor, as_completed
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional, Dict, Tuple
import requests
from mutagen import File as MutagenFile


COLORS = {
    'bg': '#1e1e1e', 'fg': '#e0e0e0', 'fg_secondary': '#888888',
    'accent': '#4a9eff', 'accent_hover': '#5aadff', 'success': '#4caf50',
    'error': '#f44336', 'warning': '#ff9800', 'input_bg': '#2d2d2d',
    'border': '#3d3d3d',
}


class LyricsCache:
    def __init__(self, cache_file: Path = None):
        self.cache: Dict[str, Optional[str]] = {}
        self.cache_file = cache_file or Path('.lrc_cache.json')
        self.load()

    def load(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
            except:
                self.cache = {}

    def save(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except:
            pass

    def key(self, artist: str, title: str) -> str:
        return f"{artist.lower()}|{title.lower()}"

    def get(self, artist: str, title: str) -> Optional[str]:
        return self.cache.get(self.key(artist, title))

    def set(self, artist: str, title: str, lyrics: Optional[str]):
        self.cache[self.key(artist, title)] = lyrics
        self.save()


class LyricsSearcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.cache = LyricsCache()

    def search(self, artist: str, title: str) -> Optional[str]:
        sources = [
            self._lrclib,
            self._lrc_red,
            self._chartlyrics,
            self._azlyrics,
            self._lyricsondemand,
            self._lyricsplus,
            self._netease,
            self._amll,
            self._lyricsovh,
        ]

        for source in sources:
            lyrics = source(artist, title)
            if lyrics and len(lyrics.strip()) > 30:
                self.cache.set(artist, title, lyrics)
                return lyrics

        return None

    def _lrclib(self, artist: str, title: str) -> Optional[str]:
        queries = [
            {"track_name": title, "artist_name": artist},
            {"track_name": title},
            {"q": f"{artist} {title}"},
        ]

        for params in queries:
            try:
                resp = self.session.get(
                    "https://lrclib.net/api/get",
                    params=params,
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    lyrics = data.get('syncedLyrics') or data.get('plainLyrics')
                    if lyrics and self._is_lyrics(lyrics):
                        return lyrics
                time.sleep(0.15)
            except:
                pass
        return None

    def _chartlyrics(self, artist: str, title: str) -> Optional[str]:
        try:
            resp = self.session.get(
                "http://api.chartlyrics.com/apiv1.asmx/SearchLyricDirect",
                params={"artist": artist, "song": title},
                timeout=10
            )
            if resp.status_code == 200:
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(resp.text)
                    lyrics = root.find('.//{http://api.chartlyrics.com/}Lyric')
                    if lyrics is not None and lyrics.text:
                        return lyrics.text.strip()
                except:
                    pass
        except:
            pass
        return None

    def _azlyrics(self, artist: str, title: str) -> Optional[str]:
        clean_artist = re.sub(r'[^\w\s]', '', artist).strip().lower().replace(' ', '')
        clean_title = re.sub(r'[^\w\s]', '', title).strip().lower().replace(' ', '')

        url = f"https://www.azlyrics.com/lyrics/{clean_artist}/{clean_title}.html"

        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                match = re.search(
                    r'<!-- Usage of azlyrics\.com content by any third-party lyrics provider is prohibited -->(.*?)<!--',
                    resp.text,
                    re.DOTALL
                )
                if match:
                    lyrics = match.group(1)
                    lyrics = re.sub(r'<[^>]+>', '', lyrics)
                    lyrics = html.unescape(lyrics).strip()
                    if self._is_lyrics(lyrics):
                        return lyrics
        except:
            pass
        return None

    def _lyricsondemand(self, artist: str, title: str) -> Optional[str]:
        clean_artist = re.sub(r'[^\w\s-]', '', artist).strip().lower().replace(' ', '-')
        clean_title = re.sub(r'[^\w\s-]', '', title).strip().lower().replace(' ', '-')

        urls = [
            f"https://www.lyricsondemand.com/{clean_artist[:1]}/{clean_artist}/{clean_title}lyrics.html",
            f"https://www.lyricsondemand.com/{clean_artist[:1]}/{clean_artist}/{clean_title}.html",
        ]

        for url in urls:
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200:
                    match = re.search(
                        r'<div class="lry">(.*?)</div>',
                        resp.text,
                        re.DOTALL | re.IGNORECASE
                    )
                    if match:
                        lyrics = match.group(1)
                        lyrics = re.sub(r'<[^>]+>', '', lyrics)
                        lyrics = html.unescape(lyrics).strip()
                        if self._is_lyrics(lyrics):
                            return lyrics
            except:
                pass
        return None

    def _genie(self, artist: str, title: str) -> Optional[str]:
        try:
            search_url = "https://www.genie.co.kr/search/search?query="
            params = f"{artist} {title}"

            resp = self.session.get(search_url + params, timeout=15)
            if resp.status_code == 200:
                pass
        except:
            pass
        return None

    def _lyricsovh(self, artist: str, title: str) -> Optional[str]:
        try:
            paths = [
                f"v1/{artist}/{title}",
                f"v1/{artist.replace(' ', '%20')}/{title.replace(' ', '%20')}",
                f"v1/{artist}/{title.split('(')[0].strip()}",
            ]

            for path in paths:
                resp = self.session.get(f"https://api.lyrics.ovh/{path}", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    lyrics = data.get('lyrics')
                    if lyrics and self._is_lyrics(lyrics):
                        return lyrics
                time.sleep(0.2)
        except:
            pass
        return None

    def _lrc_red(self, artist: str, title: str) -> Optional[str]:
        try:
            url = f"https://lrclib.net/api/search?query={artist} {title}"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    lyrics = item.get('syncedLyrics') or item.get('plainLyrics')
                    if lyrics and self._is_lyrics(lyrics):
                        return lyrics
        except:
            pass
        return None

    def _lyricsplus(self, artist: str, title: str) -> Optional[str]:
        try:
            url = "https://lyricsplus.firebaseapp.com/api/search"
            params = {"q": f"{artist} {title}"}
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    for item in data:
                        if isinstance(item, dict):
                            lyrics = item.get('lyrics') or item.get('text')
                            if lyrics and self._is_lyrics(lyrics):
                                return lyrics
                elif isinstance(data, dict):
                    lyrics = data.get('lyrics') or data.get('text')
                    if lyrics and self._is_lyrics(lyrics):
                        return lyrics
        except:
            pass
        return None

    def _amll(self, artist: str, title: str) -> Optional[str]:
        try:
            search_queries = [
                f"{artist} - {title}",
                title,
                f"{artist} {title}"
            ]

            for query in search_queries:
                url = f"https://amll.herokuapp.com/api/search?q={query}"
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        item = data[0]
                        lyrics = item.get('lyrics') or item.get('text')
                        if lyrics and self._is_lyrics(lyrics):
                            return lyrics
                time.sleep(0.15)
        except:
            pass
        return None

    def _netease(self, artist: str, title: str) -> Optional[str]:
        try:
            search_url = "https://netease-cloud-music-api-five-roan-25.vercel.app/search"
            params = {"keywords": f"{artist} {title}", "type": 1}

            resp = self.session.get(search_url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                songs = data.get('result', {}).get('songs', [])
                if songs:
                    song_id = songs[0]['id']

                    lyrics_url = f"https://netease-cloud-music-api-five-roan-25.vercel.app/lyric?id={song_id}"
                    resp2 = self.session.get(lyrics_url, timeout=15)
                    if resp2.status_code == 200:
                        lrc_data = resp2.json()
                        lrc = lrc_data.get('lrc', {}).get('lyric')
                        if lrc and self._is_lyrics(lrc):
                            return lrc
        except:
            pass
        return None

    def _is_lyrics(self, text: str) -> bool:
        if not text or len(text) < 50:
            return False

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if len(lines) < 3:
            return False

        bad_patterns = ['<!DOCTYPE', '<html', '<head>', '404', 'Not Found',
                       'Access Denied', 'rate limit', 'captcha']
        for pattern in bad_patterns:
            if pattern.lower() in text.lower():
                return False

        return True


class FastLRCApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LRC Downloader")
        self.root.geometry("700x620")
        self.root.configure(bg=COLORS['bg'])
        self.root.resizable(True, True)

        self.directory = tk.StringVar()
        self.force_mode = tk.BooleanVar()
        self.is_running = False
        self.searcher = LyricsSearcher()
        self.total_tracks = 0
        self.processed_tracks = 0
        self.results = {'ok': 0, 'skip': 0, 'fail': 0}

        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, style='Dark.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        title = tk.Label(
            main_frame,
            text="📄 LRC Downloader 📄",
            font=("Segoe UI", 20, "bold"),
            bg=COLORS['bg'],
            fg=COLORS['fg']
        )
        title.pack(pady=(0, 15))

        tk.Label(main_frame, text="Music folder:",
                font=("Segoe UI", 10), bg=COLORS['bg'], fg=COLORS['fg']).pack(anchor=tk.W)

        dir_input = ttk.Frame(main_frame, style='Dark.TFrame')
        dir_input.pack(fill=tk.X, pady=(5, 15))

        self.dir_entry = tk.Entry(
            dir_input, textvariable=self.directory,
            font=("Segoe UI", 10), bg=COLORS['input_bg'],
            fg=COLORS['fg'], insertbackground=COLORS['fg'],
            relief=tk.FLAT, bd=8
        )
        self.dir_entry.insert(0, "Enter folder path...")
        self.dir_entry.config(fg=COLORS['fg_secondary'])
        self.dir_entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.dir_entry.bind("<FocusOut>", self._on_entry_focus_out)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)

        tk.Button(
            dir_input, text="📁", font=("Segoe UI", 12),
            bg=COLORS['input_bg'], fg=COLORS['fg'],
            activebackground=COLORS['border'],
            relief=tk.FLAT, bd=0, padx=12, cursor="hand2",
            command=self.browse_directory
        ).pack(side=tk.LEFT, padx=(8, 0))

        opt_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        opt_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Checkbutton(
            opt_frame, text="Overwrite existing .lrc files",
            variable=self.force_mode,
            font=("Segoe UI", 10), bg=COLORS['bg'], fg=COLORS['fg'],
            activebackground=COLORS['bg'], selectcolor=COLORS['bg'],
            cursor="hand2"
        ).pack(anchor=tk.W)

        thread_frame = ttk.Frame(opt_frame, style='Dark.TFrame')
        thread_frame.pack(anchor=tk.W, pady=(8, 0))
        tk.Label(thread_frame, text="Threads:",
                font=("Segoe UI", 10), bg=COLORS['bg'], fg=COLORS['fg']).pack(side=tk.LEFT, padx=(0, 8))

        self.threads_var = tk.StringVar(value="6")
        tk.Spinbox(
            thread_frame, from_=1, to=16, textvariable=self.threads_var,
            font=("Segoe UI", 10), bg=COLORS['input_bg'],
            fg=COLORS['fg'], insertbackground=COLORS['fg'],
            relief=tk.FLAT, width=4
        ).pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(
            main_frame, mode='determinate',
            style='Dark.Horizontal.TProgressbar'
        )
        self.progress.pack(fill=tk.X, pady=(0, 8))

        self.progress_label = tk.Label(
            main_frame, text="Ready",
            font=("Segoe UI", 9), bg=COLORS['bg'], fg=COLORS['fg_secondary']
        )
        self.progress_label.pack(pady=(0, 8))

        btn_frame = ttk.Frame(main_frame, style='Dark.TFrame')
        btn_frame.pack(fill=tk.X, pady=(0, 15))

        self.start_btn = tk.Button(
            btn_frame, text="Start Download",
            font=("Segoe UI", 12, "bold"),
            bg=COLORS['accent'], fg='#ffffff',
            activebackground=COLORS['accent_hover'],
            relief=tk.FLAT, bd=0, padx=30, pady=12, cursor="hand2",
            command=self.start_download
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame, text="Clear Cache",
            font=("Segoe UI", 10),
            bg=COLORS['input_bg'], fg=COLORS['fg'],
            activebackground=COLORS['border'],
            relief=tk.FLAT, bd=0, padx=15, pady=8, cursor="hand2",
            command=self.clear_cache
        ).pack(side=tk.LEFT)

        tk.Label(main_frame, text="Log:",
                font=("Segoe UI", 10), bg=COLORS['bg'], fg=COLORS['fg']).pack(anchor=tk.W)

        log_frame = tk.Frame(main_frame, bg=COLORS['border'], bd=0)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            log_frame, font=("Consolas", 9),
            bg=COLORS['input_bg'], fg=COLORS['fg'],
            relief=tk.FLAT, bd=8, state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        self.stats_label = tk.Label(
            main_frame, text="Cache: 0 | Downloaded: 0 | Skipped: 0 | Not found: 0",
            font=("Segoe UI", 9), bg=COLORS['bg'], fg=COLORS['fg_secondary']
        )
        self.stats_label.pack(pady=(10, 0))

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Dark.TFrame', background=COLORS['bg'])
        style.configure('Dark.Horizontal.TProgressbar',
                       background=COLORS['accent'],
                       troughcolor=COLORS['input_bg'],
                       bordercolor=COLORS['border'])

    def browse_directory(self):
        path = filedialog.askdirectory(title="Select music folder")
        if path:
            self.directory.set(path)
            self.dir_entry.config(fg=COLORS['fg'])

    def _on_entry_focus_in(self, event):
        if self.dir_entry.get() == "Enter folder path...":
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.config(fg=COLORS['fg'])

    def _on_entry_focus_out(self, event):
        if self.dir_entry.get() == "":
            self.dir_entry.insert(0, "Enter folder path...")
            self.dir_entry.config(fg=COLORS['fg_secondary'])

    def clear_cache(self):
        self.searcher.cache.cache.clear()
        self.searcher.cache.save()
        self.log("Cache cleared", COLORS['warning'])
        self.update_stats()

    def log(self, message: str, color: str = None):
        self.log_text.config(state=tk.NORMAL)
        if color:
            self.log_text.insert(tk.END, message + "\n", color)
            self.log_text.tag_config(color, foreground=color)
        else:
            self.log_text.insert(tk.END, message + "\n")

        line_count = int(self.log_text.index('end-1c').split('.')[0])
        if line_count > 50:
            self.log_text.delete(1.0, f"{line_count-49}.0")

        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def update_stats(self):
        cache_size = len(self.searcher.cache.cache)
        loaded = sum(1 for v in self.searcher.cache.cache.values() if v and v != '')
        not_found = sum(1 for v in self.searcher.cache.cache.values() if v == '')

        text = f"Cache: {cache_size} | Downloaded: {loaded} | Skipped: {self.results['skip']} | Not found: {not_found}"
        self.stats_label.config(text=text)

        if self.total_tracks > 0:
            progress = (self.processed_tracks / self.total_tracks) * 100
            self.progress['value'] = progress
            self.progress_label.config(
                text=f"{self.processed_tracks}/{self.total_tracks} ({progress:.0f}%)"
            )

    def get_track_info(self, file_path: Path) -> Tuple[str, str]:
        try:
            audio = MutagenFile(str(file_path))
            if audio:
                artist = audio.get('artist', [''])[0].strip() if audio.get('artist') else ''
                title = audio.get('title', [''])[0].strip() if audio.get('title') else ''
                if artist and title:
                    return artist, title
        except:
            pass

        stem = file_path.stem
        if ' - ' in stem:
            parts = stem.split(' - ', 1)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else stem

        return 'Unknown', stem

    def process_track(self, audio_path: Path) -> Tuple[bool, str]:
        lrc_path = audio_path.with_suffix('.lrc')

        artist, title = self.get_track_info(audio_path)
        lyrics = self.searcher.search(artist, title)

        if lyrics:
            lrc_path.write_text(lyrics, encoding='utf-8')
            self.results['ok'] += 1
            return True, f"{artist} - {title}"
        else:
            self.results['fail'] += 1
            return False, f"{artist} - {title}"

    def run_download(self):
        dir_path = Path(self.directory.get())
        if not dir_path.exists():
            self.log("Directory does not exist", COLORS['error'])
            self.finish_download()
            return

        SUPPORTED_FORMATS = ('.flac', '.mp3', '.opus', '.ogg', '.m4a', '.wav', '.aac', '.wma')
        audio_files = []
        for ext in SUPPORTED_FORMATS:
            audio_files.extend(dir_path.rglob(f'*{ext}'))

        if not audio_files:
            self.log("No audio files found", COLORS['error'])
            self.finish_download()
            return

        self.total_tracks = len(audio_files)
        self.processed_tracks = 0
        self.results = {'ok': 0, 'skip': 0, 'fail': 0}
        self.progress['value'] = 0

        self.log(f"Tracks: {self.total_tracks} | Threads: {self.threads_var.get()}")
        self.update_stats()

        max_workers = int(self.threads_var.get())

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.process_track, f): f for f in audio_files}

            for future in as_completed(futures):
                if not self.is_running:
                    break

                try:
                    success, msg = future.result(timeout=30)
                    self.processed_tracks += 1

                    if success and msg != "SKIP":
                        self.log(f"[OK] {msg}", COLORS['success'])
                    elif msg == "SKIP":
                        self.log(f"[SKIP] Skipped", COLORS['fg_secondary'])
                    else:
                        self.log(f"[FAIL] {msg}", COLORS['error'])

                    if self.processed_tracks % 10 == 0:
                        self.update_stats()
                        self.root.update()

                except Exception as e:
                    self.processed_tracks += 1
                    self.log(f"[ERROR] {e}", COLORS['warning'])

        self.log(f"Results: OK={self.results['ok']} | SKIP={self.results['skip']} | FAIL={self.results['fail']}")
        self.finish_download()

    def start_download(self):
        if not self.directory.get():
            messagebox.showwarning("Error", "Please select a folder!")
            return
        if self.is_running:
            return

        self.is_running = True
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        self.start_btn.config(text="Stop", bg=COLORS['error'], command=self.stop_download)

        thread = threading.Thread(target=self.run_download, daemon=True)
        thread.start()

    def stop_download(self):
        self.is_running = False
        self.log("Stopped", COLORS['warning'])
        self.finish_download()

    def finish_download(self):
        self.is_running = False
        self.start_btn.config(text="Start Download", bg=COLORS['accent'], command=self.start_download)
        self.update_stats()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = FastLRCApp()
    app.run()
