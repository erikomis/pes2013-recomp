/*
 * PES_MEMSNAP=<dir>: guest memory snapshots on request, for finding game state
 * (the score, the match clock) by comparing memory between known moments.
 *
 * A background thread looks for <dir>/req every 200 ms; when it is there it
 * writes guest 0x00000000-0x20000000 (main memory and the game's heap above it)
 * to <dir>/snap-<n>.bin and deletes req. Pages the guest never mapped are
 * written as zeros: write() reports EFAULT for them instead of faulting. Off
 * unless the variable is set; nothing else in the port uses it.
 */
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <pthread.h>
#include <string>
#include <unistd.h>

extern "C" uint8_t* vm_base;

namespace {

constexpr uint32_t kEnd = 0x20000000u;
constexpr uint32_t kChunk = 0x10000u;

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

void* loop(void* arg)
{
    const std::string dir = static_cast<const char*>(arg);
    int n = 0;
    for (;;) {
        usleep(200000);
        const std::string req = dir + "/req";
        if (access(req.c_str(), F_OK) != 0) continue;
        char name[64];
        snprintf(name, sizeof name, "/snap-%d.bin", ++n);
        snap(dir + name);
        unlink(req.c_str());
        fprintf(stderr, "[memsnap] %s%s\n", dir.c_str(), name);
    }
    return nullptr;
}

struct Start {
    Start()
    {
        const char* d = getenv("PES_MEMSNAP");
        if (!d || !*d) return;
        pthread_t t;
        pthread_create(&t, nullptr, loop, (void*)d);
        pthread_detach(t);
    }
} s_start;

}  // namespace
