/*
 * League layout for PES 2013 (BLUS31029 1.04): Série B with 20 clubs.
 *
 * The EDIT save keeps every league's clubs in one table of 210 big-endian u16
 * team IDs, 0xFFFF for an empty slot. The game's code fixes each league's range of
 * it: func_00D4ECA8 gives the count and func_00D4ED6C the start, both a switch
 * over the league index. League 7 (Série B in the Brazil Option Files) gets 18
 * slots from slot 192; league 9 (other European clubs) gets 40 from slot 152, of
 * which those files use 24. The menus and the modes take each league's count from
 * a descriptor the game builds from its own data (func_00D7D200), so they show 18
 * whatever the table holds.
 *
 * Here the three are replaced (tools/weaken_lifted.py, port/lifted_overrides.txt).
 * A save whose slot 190 holds a club is read with Série B at 20 slots from slot 190
 * and the European league at 38; any other save, an ordinary Option File included,
 * is read exactly as the game reads it. tools/set_leagues.py --layout b20 writes
 * the 20-club layout.
 *
 * Each replacement mirrors the lifted function's register results: the count or
 * the pointer in r3 (and in r4/r5, where the original leaves it), nothing else.
 */
#include "ppu_recomp.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace {

constexpr uint32_t kSlots = 210;
constexpr uint32_t kEmpty = 0xFFFF;
constexpr uint32_t kB20Probe = 190;       /* first Série B slot in the 20-club layout */

struct Range { uint32_t start, count; };

/* League index -> range, as the game's two switches give it. */
constexpr Range kStock[10] = {
    {0, 20}, {20, 20}, {40, 20}, {60, 18}, {78, 20},
    {98, 16}, {134, 18}, {192, 18}, {114, 20}, {152, 40},
};

bool b20_layout(uint32_t table)
{
    return table && vm_read16(table + 2 * kB20Probe) != kEmpty;
}

Range league_range(uint32_t table, int32_t league)
{
    if (league < 0 || league > 9) return {0, 0};
    Range r = kStock[league];
    if (b20_layout(table)) {
        if (league == 7) r = {190, 20};
        if (league == 9) r = {152, 38};
    }
    return r;
}

/* Slots in use from the start of a league's range: the game's own lists end at
 * the first empty slot (func_00D4EFA8). */
uint32_t clubs_in(uint32_t table, Range r)
{
    uint32_t n = 0;
    while (n < r.count && r.start + n < kSlots &&
           vm_read16(table + 2 * (r.start + n)) != kEmpty)
        n++;
    return n;
}

/* A competition's clubs from the profile: $PS3_GAMEDATA_ROOT/pes13_competitions.txt,
 * lines "<competition> <team id> <team id> ...", '#' to the end of a line is a
 * comment. Only a list exactly as long as the game's replaces it, in place: the
 * competition's rounds and draw are laid out for that many clubs. */
struct CompList { int comp; uint32_t n; uint16_t ids[64]; };
CompList s_lists[8];
int s_nlists = -1;

void load_lists()
{
    s_nlists = 0;
    const char* root = getenv("PS3_GAMEDATA_ROOT");
    if (!root || !*root) return;
    char path[1024];
    snprintf(path, sizeof path, "%s/pes13_competitions.txt", root);
    FILE* f = fopen(path, "r");
    if (!f) return;
    char line[2048];
    while (s_nlists < 8 && fgets(line, sizeof line, f)) {
        if (char* h = strchr(line, '#')) *h = 0;
        char* p = line;
        char* end = nullptr;
        const long comp = strtol(p, &end, 10);
        if (end == p) continue;
        CompList& l = s_lists[s_nlists];
        l.comp = (int)comp;
        l.n = 0;
        p = end;
        for (;;) {
            const long id = strtol(p, &end, 10);
            if (end == p) break;
            if (id > 0 && id < 0xFFFF && l.n < 64) l.ids[l.n++] = (uint16_t)id;
            p = end;
        }
        if (l.n) s_nlists++;
    }
    fclose(f);
    fprintf(stderr, "[comp] %s: %d competition list(s)\n", path, s_nlists);
}

