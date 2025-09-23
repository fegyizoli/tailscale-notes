#!/bin/python3
import os
import grp
import getpass
import subprocess
import sys

class ec:
    NONE=0
    MISSING_OPTION=1
    INVALID_OPTION=2
    OPERATOR_SET_FAIL=3
    NON_OPERATOR_RECEIVE_FAIL=4
    RECEIVE_FAIL=5

def print_error(code):
    if code == ec.NONE:
        return
    print(f"[{int(code)}] ", end="")
    if code == ec.MISSING_OPTION:
        print("Missing option!")
        print_usage()
    elif code == ec.INVALID_OPTION:
        print("Invalid option!")
        print_usage()
    elif code == ec.OPERATOR_SET_FAIL:
        print("Failed to set current user as operator! Aborting ...")
    elif code == ec.NON_OPERATOR_RECEIVE_FAIL:
        print("Failed to initate non-operator receive! Aborting ...")
    elif code == ec.RECEIVE_FAIL:
        print("Failed to receive! Aborting ...")
    

def print_usage():
    print("Usage:")
    print(f"receive files in directory:  python3 {str(sys.argv[0])} -r <path to directory>")
    print(f"send files to target device: python3 {str(sys.argv[0])} -s <path to directory> [<target device name>]")

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

def cmd_run(cmd) -> bool:
    r = True
    try:
        print(f"Trying to execute \'{' '.join(cmd)}\'")
        sp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except Exception:
        print(f"Exception occured during executing \'{' '.join(cmd)}\'")
        r = False    
    
    e = sp.stderr.decode("utf-8")
    if e != '':
        print("Error:")
        print(e)
        r = False

    o = sp.stdout.decode("utf-8")
    if o != '':
        print("Output:")
        print(o)
    #todo: test this
    return r

def main():
    code = ec.NONE

    if len(sys.argv) < 3:
        code = ec.MISSING_OPTION
    else:
        option = sys.argv[1]
        dir = sys.argv[2]
        if str(option) not in ("-r", "-s"):
            code = ec.INVALID_OPTION
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
            print("Discovering files ...")
            files = []
            for root, _, filenames in os.walk(dir):
                for f in filenames:
                    files.append(os.path.join(root, f))
            print(f"{str(len(files))} will be sent")
            
            


    return code




if __name__ == "__main__":
    code = main()
    print_error(code)
    os.sys.exit(code)