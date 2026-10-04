# 홍익학당 · 내용 검색

A static website where viewers search **what is said inside** the channel's videos, then jump straight to that moment in an embedded player.

- Transcripts come only from **public** sources. No channel-owner login is needed.
- The index uses only original Korean captions. Auto-translated tracks and misdetected-language ASR are ignored, and titles are fetched in Korean.
- The 유형 filter has the channel's live shows (양심톡톡 Live · 정토 LIVE · 홍익학당 Live · 양덕 LIVE · 특집·기타) plus video types taken from the `[…]` title prefix, or from `title_rules` for titles without one.
- Cosmic theme: a live starfield (`site/sky.js`, star clusters, twinkling, shooting stars; static when the visitor prefers reduced motion) behind glass panels.
- The site is static (HTML + [Pagefind](https://pagefind.app)), so hosting is free and there's no server.

## Update the data

Requires Python 3.10+ and Node 18+ (for `npx pagefind`).

```powershell
.\update.ps1              # everything still pending (resumable; Ctrl+C is safe)
.\update.ps1 -Limit 300   # at most 300 videos this run
```

Or run the steps individually from `ingest/`:

| Step | Command | Output |
|---|---|---|
| 1. Video list | `python fetch_videos.py` | `data/videos.json` (title, date, length, live/video type) |
| 2. Transcripts | `python fetch_captions.py [--limit N] [--retry none]` | `data/transcripts/<id>.json`, `data/state.json` |
| 3. Pages | `python build_pages.py` | `site/video/<id>.html`, `site/stats.json` |
| 4. Search index | delete `site/pagefind/`, then `npx -y pagefind@1.3.0 --site site` (from the project root) | `site/pagefind/` |

> **Keep Pagefind pinned to 1.3.0.** Versions 1.4 and later decompose Hangul for diacritic matching and put every Korean word into one ~25 MB index file, which makes some searches take 15+ seconds. On 1.3.0 the largest file is about 0.4 MB.

### Transcript sources and statuses
`fetch_captions.py` tries **youtube-transcript-api** first, then **yt-dlp**. Each video's result is recorded in `data/state.json`:

| Status | Meaning | Retried automatically |
|---|---|---|
| `done` | Transcript saved | – |
| `none` | No Korean caption (captions disabled, scenery clips, etc.) | `--retry none` |
| `members` | Members-only video | No |
| `unavailable` | Private, deleted or age-restricted | `--retry unavailable` |
| `error` | Temporary error | Yes, on the next run |

- **Throttling:** 1.5–3.5 seconds between videos. If YouTube starts blocking, the script waits 1, 2, 4 and then 8 minutes, then stops cleanly. Re-running it continues from where it stopped.
- The full channel (~5,800 videos) takes several hours in total. Running it in chunks of a few hundred to a thousand is safer.
- **Videos without captions:** run `pip install faster-whisper` and then `python fetch_captions.py --whisper`. This transcribes them locally. It's slow on a CPU.
- **Upload dates:** without an API key, dates are collected during the transcript step. With a YouTube Data API v3 key in `config.json` → `api_key` (or the `YOUTUBE_API_KEY` environment variable), step 1 gets every date at once.

### Adjusting the types (config.json → `types`)
- `fixes`: variant spellings mapped to one series (e.g. `윤홍식의3분인문학` → `3분 인문학`); spacing and case are ignored when grouping
- `title_rules`: `[regex, type]` pairs for titles without a `[prefix]` (e.g. `^윤홍식의\s*철학\s*힐링` → `철학힐링`)
- `live_shows`: prefixes shown as their own live category
- `min_count`: video types with fewer videos than this are merged into a group
- `groups`: rules for merging small types into a group (a type goes into the group whose keywords its name contains, otherwise into `기타`)

Re-run `fetch_videos.py` → `build_pages.py` → pagefind after changing these.

## Preview locally
```powershell
python -m http.server 8765 --directory site
```
Open http://localhost:8765. (Opening the file directly with `file://` won't work, because the search index won't load.)

## Deploy (Cloudflare Pages)
1. Run `npx wrangler pages deploy site --project-name hihd-search`, or
2. connect a Git repository in the Cloudflare dashboard with no build command and `site` as the output directory. In that case, commit `site/pagefind/` too, or add `npx -y pagefind@1.3.0 --site site` as the build command.

GitHub Pages also works; publish the `site` folder as-is. All paths are relative.

## Structure
```
config.json          channel, language, type rules
ingest/              data collection and page generation (Python)
data/                video list, transcript originals, progress state
site/index.html      search page      site/app.js   search + player
site/style.css       styles (light/dark)  site/video/  per-video transcript pages (generated)
```
