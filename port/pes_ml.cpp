/*
 * Master League snapshot for PES 2013 (BLUS31029 1.04): never more than its 8000 slots.
 *
 * The Master League keeps a vector of 16-byte entries in its manager object
 * (begin at +0x64, end at +0x68; the manager is func_00EFC370 of the object at
 * *(0x01B5C628) + 0x70). A snapshot object holds a fixed array of 8000 of them
 * (0x1F40, from +0xC; func_017F7730 destroys it). func_0105117C copies the
 * vector into the array and func_01051214 copies the array back, both for as
 * many entries as the vector holds, with no bound.
 *
 * The 2026 profile without its Libertadores list makes 7880 entries when a Master
 * League is created in Latin America. With the list (38 clubs of the save, with
 * their squads, in place of the game's own Libertadores teams) it made 8355: the
 * copy wrote 355 entries past the array, over the heap, and the next
 * free of that object aborted the game (sys_process_exit(1)).
 *
 * Here both copies stop at 8000 entries, the array's size, so creating such a
 * Master League no longer corrupts the heap. That is a guard, not a fix: the
 * Master League save is laid out for 8000 too, and loading a save made with more
 * entries still fails. The profile keeps its world under the bound instead
 * (tools/fix_national_squads_2026.py: 7731 entries with the 2026 Libertadores).
 * Each copy is otherwise the lifted function's: same reads, same writes, the
 * same registers on return (r4 = the manager). PES_ML_LOG=1 logs the count each
 * time; a vector over the bound is logged once whatever the setting.
 */
#include "ppu_recomp.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>

extern "C" PPU_THREAD_LOCAL void (*g_trampoline_fn)(void*);

namespace {

constexpr uint32_t kSlots = 0x1F40;           /* 8000 */
constexpr uint32_t kEntry = 16;
constexpr uint32_t kArray = 0xC;              /* the array's offset in the snapshot */

/* The manager, as both lifted copies get it (with a frame of their own, as they do). */
uint32_t ml_manager(ppu_context* ctx, uint32_t ret)
{
    const uint64_t sp = ctx->gpr[1];
    vm_write64(sp - 0x80, sp);
    ctx->gpr[1] = sp - 0x80;
    ctx->gpr[3] = vm_read32(vm_read32(0x01B5C628) + 0x70);
    ctx->lr = ret;
    func_00EFC370(ctx);
    while (g_trampoline_fn) { void (*f)(void*) = g_trampoline_fn; g_trampoline_fn = 0; f(ctx); }
    ctx->gpr[1] = sp;
    return (uint32_t)ctx->gpr[3];
}

uint32_t clamp(const char* what, uint32_t begin, uint32_t end)
{
    const uint32_t n = end > begin ? (end - begin) / kEntry : 0;
    static int on = -1;
    if (on < 0) on = getenv("PES_ML_LOG") ? 1 : 0;
    static int warned;
    if (on || (n > kSlots && !warned)) {
        if (n > kSlots) warned = 1;
        fprintf(stderr, "[ml] snapshot %s: %u entries%s\n", what, n,
                n > kSlots ? " (over 8000: the rest stay out of the snapshot, and a Master League saved"
                                  " like this will not load)" : "");
    }
    return n > kSlots ? kSlots : n;
}

}  // namespace

/* Vector -> snapshot array. r3 = the snapshot. */
void func_0105117C(ppu_context* ctx)
{
    const uint64_t lr = ctx->lr;
    const uint32_t self = (uint32_t)ctx->gpr[3];
    const uint32_t mgr = ml_manager(ctx, 0x010511A0);
    const uint32_t begin = vm_read32(mgr + 0x64), end = vm_read32(mgr + 0x68);
    const uint32_t n = clamp("save", begin, end);
    for (uint32_t i = 0; i < n; i++)
        for (uint32_t w = 0; w < kEntry; w += 4)
            vm_write32(self + kArray + i * kEntry + w, vm_read32(begin + i * kEntry + w));
    ctx->gpr[3] = begin + n * kEntry;
    ctx->gpr[4] = mgr;
    ctx->lr = lr;
}

/* Snapshot array -> vector. r3 = the snapshot. */
void func_01051214(ppu_context* ctx)
{
    const uint64_t lr = ctx->lr;
    const uint32_t self = (uint32_t)ctx->gpr[3];
    const uint32_t mgr = ml_manager(ctx, 0x01051238);
    const uint32_t begin = vm_read32(mgr + 0x64), end = vm_read32(mgr + 0x68);
    const uint32_t n = clamp("restore", begin, end);
    for (uint32_t i = 0; i < n; i++)
        for (uint32_t w = 0; w < kEntry; w += 4)
            vm_write32(begin + i * kEntry + w, vm_read32(self + kArray + i * kEntry + w));
    ctx->gpr[3] = begin + n * kEntry;
    ctx->gpr[4] = mgr;
    ctx->lr = lr;
}
