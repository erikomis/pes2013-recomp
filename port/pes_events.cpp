/*
 * Match events for the DualSense: a goal and the whistle at the end of each half,
 * read from the game's own match state and passed to cellPad (ps3_pad_event),
 * which flashes the light bar, plays the goal through the controller's speaker
 * and vibrates.
 *
 * Where the state is (PES 2013 BLUS31029 01.04, static data of the executable,
 * found by comparing memory snapshots of a friendly at 0-0, 1-0 and 2-0):
 *   0x01BE3688  u16  home goals
 *   0x01BE368A  u16  away goals
 *   0x01BCB4C4  u32  match clock, 400 per game minute (18000 at 45:00, 36000 at 90:00)
 * A thread reads them ten times a second. A goal is one team's count going up by
 * one while a match is on; the whistle is the clock standing still for two
 * seconds after 45, 90, 105 or 120 minutes, once each per match.
 *
 * PES_EVENTS=0 turns it off. PES_EVENTS_LOG=1 logs every score change and clock
 * stop, to check the addresses against the picture.
 */
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <thread>

extern "C" uint8_t* vm_base;
extern "C" void ps3_pad_event(int kind);

namespace {

constexpr uint32_t kHome = 0x01BE3688u, kAway = 0x01BE368Au, kClock = 0x01BCB4C4u;
constexpr uint32_t kPerMinute = 400;
enum { kGoal = 1, kWhistle = 2 };

uint16_t rd16(uint32_t a) { return (uint16_t)(vm_base[a] << 8 | vm_base[a + 1]); }
uint32_t rd32(uint32_t a)
{
    return (uint32_t)vm_base[a] << 24 | (uint32_t)vm_base[a + 1] << 16 | (uint32_t)vm_base[a + 2] << 8 | vm_base[a + 3];
}

double now_s()
{
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

void* loop(void*)
{
    const bool log = getenv("PES_EVENTS_LOG") && atoi(getenv("PES_EVENTS_LOG"));
    static const uint32_t ends[] = {45 * kPerMinute, 90 * kPerMinute, 105 * kPerMinute, 120 * kPerMinute};
    uint16_t home = 0, away = 0;
    uint32_t clock = 0;
    double moved = now_s();
    bool live = false, stopped_logged = false;
    unsigned whistled = 0;   // bit per entry of ends[]
    while (!vm_base) std::this_thread::sleep_for(std::chrono::milliseconds(200));
    for (;;) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        const uint16_t h = rd16(kHome), a = rd16(kAway);
        const uint32_t c = rd32(kClock);
        const double t = now_s();
        if (c != clock) {
            if (c + 4 * kPerMinute < clock) {      // went back: another match
                whistled = 0;
                if (log) fprintf(stderr, "[pes-events] clock reset %u -> %u\n", clock, c);
            }
            live = c > 0;
            clock = c;
            moved = t;
            stopped_logged = false;
        } else if (live && t - moved > 2.0) {
            if (log && !stopped_logged) {
                fprintf(stderr, "[pes-events] clock stopped at %u (%u:%02u) score %u-%u\n", c, c / kPerMinute,
                        c % kPerMinute * 60 / kPerMinute, h, a);
                stopped_logged = true;
            }
            for (unsigned i = 0; i < 4; i++)
                if (c >= ends[i] && c < ends[i] + 15 * kPerMinute && !(whistled & (1u << i))) {
                    whistled |= 1u << i;
                    if (log) fprintf(stderr, "[pes-events] whistle at %u:%02u\n", c / kPerMinute, c % kPerMinute * 60 / kPerMinute);
                    ps3_pad_event(kWhistle);
                }
        }
        if (h != home || a != away) {
            const bool goal = live && ((h == home + 1 && a == away) || (a == away + 1 && h == home));
            if (log)
                fprintf(stderr, "[pes-events] score %u-%u -> %u-%u at %u:%02u%s\n", home, away, h, a, c / kPerMinute,
                        c % kPerMinute * 60 / kPerMinute, goal ? " goal" : "");
            if (goal) ps3_pad_event(kGoal);
            home = h;
            away = a;
        }
    }
    return nullptr;
}

struct Start {
    Start()
    {
        const char* e = getenv("PES_EVENTS");
        if (e && e[0] == '0') return;
        std::thread(loop, nullptr).detach();
    }
} s_start;

}  // namespace
