#!/bin/python3
import os
import grp
import getpass
import subprocess
import sys
import tkinter as tk
from typing import Tuple

class ec:
    NONE=0
    MISSING_PARAMETER=1
    INVALID_PARAMETER=2
    OPERATOR_SET_FAIL=3
    NON_OPERATOR_RECEIVE_FAIL=4
    RECEIVE_FAIL=5
    EMPTY_FILELIST=6
    NOTHING_SELECTED=7
    STATUS_FAIL=8

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

def cmd_run(cmd):
    r = True
    e = ''
    o = ''
    try:
        print(f"Trying to execute \'{' '.join(cmd)}\'")
        sp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        e = sp.stderr.decode("utf-8")
        if e != '':
            print("Error:")
            print(e)
            r = False

        o = sp.stdout.decode("utf-8")
        if o != '':
            print("Output:")
            print(o)
    except Exception:
        print(f"Exception occured during executing \'{' '.join(cmd)}\'")
        r = False    
    
    #todo: test this
    return r, o

def can_use_tailscale() -> bool:
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
    try:
        subprocess.run(["tailscale", "status"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def show_checkboxes(title, options) -> list:
    root = tk.Tk()
    root.title(title)

    root.minsize(width=400, height=0)

    vars = []
    for opt in options:
        var = tk.BooleanVar()
        chk = tk.Checkbutton(root, text=opt, variable=var)
        chk.pack(anchor="w")
        vars.append((opt, var))

    selected = []

    def select_all():
        for _, var in vars:
            var.set(True)

    def clear_all():
        for _, var in vars:
            var.set(False)

    def submit():
        nonlocal selected
        selected = [opt for opt, var in vars if var.get()]
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=5)

    tk.Button(btn_frame, text="Select All", command=select_all).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Clear All", command=clear_all).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Apply selection", command=submit).pack(side="left", padx=5)

    root.mainloop()
    return selected

def show_radiobuttons(title, options) -> str:
    root = tk.Tk()
    root.title(title)

    root.minsize(width=400, height=0)

    selected_var = tk.StringVar(value="")

    for opt in options:
        rb = tk.Radiobutton(root, text=opt, variable=selected_var, value=opt)
        rb.pack(anchor="w")

    def submit():
        root.destroy()

    btn = tk.Button(root, text="Select", command=submit)
    btn.pack(pady=5)

    root.mainloop()
    return selected_var.get().strip() + ":"

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
    selected = show_radiobuttons("Select device", devices)
    return selected

def main():
    code = ec.NONE

    if len(sys.argv) < 3:
        code = ec.MISSING_PARAMETER
    else:
        option = sys.argv[1]
        dir = sys.argv[2]
        if str(option) not in ("-r", "-s"):
            code = ec.INVALID_PARAMETER
        # RECEIVE
        elif option == "-r" and os.path.isdir(dir):
            if not can_use_tailscale():
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
        # SEND
        elif option == "-s" and os.path.isdir(dir):
            print("Reading files ...")
            files = []
            for root, _, filenames in os.walk(dir):
                for f in filenames:
                    files.append(f)
            selected_files = show_checkboxes("Select files", files)
            if selected_files == []:
                code = ec.EMPTY_FILELIST
            else:
                formatted_filelist = ["'"+ file + "'" for file in selected_files]
                device = select_device()
                if device == "":
                    code = ec.NOTHING_SELECTED
                else:    
                    cmd = ["tailscale", "file", "cp", "--verbose"]
                    cmd.extend(formatted_filelist)
                    cmd.append(device)
                    print(" ".join(cmd))
    return code

if __name__ == "__main__":
    code = main()
    print_error(code)
    os.sys.exit(code)