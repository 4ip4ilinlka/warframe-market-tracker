"""Read-only lookup of the game session (accountId + nonce) in Warframe's memory.

Safety rules (see docs/design.md):
* The process is opened with PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION only.
* Only VirtualQueryEx and ReadProcessMemory are used: no writes, no injection, no hooks.
* Found values are returned to the caller and never logged or stored.
"""
from __future__ import annotations

import ctypes
import re
import sys
from ctypes import wintypes

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ACCESS = PROCESS_VM_READ | PROCESS_QUERY_LIMITED_INFORMATION

MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_READWRITE = 0x04
CHUNK = 4 * 1024 * 1024
OVERLAP = 64
GAME_EXE = "Warframe.x64.exe"

PATTERN = re.compile(rb"accountId=([0-9a-f]{24})&nonce=(\d+)")


class GameNotRunning(Exception):
    pass


class CredentialsNotFound(Exception):
    pass


class GameAccessDenied(Exception):
    """Windows refused read access (e.g. the game runs as administrator)."""


ERROR_ACCESS_DENIED = 5
MAX_CANDIDATES = 2


def scan_all(buf: bytes) -> list[tuple[str, str]]:
    """Distinct (accountId, nonce) pairs, ordered by their last occurrence."""
    seen: dict[tuple[str, str], int] = {}
    for i, m in enumerate(PATTERN.finditer(buf)):
        seen.pop((m.group(1).decode(), m.group(2).decode()), None)
        seen[(m.group(1).decode(), m.group(2).decode())] = i
    return list(seen)


def scan_buffer(buf: bytes) -> tuple[str, str] | None:
    last = None
    for m in PATTERN.finditer(buf):
        last = m
    if last is None:
        return None
    return last.group(1).decode(), last.group(2).decode()


if sys.platform == "win32":
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    class MEMORY_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", wintypes.DWORD),
            ("PartitionId", wintypes.WORD),
            ("RegionSize", ctypes.c_size_t),
            ("State", wintypes.DWORD),
            ("Protect", wintypes.DWORD),
            ("Type", wintypes.DWORD),
        ]

    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.VirtualQueryEx.restype = ctypes.c_size_t
    _k32.VirtualQueryEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(MEMORY_BASIC_INFORMATION),
        ctypes.c_size_t,
    ]
    _k32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]


def find_pid(name: str = GAME_EXE) -> int | None:
    if sys.platform != "win32":
        return None
    TH32CS_SNAPPROCESS = 0x2
    snap = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return None
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = _k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == name.lower():
                return int(entry.th32ProcessID)
            ok = _k32.Process32NextW(snap, ctypes.byref(entry))
        return None
    finally:
        _k32.CloseHandle(snap)


def find_credentials(pid: int) -> list[tuple[str, str]]:
    """Session candidates, most recent first (at most MAX_CANDIDATES)."""
    if sys.platform != "win32":
        raise GameNotRunning()
    handle = _k32.OpenProcess(ACCESS, False, pid)
    if not handle:
        if ctypes.get_last_error() == ERROR_ACCESS_DENIED:
            raise GameAccessDenied()
        raise GameNotRunning()
    found: dict[tuple[str, str], None] = {}
    try:
        mbi = MEMORY_BASIC_INFORMATION()
        addr = 0
        buf = ctypes.create_string_buffer(CHUNK)
        read = ctypes.c_size_t()
        while _k32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            base = mbi.BaseAddress or 0
            size = mbi.RegionSize
            if mbi.State == MEM_COMMIT and mbi.Type == MEM_PRIVATE and mbi.Protect == PAGE_READWRITE:
                off = 0
                while off < size:
                    n = min(CHUNK, size - off)
                    if _k32.ReadProcessMemory(handle, ctypes.c_void_p(base + off), buf, n, ctypes.byref(read)):
                        for pair in scan_all(buf.raw[: read.value]):
                            found.pop(pair, None)
                            found[pair] = None
                    if n < CHUNK:
                        break
                    off += CHUNK - OVERLAP
            addr = base + size
            if addr >= 0x7FFFFFFFFFFF:
                break
    finally:
        _k32.CloseHandle(handle)
    if not found:
        raise CredentialsNotFound()
    return list(reversed(list(found)))[:MAX_CANDIDATES]
