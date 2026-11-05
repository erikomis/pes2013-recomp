#!/usr/bin/env python3
"""Read the locally verified BLUS31029 1.04 EEDIT layout. No save writer.

Unknown regions, player attributes and league structures are not decoded.
Exports contain game-derived data: keep output in analysis/, never commit it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

SIZE = 7905992
PLAYER_TABLE = 0x20
PLAYER_STRIDE = 228
PLAYER_COUNT = 12000
CREATED_TABLE = 0x516C4C
CREATED_COUNT = 160
TEAM_TABLE = 0x29BFA0
TEAM_STRIDE = 1460
# 417 populated team-name slots observed in this particular Option File.
TEAM_COUNT = 417
ROSTER_TABLE = 0x383B48
ROSTER_STRIDE = 164
ROSTER_COUNT = 340


def crc32(data):
    checksum = zlib.crc32(data[:8])
    checksum = zlib.crc32(bytes(4), checksum)
    return zlib.crc32(data[12:], checksum)


def read_text(data, offset, size):
    raw = data[offset:offset + size]
    if len(raw) != size or b"\0" not in raw:
        raise ValueError(f"Invalid text field at 0x{offset:X}")
    return raw.split(b"\0", 1)[0].decode("utf-8")


def decode(data):
    if len(data) != SIZE or data[:4] != bytes.fromhex("01000601"):
        raise ValueError("Unsupported EEDIT size/version; only the inspected local layout is supported")
    stored = struct.unpack_from(">I", data, 8)[0]
    if stored != crc32(data):
        raise ValueError("EEDIT CRC32 mismatch")
    players = {}
    for base, count, kind in ((PLAYER_TABLE, PLAYER_COUNT, "base"),
                              (CREATED_TABLE, CREATED_COUNT, "created")):
        for slot in range(count):
            offset = base + slot * PLAYER_STRIDE
            player_id = struct.unpack_from(">I", data, offset)[0]
            if player_id == 0xFFFFFFFF:
                continue
            if player_id in players:
                raise ValueError(f"Duplicate player ID {player_id}")
            players[player_id] = dict(id=player_id, kind=kind, slot=slot,
                                      offset=offset, name=read_text(data, offset + 50, 46),
                                      shirt_name=read_text(data, offset + 96, 18))
    teams = []
    for slot in range(TEAM_COUNT):
        offset = TEAM_TABLE + slot * TEAM_STRIDE
        team_id = struct.unpack_from(">H", data, offset + 1456)[0]
        teams.append(dict(id=team_id, base_id=struct.unpack_from(">H", data, offset + 1444)[0],
                          slot=slot, offset=offset, name=read_text(data, offset, 72)))
    rosters = {}
    for slot in range(ROSTER_COUNT):
        offset = ROSTER_TABLE + slot * ROSTER_STRIDE
        team_id = struct.unpack_from(">H", data, offset)[0]
        if team_id in rosters or team_id == 0xFFFF:
            raise ValueError(f"Unexpected roster ID at 0x{offset:X}")
        members = []
        for index, player_id in enumerate(struct.unpack_from(">32I", data, offset + 4)):
            if player_id == 0:
                continue
            if player_id not in players:
                raise ValueError(f"Unresolved player ID {player_id} in team {team_id}")
            members.append(dict(player_id=player_id, name=players[player_id]["name"],
                                slot=index, shirt_number=data[offset + 132 + index]))
        rosters[team_id] = dict(team_id=team_id, offset=offset, members=members)
    for team in teams:
        # Continental variants have distinct IDs. Do not silently substitute a
        # domestic squad: those tables have not been mapped yet.
        team["roster"] = rosters.get(team["id"])
    return dict(layout="BLUS31029-1.04-local-OF-observed", schema_complete=False,
                sha256=hashlib.sha256(data).hexdigest(), crc32=f"{stored:08x}",
                players=list(players.values()), teams=teams,
                rosters=list(rosters.values()),
                limitations=["Continental squad tables not mapped",
                             "Attributes and league slots not decoded",
                             "No modification or in-game round-trip validation"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    args = parser.parse_args()
    try:
        result = decode(args.data.read_bytes())
    except (ValueError, OSError, UnicodeDecodeError, struct.error) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
