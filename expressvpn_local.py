"""Locate the installed ExpressVPN controls without assuming an install path."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

_cached = None
_lock = threading.Lock()
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def running_clients():
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
             "@(Get-Process -Name expressvpn-client -ErrorAction SilentlyContinue | ForEach-Object { $_.Path }) | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=8, creationflags=NO_WINDOW)
        paths = json.loads(result.stdout or '[]')
        if isinstance(paths, str):
            paths = [paths]
        return [Path(path) for path in paths or [] if path]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def installed_directories():
    try:
        import winreg
    except ImportError:
        return
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, r'Software\Microsoft\Windows\CurrentVersion\Uninstall', 0, winreg.KEY_READ | view) as key:
                    for index in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            with winreg.OpenKey(key, winreg.EnumKey(key, index)) as app:
                                name = winreg.QueryValueEx(app, 'DisplayName')[0]
                                if 'expressvpn' in str(name).lower():
                                    location = winreg.QueryValueEx(app, 'InstallLocation')[0]
                                    if location:
                                        yield Path(location)
                        except OSError:
                            continue
            except OSError:
                continue


def drive_roots():
    if os.name != 'nt':
        return [Path.home()]
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [Path(f'{chr(65 + index)}:/') for index in range(26)
            if mask & (1 << index)
            and ctypes.windll.kernel32.GetDriveTypeW(f'{chr(65 + index)}:\\') in (2, 3)]


def search_tree(root):
    # Inaccessible directories are skipped. Avoid junctions that loop or leave a drive.
    for folder, directories, files in os.walk(root, followlinks=False):
        directories[:] = [name for name in directories
                          if not os.path.islink(os.path.join(folder, name))
                          and not getattr(os.path, 'isjunction', lambda path: False)(os.path.join(folder, name))]
        for filename in files:
            if filename.lower() == 'expressvpnctl.exe':
                candidate = Path(folder) / filename
                if candidate.is_file():
                    return candidate
    return None


def find_cli():
    global _cached
    with _lock:
        if _cached is not None and _cached.is_file():
            return _cached
        candidates = [path.parent / 'expressvpnctl.exe' for path in running_clients()]
        on_path = shutil.which('expressvpnctl.exe')
        if on_path:
            candidates.append(Path(on_path))
        candidates.extend(folder / 'expressvpnctl.exe' for folder in installed_directories())
        for variable in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
            base = os.environ.get(variable)
            if base:
                candidates.extend([Path(base) / 'ExpressVPN/expressvpnctl.exe',
                                   Path(base) / 'Programs/ExpressVPN/expressvpnctl.exe'])
        for candidate in candidates:
            if candidate.is_file():
                _cached = candidate
                return candidate
        # Prioritize likely portable/downloaded locations before scanning all local drives.
        roots = [Path.home() / name for name in ('Downloads', 'Desktop', 'Documents')]
        roots.extend(drive_roots())
        for root in roots:
            found = search_tree(root)
            if found:
                _cached = found
                return found
    raise RuntimeError('Could not find expressvpnctl.exe in accessible folders on local drives. Install ExpressVPN; an installer alone cannot connect the VPN.')


def ensure_client(cli):
    if running_clients():
        return
    client = cli.parent / 'expressvpn-client.exe'
    if not client.is_file():
        raise RuntimeError('Found ExpressVPN controls but its desktop app is missing. Repair or reinstall ExpressVPN.')
    subprocess.Popen([str(client)], creationflags=NO_WINDOW)
