"""Shared 256-color presentation for room names and descriptions only.

This is display-time formatting; builder area/room data is never changed.
Other UI, item, NPC and combat colors retain their existing behavior.
Existing embedded room-description color tags are still honored.
"""
ROOM_TITLE = "&[114]"          # jade green / #87d787
ROOM_DESCRIPTION = "&[253]"    # readable soft silver / #dadada


def color_room_name(name):
    return f"{ROOM_TITLE}{name}&x"


def color_room_description(description):
    return f"{ROOM_DESCRIPTION}{description}&x"
