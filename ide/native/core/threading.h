#ifndef SOVEREIGN_THREADING_H
#define SOVEREIGN_THREADING_H

#include <windows.h>
#include <stdint.h>

typedef struct SovThread {
    HANDLE   handle;
    DWORD    id;
    void   (*entry)(void *);
    void    *arg;
} SovThread;

typedef struct SovMutex {
    SRWLOCK lock;
} SovMutex;

typedef struct SovCondVar {
    CONDITION_VARIABLE cv;
} SovCondVar;

static inline void sov_mutex_init(SovMutex *m)    { InitializeSRWLock(&m->lock); }
static inline void sov_mutex_lock(SovMutex *m)    { AcquireSRWLockExclusive(&m->lock); }
static inline void sov_mutex_unlock(SovMutex *m)  { ReleaseSRWLockExclusive(&m->lock); }

static inline void sov_condvar_init(SovCondVar *cv)              { InitializeConditionVariable(&cv->cv); }
static inline void sov_condvar_wait(SovCondVar *cv, SovMutex *m) { SleepConditionVariableSRW(&cv->cv, &m->lock, INFINITE, 0); }
static inline void sov_condvar_signal(SovCondVar *cv)            { WakeConditionVariable(&cv->cv); }
static inline void sov_condvar_broadcast(SovCondVar *cv)         { WakeAllConditionVariable(&cv->cv); }

#endif /* SOVEREIGN_THREADING_H */
