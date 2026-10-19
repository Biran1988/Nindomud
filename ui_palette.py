"""Shared 256-color presentation for room names and descriptions only.

This is display-time formatting; builder area/room data is never changed.
Other UI, item, NPC and combat colors retain their existing behavior.
Existing embedded room-description color tags are still honored.
"""
ROOM_TITLE = "&[208]"          # ember orange / #ff8700
ROOM_DESCRIPTION = "&[223]"    # warm sand / #ffd7af


def color_room_name(name):
    return f"{ROOM_TITLE}{name}&x"


def color_room_description(description):
    return f"{ROOM_DESCRIPTION}{description}&x"
