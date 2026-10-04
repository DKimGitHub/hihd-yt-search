"""Step 1: list every public video on the channel into data/videos.json.

Uses the YouTube Data API when an API key is configured (fast, includes
upload dates). Otherwise uses yt-dlp's flat channel listing; upload dates
are then filled in per video by fetch_captions.py.
"""
import re
import urllib.parse

from common import VIDEOS_FILE, load_config, load_json, save_json, ytdlp_opts

SERIES_RE = re.compile(r"^\s*\[([^\]]+)\]")
LIVE_PREFIX = "라이브 · "


def _key(name):
    """Grouping key: spacing and case never split a series ('3분 인문학' == '3분인문학')."""
    return re.sub(r"\s+", "", name).lower()


def raw_type(title, cfg):
    """Return (key, display name) of a video's series.

    '[3분 인문학] ...' -> ('3분인문학', '3분 인문학'). Known variants are mapped via
    types.fixes; titles without a [prefix] are matched against types.title_rules.
    """
    tc = cfg["types"]
    m = SERIES_RE.match(title or "")
    if not m:
        for pattern, name in tc.get("title_rules", []):
            if re.search(pattern, title or ""):
                return _key(name), name
        return "기타", "기타"
    display = re.sub(r"\s+", " ", re.sub(tc["strip_prefix"], "", m.group(1))).strip()
    fixes = {_key(k): v for k, v in tc["fixes"].items()}
    display = fixes.get(_key(display), display)
    return (_key(display), display) if display else ("기타", "기타")


def assign_types(videos, cfg):
    """Set v["type"], the value of the 유형 search filter.

    Live streams: '라이브 · <name>' for the configured live shows, else a shared bucket.
    Videos: own name when common enough, otherwise a keyword-based group.
    A series is shown with its most common spelling.
    """
    tc = cfg["types"]
    live_shows = {_key(s) for s in tc["live_shows"]}
    counts, spellings = {}, {}
    for v in videos:
        key, display = v["_raw"] = raw_type(v["title"], cfg)
        spellings.setdefault(key, {}).setdefault(display, 0)
        spellings[key][display] += 1
        if not v.get("live"):
            counts[key] = counts.get(key, 0) + 1
    name_of = {k: max(s, key=s.get) for k, s in spellings.items()}
    for v in videos:
        key, _ = v.pop("_raw")
        name = name_of[key]
        if v.get("live"):
            v["type"] = LIVE_PREFIX + (name if key in live_shows else tc["live_other"])
        elif counts[key] >= tc["min_count"]:
            v["type"] = name
        else:
            v["type"] = next((group for group, words in tc["groups"].items()
                              if any(w in key for w in words)), "기타")


def parse_iso_duration(s):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + se


def channel_base_url(channel):
    channel = channel.strip()
    if re.fullmatch(r"UC[\w-]{22}", channel):
        return f"https://www.youtube.com/channel/{channel}"
    if channel.startswith("@"):
        return "https://www.youtube.com/" + urllib.parse.quote(channel)
    parts = urllib.parse.urlsplit(channel)
    path = urllib.parse.quote(urllib.parse.unquote(parts.path.rstrip("/")))
    path = re.sub(r"/(videos|streams|shorts|featured)$", "", path)
    return f"https://www.youtube.com{path}"


# ---------------------------------------------------------------- API path

def list_with_api(cfg):
    from googleapiclient.discovery import build

    yt = build("youtube", "v3", developerKey=cfg["api_key"], cache_discovery=False)
    channel = cfg["channel"]
    handle = re.search(r"@([^/?#]+)", urllib.parse.unquote(channel))
    cid = re.search(r"(UC[\w-]{22})", channel)
    req = (yt.channels().list(part="contentDetails", id=cid.group(1)) if cid
           else yt.channels().list(part="contentDetails", forHandle="@" + handle.group(1)))
    items = req.execute().get("items") or []
    if not items:
        raise SystemExit(f"Channel not found: {channel}")
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    ids, token = [], None
    while True:
        resp = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                       maxResults=50, pageToken=token).execute()
        ids += [it["contentDetails"]["videoId"] for it in resp["items"]]
        token = resp.get("nextPageToken")
        print(f"  listed {len(ids)} uploads", end="\r")
        if not token:
            break
    print()

    videos = []
    for i in range(0, len(ids), 50):
        resp = yt.videos().list(part="snippet,contentDetails,statistics,liveStreamingDetails", hl="ko",
                                id=",".join(ids[i:i + 50])).execute()
        for v in resp["items"]:
            sn = v["snippet"]
            if sn.get("liveBroadcastContent") in ("live", "upcoming"):
                continue
            videos.append({
                "id": v["id"],
                "title": (sn.get("localized") or {}).get("title") or sn["title"],
                "published": sn["publishedAt"][:10],
                "duration": parse_iso_duration(v["contentDetails"].get("duration")),
                "views": int(v.get("statistics", {}).get("viewCount", 0)),
                "live": "liveStreamingDetails" in v,
            })
    return videos


# ------------------------------------------------------------- yt-dlp path

def list_with_ytdlp(cfg):
    import yt_dlp

    base = channel_base_url(cfg["channel"])
    videos, seen = [], set()
    with yt_dlp.YoutubeDL(ytdlp_opts(extract_flat="in_playlist", ignoreerrors=True)) as ydl:
        for tab in ("videos", "streams"):
            info = ydl.extract_info(f"{base}/{tab}", download=False)
            for e in (info or {}).get("entries") or []:
                if not e or e["id"] in seen:
                    continue
                seen.add(e["id"])
                videos.append({
                    "id": e["id"],
                    "title": e.get("title") or "",
                    "published": None,
                    "duration": e.get("duration"),
                    "views": e.get("view_count"),
                    "live": tab == "streams",
                })
            print(f"  {tab}: {len(videos)} total")
    return videos


def main():
    cfg = load_config()
    print("Listing videos via", "YouTube Data API" if cfg["api_key"] else "yt-dlp")
    fresh = list_with_api(cfg) if cfg["api_key"] else list_with_ytdlp(cfg)

    # Keep dates learned on earlier runs (the yt-dlp listing has none).
    old = {v["id"]: v for v in load_json(VIDEOS_FILE, [])}
    for v in fresh:
        if not v["published"] and old.get(v["id"], {}).get("published"):
            v["published"] = old[v["id"]]["published"]
    assign_types(fresh, cfg)

    save_json(VIDEOS_FILE, fresh)
    new = sum(1 for v in fresh if v["id"] not in old)
    print(f"Saved {len(fresh)} videos ({new} new) to {VIDEOS_FILE.relative_to(VIDEOS_FILE.parents[1])}")
    types = {}
    for v in fresh:
        types[v["type"]] = types.get(v["type"], 0) + 1
    print(f"{len(types)} types:", ", ".join(f"{k} {n}" for k, n in sorted(types.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()
