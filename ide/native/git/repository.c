/*
 * Sovereign IDE — Git repository helpers
 * Reads .git/HEAD and .git/index mtime for branch + dirty detection.
 * No libgit2 — pure Win32 file I/O.
 */

#include "repository.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* Walk up from path looking for a .git directory/file */
static bool find_git_root(const wchar_t *start, wchar_t *root_out, size_t root_cap) {
    wchar_t cur[MAX_PATH];
    wcscpy_s(cur, MAX_PATH, start);

    for (int depth = 0; depth < 32; depth++) {
        wchar_t candidate[MAX_PATH];
        swprintf_s(candidate, MAX_PATH, L"%s\\.git", cur);

        DWORD attr = GetFileAttributesW(candidate);
        if (attr != INVALID_FILE_ATTRIBUTES) {
            wcscpy_s(root_out, root_cap, cur);
            return true;
        }

        /* Go up one level */
        wchar_t *last = wcsrchr(cur, L'\\');
        if (!last || last == cur) break;
        *last = L'\0';
    }
    return false;
}

SovResult git_repo_open(GitRepo *repo, const wchar_t *path) {
    memset(repo, 0, sizeof(*repo));

    if (!find_git_root(path, repo->root, MAX_PATH))
        return SOV_ERR_IO;

    swprintf_s(repo->git_dir, MAX_PATH, L"%s\\.git", repo->root);
    repo->valid = true;
    return git_repo_refresh(repo);
}

SovResult git_repo_refresh(GitRepo *repo) {
    if (!repo->valid) return SOV_ERR_IO;

    /* Read HEAD → branch name */
    wchar_t head_path[MAX_PATH];
    swprintf_s(head_path, MAX_PATH, L"%s\\HEAD", repo->git_dir);

    HANDLE hf = CreateFileW(head_path, GENERIC_READ, FILE_SHARE_READ,
                            NULL, OPEN_EXISTING, 0, NULL);
    if (hf == INVALID_HANDLE_VALUE) return SOV_ERR_IO;

    char buf[256] = {0};
    DWORD nread = 0;
    ReadFile(hf, buf, sizeof(buf) - 1, &nread, NULL);
    CloseHandle(hf);

    /* "ref: refs/heads/main\n"  or  detached SHA */
    static const char prefix[] = "ref: refs/heads/";
    if (strncmp(buf, prefix, sizeof(prefix) - 1) == 0) {
        const char *branch = buf + sizeof(prefix) - 1;
        size_t len = strcspn(branch, "\r\n");
        if (len >= 128) len = 127;
        MultiByteToWideChar(CP_UTF8, 0, branch, (int)len,
                            repo->branch, 128);
        repo->branch[len] = L'\0';
        repo->detached = false;
    } else {
        /* Detached HEAD — show short SHA */
        size_t len = strcspn(buf, "\r\n");
        if (len > 8) len = 8;
        MultiByteToWideChar(CP_UTF8, 0, buf, (int)len,
                            repo->branch, 128);
        repo->branch[len] = L'\0';
        repo->detached = true;
    }

    /* Dirty detection: compare index mtime to HEAD mtime.
     * If index is newer → working tree likely has staged changes.
     * Good enough for status bar; not a full diff. */
    wchar_t index_path[MAX_PATH];
    swprintf_s(index_path, MAX_PATH, L"%s\\index", repo->git_dir);

    WIN32_FILE_ATTRIBUTE_DATA fa_index = {0}, fa_head = {0};
    bool has_index = GetFileAttributesExW(index_path, GetFileExInfoStandard, &fa_index);
    bool has_head  = GetFileAttributesExW(head_path,  GetFileExInfoStandard, &fa_head);

    if (has_index && has_head) {
        LONG cmp = CompareFileTime(&fa_index.ftLastWriteTime,
                                   &fa_head.ftLastWriteTime);
        repo->dirty = (cmp > 0);
    } else {
        repo->dirty = false;
    }

    return SOV_OK;
}
