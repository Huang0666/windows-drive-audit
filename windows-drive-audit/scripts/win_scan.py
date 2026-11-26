"""Read-only Windows drive inventory using directory metadata."""

import ctypes as ct
from ctypes import wintypes as wt
import os
import shutil
import struct
import winreg


DIR = 0x10
REPARSE = 0x400
FIELDS = struct.Struct('<I4xqqqqqqII32xQ')
INVALID_HANDLE = ct.c_void_p(-1).value

kernel = ct.WinDLL('kernel32', use_last_error=True)
open_dir = kernel.CreateFileW
open_dir.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID, wt.DWORD, wt.DWORD, wt.HANDLE]
open_dir.restype = wt.HANDLE
query_dir = kernel.GetFileInformationByHandleEx
query_dir.argtypes = [wt.HANDLE, ct.c_int, wt.LPVOID, wt.DWORD]
query_dir.restype = wt.BOOL
close_dir = kernel.CloseHandle
close_dir.argtypes = [wt.HANDLE]
close_dir.restype = wt.BOOL
drive_type = kernel.GetDriveTypeW
drive_type.argtypes = [wt.LPCWSTR]
drive_type.restype = wt.UINT
get_volume = kernel.GetVolumeInformationW
get_volume.argtypes = [wt.LPCWSTR, wt.LPWSTR, wt.DWORD, ct.POINTER(wt.DWORD),
                       ct.POINTER(wt.DWORD), ct.POINTER(wt.DWORD), wt.LPWSTR, wt.DWORD]
get_volume.restype = wt.BOOL


def volume_format(root):
    if drive_type(root) not in (2, 3, 5, 6):
        raise ValueError('请选择已挂载的本地盘符。')
    filesystem = ct.create_unicode_buffer(64)
    if not get_volume(root, None, 0, None, None, None, filesystem, len(filesystem)):
        raise ct.WinError(ct.get_last_error())
    return filesystem.value


def ntfs_entries(path):
    # FILE_LIST_DIRECTORY, share read/write/delete, OPEN_EXISTING,
    # FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT.
    handle = open_dir('\\\\?\\' + path, 1, 7, None, 3, 0x02200000, None)
    if handle == INVALID_HANDLE:
        raise ct.WinError(ct.get_last_error())
    buffer = ct.create_string_buffer(65536)
    try:
        while query_dir(handle, 10, buffer, len(buffer)):
            start = 0
            while True:
                next_offset, _, _, _, _, _, allocated, attributes, name_length, identifier = FIELDS.unpack_from(buffer, start)
                first = start + FIELDS.size
                name = buffer[first:first + name_length].decode('utf-16-le', errors='surrogatepass')
                if name not in ('.', '..'):
                    yield name, max(0, allocated), attributes, identifier
                if not next_offset:
                    break
                start += next_offset
        error = ct.get_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES
            raise ct.WinError(error)
    finally:
        close_dir(handle)


def logical_entries(path):
    with os.scandir('\\\\?\\' + path) as items:
        for item in items:
            info = item.stat(follow_symlinks=False)
            yield item.name, info.st_size, info.st_file_attributes, 0


def scan(root, filesystem, stores=(), packages=(), progress=None):
    enumerate_entries = ntfs_entries if filesystem.upper() == 'NTFS' else logical_entries
    rows = []
    seen_ids = set()
    stack = [('', -1, False)]
    while stack:
        relative, parent, redirect = stack.pop()
        index = len(rows)
        # Path, parent, status, direct accounted, total accounted, raw by path,
        # visible files, partial reads, skipped links.
        row = [relative, parent, '已读取', 0, 0, 0, 0, 0, 0]
        rows.append(row)
        if redirect:
            row[2] = '链接或挂载点'
            row[8] = 1
            continue
        children = []
        try:
            for name, size, attributes, identifier in enumerate_entries(root + relative):
                path = f'{relative}\\{name}' if relative else name
                if attributes & DIR:
                    children.append((path, index, bool(attributes & REPARSE)))
                    continue
                row[5] += size
                row[6] += 1
                if not identifier or identifier not in seen_ids:
                    row[3] += size
                    if identifier:
                        seen_ids.add(identifier)
        except OSError as error:
            row[2] = f'无法完整读取（Win32 {getattr(error, "winerror", None) or error.errno}）'
            row[7] = 1
            if relative.casefold() in stores:
                listed = {child[0].casefold() for child in children}
                for package in packages:
                    if package.rpartition('\\')[0].casefold() != relative.casefold():
                        continue
                    full_path = root + package
                    if package.casefold() in listed:
                        continue
                    try:
                        attributes = os.lstat(full_path).st_file_attributes
                    except OSError:
                        continue
                    if attributes & DIR and not attributes & REPARSE:
                        children.append((package, index, False))
                        listed.add(package.casefold())
                if children:
                    row[2] = '受保护，已读取登记的应用子目录'
        if not relative:
            # Count shared component hard links under the regular program/system paths first.
            children.sort(key=lambda child: (child[0].casefold() == 'windows', child[0].casefold()))
        row[4] = row[3]
        stack.extend(reversed(children))
        if progress and index and index % 50000 == 0:
            progress(index)

    for row in reversed(rows[1:]):
        parent_row = rows[row[1]]
        for field in range(4, 9):
            parent_row[field] += row[field]
    return rows, shutil.disk_usage(root)


def installed_programs(root):
    result = {}
    subkey = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, subkey, access=winreg.KEY_READ | view) as parent:
                    for index in range(winreg.QueryInfoKey(parent)[0]):
                        try:
                            child = winreg.EnumKey(parent, index)
                            with winreg.OpenKey(parent, child) as key:
                                location = winreg.QueryValueEx(key, 'InstallLocation')[0]
                                name = winreg.QueryValueEx(key, 'DisplayName')[0]
                            if not isinstance(location, str) or not isinstance(name, str) or not name.strip():
                                continue
                            location = os.path.normpath(os.path.expandvars(location.strip().strip('"')))
                            rel = location[len(root):]
                            if location[:len(root)].casefold() == root.casefold() and rel:
                                result.setdefault(rel.casefold(), set()).add(name.strip())
                        except OSError:
                            pass
            except OSError:
                pass
    return {key: ' / '.join(sorted(names)) for key, names in result.items()}
