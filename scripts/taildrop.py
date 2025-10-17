#!/bin/python3
import os
import platform

try:
    import grp
    import getpass
    ON_WIN = False
except ModuleNotFoundError:
    ON_WIN = True

import subprocess
import sys
from typing import Tuple

# multiplatform key handlers
if ON_WIN:
    import msvcrt

    def getkey():
        key = msvcrt.getch()
        if key == b'\xe0': # special key prefix
            key2 = msvcrt.getch()
            if key2 == b'H': return "UP"
            elif key2 == b'P': return "DOWN"
            else: return None
        elif key == b' ': return "SPACE"
        elif key == b'\r': return "ENTER"
        elif key == b'\x1b': return "ESC"
        elif key.lower() == b'a': return "ALL"
        elif key.lower() == b'n': return "NONE"
        else: return None

else: # linux / macosx
    import tty, termios

    def getkey():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b': # escape sequence
                seq = sys.stdin.read(2)
                if seq == '[A': return "UP"
                elif seq == '[B': return "DOWN"
                else: return "ESC"
            elif ch == ' ': return "SPACE"
            elif ch == '\r' or ch == '\n': return "ENTER"
            elif ch.lower() == 'a': return "ALL"
            elif ch.lower() == 'n': return "NONE"
            else: return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

class ec:
    NONE=0
    MISSING_PARAMETER=1
    INVALID_PARAMETER=2
    OPERATOR_SET_FAIL=3
    NON_OPERATOR_RECEIVE_FAIL=4
    RECEIVE_FAIL=5
    SEND_FAIL=6
    EMPTY_FILELIST=7
    NOTHING_SELECTED=8
    STATUS_FAIL=9

def print_error(code):
    if code == ec.NONE:
        return
    print(f"[{int(code)}] ", end="")
    if code == ec.MISSING_PARAMETER:
        print("Missing parameter!")
        print_usage()
    elif code == ec.INVALID_PARAMETER:
        print("Invalid parameter!")
        print_usage()
    elif code == ec.OPERATOR_SET_FAIL:
        print("Failed to set current user as operator!")
    elif code == ec.NON_OPERATOR_RECEIVE_FAIL:
        print("Failed to initate non-operator receive!")
    elif code == ec.RECEIVE_FAIL:
        print("Failed to receive!")
    elif code == ec.SEND_FAIL:
        print("Failed to send!")
    elif code == ec.EMPTY_FILELIST:
        print("No files selected!")
    elif code == ec.NOTHING_SELECTED:
        print("No device selected!")
    elif code == ec.STATUS_FAIL:
        print("Failed to get tailscale status!") 

def print_usage():
    print("Usage:")
    print(f"receive files in directory:  python3 {str(sys.argv[0])} -r <path to directory>")
    print(f"send files to target device: python3 {str(sys.argv[0])} -s <path to directory> [<target device name>]")

def cmd_run(cmd, bypass=False):
    r = True
    e = ''
    o = ''
    try:
        print(f"Trying to execute \'{' '.join(cmd)}\'")
        sp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        e = sp.stderr.decode("utf-8")
        if e != '':
            if not bypass:
                r = False
                print("Error:")
            # tailscale outputs to stderr
            print(e)

        o = sp.stdout.decode("utf-8")
        if o != '':
            print("Output:")
            print(o)
    except Exception:
        print(f"Exception occured during executing \'{' '.join(cmd)}\'")
        r = False    
    
    #todo: test this
    return r, o

