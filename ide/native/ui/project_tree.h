#ifndef SOVEREIGN_PROJECT_TREE_H
#define SOVEREIGN_PROJECT_TREE_H

#include <windows.h>
#include <stdbool.h>
#include <stddef.h>
#include "../core/errors.h"

/* Opaque handle — full struct lives in project_tree.cpp (contains COM types) */
typedef struct ProjectTree ProjectTree;

SovResult project_tree_create(ProjectTree **out, HWND hwnd);
void      project_tree_destroy(ProjectTree *pt);
SovResult project_tree_open(ProjectTree *pt, const wchar_t *path);
void      project_tree_paint(ProjectTree *pt);
void      project_tree_resize(ProjectTree *pt, int w, int h);
void      project_tree_mouse_down(ProjectTree *pt, int x, int y);
void      project_tree_key_down(ProjectTree *pt, UINT vk);

/* Set the file-open callback (called from C shell code) */
void      project_tree_set_callback(ProjectTree *pt,
              void (*on_open)(const wchar_t *path, void *ctx), void *ctx);

#endif
