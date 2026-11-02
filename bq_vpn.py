"""Own the VPN lifetime for a dedicated B&Q browser window."""
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from expressvpn_local import find_cli, ensure_client

ROOT = Path(__file__).resolve().parent
_lock = threading.Lock()
_active = False
_ready = threading.Event()
_error = None
_browser = None


def vpn(*args):
    cli = find_cli()
    if args and args[0] == 'connect':
        ensure_client(cli)
        # Allow a newly opened desktop app to initialize before issuing the command.
        time.sleep(1)
    result = subprocess.run([str(cli), '--timeout', '20', *args],
                            capture_output=True, text=True, timeout=25,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('ExpressVPN could not complete the command. Check that it is signed in and running.')
    return result.stdout.strip()


def browser_executable():
    candidates = [
        Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe',
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError('Install Google Chrome or Microsoft Edge to open B&Q.')


def browser_command():
    return [str(browser_executable()),
            '--user-data-dir=' + str(ROOT / 'data' / 'bq-native-profile'),
            '--no-first-run', '--disable-background-mode', '--start-maximized', '--new-window',
            'https://www.diy.com/verified-sellers/seller/3038/products']


def open_bq():
    global _active, _error, _ready
    with _lock:
        if _active:
            if _browser is not None and _browser.poll() is None:
                # Chrome forwards this request to the existing dedicated profile.
                subprocess.Popen(browser_command())
                return {'message': 'B&Q opened in its dedicated Chrome window. Close its windows to turn off the VPN.'}
            return {'message': 'Connecting UK VPN. B&Q will open shortly.'}
        _active, _error = True, None
        _ready = threading.Event()
        ready = _ready
        threading.Thread(target=_session, args=(ready,), daemon=True, name='bq-vpn').start()
    if not ready.wait(55):
        raise RuntimeError('B&Q is still opening. Please wait before trying again.')
    if _error:
        raise RuntimeError(_error)
    return {'message': 'B&Q opened in Chrome. Close all its dedicated windows to turn off the VPN.'}


def _session(ready):
    global _active, _error, _browser
    attempted = False
    try:
        command = browser_command()
        attempted = True
        vpn('connect', 'uk-london')
        deadline = time.monotonic() + 25
        while vpn('get', 'connectionstate') != 'Connected':
            if time.monotonic() >= deadline:
                raise RuntimeError('ExpressVPN did not connect. Check the ExpressVPN app and retry.')
            time.sleep(.5)
        _browser = subprocess.Popen(command)
        # The dedicated profile keeps this process alive until its last window closes.
        time.sleep(1)
        if _browser.poll() is not None:
            raise RuntimeError('Chrome could not stay open (exit code %s). Close any old B&Q windows and try again.' % _browser.returncode)
        ready.set()
        _browser.wait()
    except Exception as error:
        _error = str(error)
        logging.exception('B&Q VPN session failed')
    finally:
        if attempted:
            try:
                vpn('disconnect')
            except Exception:
                logging.exception('Could not disconnect ExpressVPN after B&Q closed')
        with _lock:
            _active = False
            _browser = None
        ready.set()