/* Write the profile's list for this competition over the game's, once per list. */
void apply_list(int comp, uint32_t desc)
{
    if (s_nlists < 0) load_lists();
    for (int i = 0; i < s_nlists; i++) {
        CompList& l = s_lists[i];
        if (l.comp != comp) continue;
        const uint32_t n = vm_read32(desc), list = vm_read32(desc + 4);
        if (!list) return;
        if (n != l.n) {
            static uint64_t warned;
            if (comp < 64 && !(warned & (1ull << comp))) {
                warned |= 1ull << comp;
                fprintf(stderr, "[comp] %d: the game has %u clubs, the profile lists %u; not replaced\n",
                        comp, n, l.n);
            }
            return;
        }
        bool same = true;
        for (uint32_t k = 0; k < n && same; k++) same = vm_read16(list + 2 * k) == l.ids[k];
        if (same) return;
        for (uint32_t k = 0; k < n; k++) vm_write16(list + 2 * k, l.ids[k]);
        fprintf(stderr, "[comp] %d: %u clubs from the profile\n", comp, n);
        return;
    }
}

}  // namespace

/* Team count of a league. r3 = team table, r4 = league; count in r3 and r4. */
void func_00D4ECA8(ppu_context* ctx)
{
    const Range r = league_range((uint32_t)ctx->gpr[3], (int32_t)ctx->gpr[4]);
    ctx->gpr[4] = r.count;
    ctx->gpr[3] = r.count;
}

/* Start of a league in the team table. r3 = team table, r4 = league; the
 * address of its first slot in r3 and r5, 0 for a league that does not exist. */
void func_00D4ED6C(ppu_context* ctx)
{
    const uint32_t table = (uint32_t)ctx->gpr[3];
    const int32_t league = (int32_t)ctx->gpr[4];
    const uint32_t at = (league < 0 || league > 9)
        ? 0u : (uint32_t)(table + 2 * league_range(table, league).start);
    ctx->gpr[5] = at;
    ctx->gpr[3] = at;
}

/* A competition's descriptor for the menus and modes: r3 = the competition data,
 * r4 = an 8-byte {count, team list} to fill, r5 = the competition. The lifted
 * function copies the game's descriptor, then, for the ten leagues and once the
 * EDIT data is loaded (the byte after the table), points the list at the league's
 * range of the EDIT table. The count is the game's own; for Série B in the 20-club
 * layout it becomes the clubs actually there. */
void func_00D7D200(ppu_context* ctx)
{
    const uint32_t base = (uint32_t)ctx->gpr[3];
    const uint32_t out = (uint32_t)ctx->gpr[4];
    const int32_t comp = (int32_t)ctx->gpr[5];
    const uint32_t desc = (uint32_t)(base + ((uint64_t)(int64_t)comp << 3) + 40);
    apply_list(comp, desc);
    vm_write32(out, vm_read32(desc));
    vm_write32(out + 4, vm_read32(desc + 4));
    /* PES_COMP_LOG=1: each competition asked for, once: its number, the game's
     * count and its first team IDs. */
    { static int on = -1; static uint64_t seen;
      if (on < 0) on = getenv("PES_COMP_LOG") ? 1 : 0;
      if (on && comp >= 0 && comp < 64 && !(seen & (1ull << comp))) {
          seen |= 1ull << comp;
          const uint32_t n = vm_read32(desc), list = vm_read32(desc + 4);
          fprintf(stderr, "[comp] %d: %u teams at 0x%08X:", comp, n, list);
          for (uint32_t i = 0; list && i < n && i < 8; i++) fprintf(stderr, " %u", vm_read16(list + 2 * i));
          fprintf(stderr, "\n");
      } }
    if (!vm_read32(out)) return;
    const uint32_t table = vm_read32(base + 336);
    if (!table || !vm_read8(table + 2 * kSlots)) return;
    int32_t league;
    switch (comp) {
    case 7: league = 0; break;
    case 8: league = 1; break;
    case 9: league = 2; break;
    case 10: league = 3; break;
    case 11: league = 4; break;
    case 12: league = 5; break;
    case 13: league = 8; break;
    case 14: league = 6; break;
    case 15: league = 7; break;
    case 16: league = 9; break;
    default: return;
    }
    const Range r = league_range(table, league);
    const uint32_t at = table + 2 * r.start;
    vm_write32(out + 4, at);
    if (league == 7 && b20_layout(table)) vm_write32(out, clubs_in(table, r));
    ctx->gpr[3] = at;
}
