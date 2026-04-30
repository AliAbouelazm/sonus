import logging
import os
from typing import Any, Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from backend.app.config import settings

logger = logging.getLogger(__name__)

SCOPES = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "playlist-read-private "
    "playlist-read-collaborative"
)

TOKEN_CACHE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".spotify_cache"
)


class SpotifyIntegration:
    """Spotify playback control and search via spotipy + OAuth."""

    def __init__(self) -> None:
        self._sp: Optional[spotipy.Spotify] = None
        self._auth_manager: Optional[SpotifyOAuth] = None
        # Override credentials set from the UI (takes priority over .env)
        self._ui_client_id: str = ""
        self._ui_client_secret: str = ""

    def set_oauth_credentials(self, client_id: str, client_secret: str) -> None:
        """Override the OAuth credentials with values entered in the Sonus UI."""
        self._ui_client_id = client_id or ""
        self._ui_client_secret = client_secret or ""
        # Reset cached auth manager so next login uses new credentials
        self._auth_manager = None

    def _get_client_id(self) -> str:
        return self._ui_client_id or ""

    def _get_client_secret(self) -> str:
        return self._ui_client_secret or ""

    def _is_configured(self) -> bool:
        return bool(self._get_client_id() and self._get_client_secret())

    def _get_auth_manager(self) -> SpotifyOAuth:
        if self._auth_manager is None:
            self._auth_manager = SpotifyOAuth(
                client_id=self._get_client_id(),
                client_secret=self._get_client_secret(),
                redirect_uri=settings.spotify_redirect_uri,
                scope=SCOPES,
                cache_path=TOKEN_CACHE,
                open_browser=False,
            )
        return self._auth_manager

    def get_auth_url(self) -> str:
        if not self._is_configured():
            return ""
        return self._get_auth_manager().get_authorize_url()

    def handle_callback(self, code: str) -> bool:
        """Exchange the auth code for tokens. Returns True on success."""
        try:
            am = self._get_auth_manager()
            am.get_access_token(code, as_dict=False)
            self._sp = spotipy.Spotify(auth_manager=am)
            logger.info("Spotify authenticated successfully")
            return True
        except Exception as e:
            logger.error("Spotify auth callback failed: %s", e)
            return False

    def is_authenticated(self) -> bool:
        if not self._is_configured():
            return False
        try:
            am = self._get_auth_manager()
            token_info = am.cache_handler.get_cached_token()
            if token_info is None:
                return False
            if am.is_token_expired(token_info):
                token_info = am.refresh_access_token(token_info["refresh_token"])
            return token_info is not None
        except Exception:
            return False

    def _get_client(self) -> Optional[spotipy.Spotify]:
        if self._sp is not None:
            return self._sp
        if not self._is_configured():
            return None
        try:
            am = self._get_auth_manager()
            token_info = am.cache_handler.get_cached_token()
            if token_info is None:
                return None
            if am.is_token_expired(token_info):
                token_info = am.refresh_access_token(token_info["refresh_token"])
            self._sp = spotipy.Spotify(auth_manager=am)
            return self._sp
        except Exception as e:
            logger.error("Failed to create Spotify client: %s", e)
            return None

    def _not_ready(self) -> dict[str, str]:
        if not self._is_configured():
            return {"error": "Spotify not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env."}
        return {"error": "Spotify not authenticated. Visit /api/spotify/login to connect your account."}

    async def get_current_playback(self) -> Any:
        sp = self._get_client()
        if sp is None:
            return self._not_ready()
        try:
            pb = sp.current_playback()
            if pb is None:
                return {"status": "nothing_playing", "message": "Nothing is currently playing."}
            item = pb.get("item") or {}
            artists = ", ".join(a["name"] for a in item.get("artists", []))
            device = pb.get("device") or {}
            return {
                "status": "playing" if pb.get("is_playing") else "paused",
                "track": item.get("name", "Unknown"),
                "artist": artists,
                "album": item.get("album", {}).get("name", ""),
                "progress_ms": pb.get("progress_ms", 0),
                "duration_ms": item.get("duration_ms", 0),
                "volume": device.get("volume_percent"),
                "device": device.get("name", "Unknown"),
                "shuffle": pb.get("shuffle_state", False),
                "repeat": pb.get("repeat_state", "off"),
            }
        except spotipy.SpotifyException as e:
            logger.error("Spotify get_current_playback error: %s", e)
            return {"error": f"Spotify error: {e.msg}"}

    async def play(self, query: Optional[str] = None, uri: Optional[str] = None) -> Any:
        sp = self._get_client()
        if sp is None:
            return self._not_ready()
        try:
            if uri:
                if uri.startswith("spotify:track:"):
                    sp.start_playback(uris=[uri])
                else:
                    sp.start_playback(context_uri=uri)
                return {"status": "playing", "uri": uri}

            if query:
                results = sp.search(q=query, limit=1, type="track")
                tracks = results.get("tracks", {}).get("items", [])
                if not tracks:
                    return {"error": f"No tracks found for '{query}'."}
                track = tracks[0]
                sp.start_playback(uris=[track["uri"]])
                artists = ", ".join(a["name"] for a in track.get("artists", []))
                return {
                    "status": "playing",
                    "track": track["name"],
                    "artist": artists,
                    "uri": track["uri"],
                }

            sp.start_playback()
            return {"status": "resumed"}
        except spotipy.SpotifyException as e:
            if e.http_status == 404:
                return {"error": "No active Spotify device found. Open Spotify on a device first."}
            logger.error("Spotify play error: %s", e)
            return {"error": f"Spotify error: {e.msg}"}

    async def pause(self) -> Any:
        sp = self._get_client()
        if sp is None:
            return self._not_ready()
        try:
            sp.pause_playback()
            return {"status": "paused"}
        except spotipy.SpotifyException as e:
            logger.error("Spotify pause error: %s", e)
            return {"error": f"Spotify error: {e.msg}"}

    async def skip(self, direction: str = "next") -> Any:
        sp = self._get_client()
        if sp is None:
            return self._not_ready()
        try:
            if direction == "previous":
                sp.previous_track()
            else:
                sp.next_track()
            return {"status": f"skipped_{direction}"}
        except spotipy.SpotifyException as e:
            logger.error("Spotify skip error: %s", e)
            return {"error": f"Spotify error: {e.msg}"}

    async def set_volume(self, volume: int) -> Any:
        sp = self._get_client()
        if sp is None:
            return self._not_ready()
        try:
            volume = max(0, min(100, volume))
            sp.volume(volume)
            return {"status": "volume_set", "volume": volume}
        except spotipy.SpotifyException as e:
            logger.error("Spotify volume error: %s", e)
            return {"error": f"Spotify error: {e.msg}"}

    async def search(self, query: str, search_type: str = "track", limit: int = 5) -> Any:
        sp = self._get_client()
        if sp is None:
            return self._not_ready()
        try:
            valid_types = {"track", "album", "artist", "playlist"}
            if search_type not in valid_types:
                search_type = "track"
            results = sp.search(q=query, limit=limit, type=search_type)
            key = f"{search_type}s"
            items = results.get(key, {}).get("items", [])

            formatted = []
            for item in items:
                entry: dict[str, Any] = {"name": item["name"], "uri": item["uri"]}
                if search_type == "track":
                    entry["artist"] = ", ".join(a["name"] for a in item.get("artists", []))
                    entry["album"] = item.get("album", {}).get("name", "")
                elif search_type == "album":
                    entry["artist"] = ", ".join(a["name"] for a in item.get("artists", []))
                elif search_type == "playlist":
                    entry["owner"] = item.get("owner", {}).get("display_name", "")
                    entry["tracks"] = item.get("tracks", {}).get("total", 0)
                formatted.append(entry)

            return {"results": formatted, "type": search_type, "query": query}
        except spotipy.SpotifyException as e:
            logger.error("Spotify search error: %s", e)
            return {"error": f"Spotify error: {e.msg}"}

    async def play_playlist(self, query: str) -> Any:
        sp = self._get_client()
        if sp is None:
            return self._not_ready()
        try:
            results = sp.search(q=query, limit=1, type="playlist")
            playlists = results.get("playlists", {}).get("items", [])
            if not playlists:
                return {"error": f"No playlists found for '{query}'."}
            pl = playlists[0]
            sp.start_playback(context_uri=pl["uri"])
            return {
                "status": "playing",
                "playlist": pl["name"],
                "owner": pl.get("owner", {}).get("display_name", ""),
                "uri": pl["uri"],
            }
        except spotipy.SpotifyException as e:
            if e.http_status == 404:
                return {"error": "No active Spotify device found. Open Spotify on a device first."}
            logger.error("Spotify play_playlist error: %s", e)
            return {"error": f"Spotify error: {e.msg}"}

    async def shuffle(self, state: bool) -> Any:
        sp = self._get_client()
        if sp is None:
            return self._not_ready()
        try:
            sp.shuffle(state)
            return {"status": "shuffle_on" if state else "shuffle_off"}
        except spotipy.SpotifyException as e:
            logger.error("Spotify shuffle error: %s", e)
            return {"error": f"Spotify error: {e.msg}"}

    async def get_devices(self) -> Any:
        sp = self._get_client()
        if sp is None:
            return self._not_ready()
        try:
            devices = sp.devices()
            return [
                {
                    "id": d["id"],
                    "name": d["name"],
                    "type": d["type"],
                    "is_active": d["is_active"],
                    "volume": d.get("volume_percent"),
                }
                for d in devices.get("devices", [])
            ]
        except spotipy.SpotifyException as e:
            logger.error("Spotify devices error: %s", e)
            return {"error": f"Spotify error: {e.msg}"}

    async def transfer_playback(self, device_id: str) -> Any:
        sp = self._get_client()
        if sp is None:
            return self._not_ready()
        try:
            sp.transfer_playback(device_id, force_play=True)
            return {"status": "transferred", "device_id": device_id}
        except spotipy.SpotifyException as e:
            logger.error("Spotify transfer error: %s", e)
            return {"error": f"Spotify error: {e.msg}"}
