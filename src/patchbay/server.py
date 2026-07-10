"""patchbay MCP server — exposes Spotify library tools to Claude Desktop over stdio.

The tools are deliberately thin wrappers around the Spotify client. The
judgement about *which* song belongs in *which* occasion playlist happens in the
conversation with Claude, and you approve each write in Claude Desktop.
"""

from mcp.server.fastmcp import FastMCP

from .client import Spotify

mcp = FastMCP("patchbay")
sp = Spotify()


# --- reads -----------------------------------------------------------------
@mcp.tool()
def get_liked_songs(limit: int = 200, offset: int = 0) -> dict:
    """Read the current user's Liked Songs (most recently added first).

    Paginates internally in pages of 50; `limit` caps the total (max 1000).
    Use `offset` to continue through a large library. Returns
    {total, count, offset, items:[{id, uri, name, artists, album, isrc, release_year}]}.
    """
    return sp.get_liked_songs(limit, offset)


@mcp.tool()
def get_playlists(limit: int = 50, offset: int = 0) -> dict:
    """List the current user's playlists (owned and followed).

    Returns {total, count, items:[{id, name, owner, tracks_total, public,
    collaborative}]}. Use a playlist `id` with the other playlist tools.
    """
    return sp.get_playlists(limit, offset)


@mcp.tool()
def get_playlist_tracks(playlist_id: str, limit: int = 300, offset: int = 0) -> dict:
    """Read tracks in a playlist you own or collaborate on (pages of 100, max 1000).

    Returns {total, count, offset, items:[{id, uri, name, artists, album, isrc, release_year}]}.
    Use `offset` to continue past the first `limit`. For playlists you don't
    own/collaborate on, Spotify returns metadata only and this may be empty.
    """
    return sp.get_playlist_tracks(playlist_id, limit, offset)


@mcp.tool()
def search_tracks(query: str, limit: int = 10) -> dict:
    """Search Spotify's catalog for tracks. Returns {count, items:[...]}. """
    return sp.search_tracks(query, limit)


# --- writes ----------------------------------------------------------------
@mcp.tool()
def create_playlist(name: str, description: str = "", public: bool = False) -> dict:
    """Create a new playlist owned by the current user (private by default).

    Returns {id, name, url, owner}. Use the id with add_tracks.
    """
    return sp.create_playlist(name, description, public)


@mcp.tool()
def add_tracks(playlist_id: str, track_uris: list[str]) -> dict:
    """Add tracks by Spotify URI (e.g. 'spotify:track:...') to a playlist.

    Batches of 100. Returns {added}.
    """
    return sp.add_tracks(playlist_id, track_uris)


@mcp.tool()
def remove_tracks(playlist_id: str, track_uris: list[str]) -> dict:
    """Remove tracks by URI from a playlist you own/collaborate on.

    Batches of 100. Returns {removed}.
    """
    return sp.remove_tracks(playlist_id, track_uris)


@mcp.tool()
def delete_playlist(playlist_id: str) -> dict:
    """Delete a playlist you own (Spotify models this as unfollowing your own playlist).

    Returns {deleted: playlist_id}. Irreversible from patchbay's side, though
    the Spotify web UI still lets you recover recently unfollowed playlists.
    """
    return sp.delete_playlist(playlist_id)


@mcp.tool()
def remove_liked_songs(track_ids: list[str]) -> dict:
    """Remove tracks from Liked Songs, by track ID (not URI). Batches of 50.

    Returns {removed}. Do this only after the songs are safely in a playlist.
    """
    return sp.remove_liked_songs(track_ids)


def main() -> None:
    mcp.run()  # stdio transport, as Claude Desktop expects


if __name__ == "__main__":
    main()
