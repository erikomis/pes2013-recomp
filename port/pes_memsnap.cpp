/*
 * PES_MEMSNAP=<dir>: guest memory snapshots on request, for finding game state
 * (the score, the match clock) by comparing memory between known moments.
 *
 * A background thread looks for <dir>/req every 200 ms; when it is there it
 * writes guest 0x00000000-0x20000000 (main memory and the game's heap above it)
 * to <dir>/snap-<n>.bin and deletes req. Pages the guest never mapped are
 * written as zeros: write() reports EFAULT for them instead of faulting (on
 * Windows, VirtualQuery says which 64 KB chunks are committed). Off unless the
 * variable is set; nothing else in the port uses it.
 */
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <string>
#include <thread>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <io.h>
#else
#include <fcntl.h>
#include <unistd.h>
#endif

extern "C" uint8_t* vm_base;

namespace {

constexpr uint32_t kEnd = 0x20000000u;
constexpr uint32_t kChunk = 0x10000u;

#ifdef _WIN32
void snap(const std::string& path)
{
    FILE* f = fopen(path.c_str(), "wb");
    if (!f) return;
    static uint8_t zeros[kChunk];
    for (uint32_t a = 0; a < kEnd; a += kChunk) {
        MEMORY_BASIC_INFORMATION mbi;
        const bool live = vm_base && VirtualQuery(vm_base + a, &mbi, sizeof mbi) &&
                          mbi.State == MEM_COMMIT;
        if (fwrite(live ? vm_base + a : zeros, 1, kChunk, f) != kChunk) break;
    }
    fclose(f);
}
#else
void snap(const std::string& path)
{
    const int fd = open(path.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    static uint8_t zeros[kChunk];
    for (uint32_t a = 0; a < kEnd; a += kChunk) {
        ssize_t n = vm_base ? write(fd, vm_base + a, kChunk) : -1;
        if (n != (ssize_t)kChunk) {
            if (n > 0) lseek(fd, (off_t)a, SEEK_SET);
            if (write(fd, zeros, kChunk) != (ssize_t)kChunk) break;
        }
    }
    close(fd);
}
#endif

void* loop(void* arg)
{
    const std::string dir = static_cast<const char*>(arg);
    int n = 0;
    for (;;) {
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        const std::string req = dir + "/req";
        if (FILE* r = fopen(req.c_str(), "rb")) fclose(r);
        else continue;
        char name[64];
        snprintf(name, sizeof name, "/snap-%d.bin", ++n);
        snap(dir + name);
        remove(req.c_str());
        fprintf(stderr, "[memsnap] %s%s\n", dir.c_str(), name);
    }
    return nullptr;
}

struct Start {
    Start()
    {
        const char* d = getenv("PES_MEMSNAP");
        if (!d || !*d) return;
        std::thread(loop, (void*)d).detach();
    }
} s_start;

}  // namespace
