#ifndef SOVEREIGN_GIT_REPOSITORY_H
#define SOVEREIGN_GIT_REPOSITORY_H

#include <windows.h>
#include <stdbool.h>
#include "../core/errors.h"

typedef struct GitRepo {
    wchar_t root[MAX_PATH];
    wchar_t git_dir[MAX_PATH];
    wchar_t branch[128];
    bool    detached;
    bool    dirty;
    bool    valid;
} GitRepo;

SovResult git_repo_open(GitRepo *repo, const wchar_t *path);
SovResult git_repo_refresh(GitRepo *repo);

#endif