def can_use_tailscale(on_windows) -> bool:
    if not on_windows:
        user = getpass.getuser()
        # current user is root
        if os.geteuid() == 0:
            return True
        # current user is in tailscale group
        try:
            groups = [g.gr_name for g in grp.getgrall() if user in g.gr_name]
            if "tailscale" in groups:
                return True
        except Exception:
            pass
        # current user can run a harmless tailscale command -> already an operator
    else:
        print("Hello windows!")
    try:
        subprocess.run(["tailscale", "status"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def show_choices(title, options, multiple=True) -> list:
    """
    Interactive choices menu.

    """
    selected = [False] * len(options)
    current = 0

    while True:
        os.system("cls" if ON_WIN else "clear")
        print(title)
        if multiple:
            nav_help = "move: ↑↓ | toggle: SPACE | all: a | none: n | confirm: ENTER | cancel: ESC "
        else:
            nav_help = "move: ↑↓ | select: ENTER | cancel: ESC "
        print("-" * len(nav_help))
        print(nav_help)
        print("-" * len(nav_help))

        # render
        for i, option in enumerate(options):
            prefix = "> " if i == current else "  "
            if multiple:
                checkbox = "[x]" if selected[i] else "[ ]"
                print(f"{prefix}{checkbox} {option}")
            else:
                print(f"{prefix}{option}")

        key = getkey()
        if key == "UP":
            current = (current - 1) % len(options)
        elif key == "DOWN":
            current = (current + 1) % len(options)
        elif multiple and key == "SPACE":
            selected[current] = not selected[current]
        elif multiple and key == "ALL":
            selected = [True] * len(options)
        elif multiple and key == "NONE":
            selected = [False] * len(options)
        elif key == "ESC":
            print("Cancelled selection!")
            return []
        elif key == "ENTER":
            if not multiple:
                selected[current] = not selected[current]
            break

    return [opt for opt, sel in zip(options, selected) if sel]

def select_device() -> str:
    cmd = ["tailscale", "status"]
    r, output = cmd_run(cmd)
    if not r or output == '':
        code = ec.STATUS_FAIL
    
    lines = output.strip().splitlines()
    devices = []
    for line in lines[1:]:  # skip header line
        parts = line.split()
        if len(parts) >= 2:
            hostname = parts[1]
            status_info = " ".join(parts[3:])
            # Simple filter: only include if "active" or "idle"
            if "active" in status_info or "idle" in status_info:
                devices.append(hostname)

    if not devices:
        print("No online devices found.")
        return []

    # Show selection window
    selected = show_choices("Select device", devices, multiple=False)
    return selected[0] + ":"

def main():
    code = ec.NONE

    if len(sys.argv) < 3:
        code = ec.MISSING_PARAMETER
    else:
        option = sys.argv[1]
        dir = sys.argv[2].replace('\\', '/')
        if str(option) not in ("-r", "-s"):
            code = ec.INVALID_PARAMETER
        # RECEIVE --------------------------------------------------
        elif option == "-r" and os.path.isdir(dir):
            if not can_use_tailscale(ON_WIN):
                print("Operators can use \'tailscale file get\' without sudo which this option use under the hood.")
                print("Choose no and every time the script executes \'tailscale file get\' it'll do it with sudo.")
                print(f"Set the current user \'{os.environ['USER']}\' as an operator?")
                yn = input("This step requires sudo. (Y/n)")
                if yn.lower() == "n":
                    cmd = ["sudo", "tailscale", "file", "get", dir]
                else:
                    cmd = ["sudo", "tailscale", "set", "--operator=$USER"]
                    if not cmd_run(cmd):
                        code = ec.OPERATOR_SET_FAIL
                
                if code != ec.OPERATOR_SET_FAIL:
                    print("Receiving...")
                    if not cmd_run(cmd):
                        code = ec.NON_OPERATOR_RECEIVE_FAIL
            else:
                cmd = ["tailscale", "file", "get", dir]
                print("Receiving...")
                if not cmd_run(cmd):
                    code = ec.RECEIVE_FAIL
                elif ON_WIN:
                    # on windows all files received into the user's Download/Tailscale directory
                    for root, _, filenames in os.walk(dir):
                        for f in filenames:
                            files.append(os.path.join(root,f))
                    selected_files = show_choices(f"Select files to copy to \'{dir}\'", files)
                    if selected_files == []:
                        code = ec.EMPTY_FILELIST

        # SEND --------------------------------------------------
        elif option == "-s" and os.path.isdir(dir):
            files = []
            for root, _, filenames in os.walk(dir):
                for f in filenames:
                    files.append(os.path.join(root,f).replace('\\', '/'))
            selected_files = show_choices("Select files", files)
            if selected_files == []:
                code = ec.EMPTY_FILELIST
            else:
                device = select_device()
                if device == "":
                    code = ec.NOTHING_SELECTED
                else:    
                    cmd = ["tailscale", "file", "cp", "--verbose"]
                    cmd.extend(selected_files)
                    cmd.append(device)
                    if not cmd_run(cmd, bypass=True):
                        code = ec.SEND_FAIL
    return code

if __name__ == "__main__":
    code = main()
    print_error(code)
    os.sys.exit(code)