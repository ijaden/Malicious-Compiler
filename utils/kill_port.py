import os
import subprocess
import platform

def get_pid_on_windows(port):
    result = subprocess.run(['netstat', '-aon'], stdout=subprocess.PIPE, text=True)
    for line in result.stdout.splitlines():
        if f":{port}" in line:
            parts = line.split()
            return parts[-1]
    return None

def get_pid_on_unix(port):

    result = subprocess.run(['lsof', '-i', f':{port}'], stdout=subprocess.PIPE, text=True)

    print(result.stdout)
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if parts[1].isdigit():
            return parts[1]
    return None

def terminate_process(pid):
    try:
        if platform.system() == "Windows":
            subprocess.run(['taskkill', '/PID', pid, '/F'], check=True)
        else:
            subprocess.run(['kill', '-9', pid], check=True)
    except Exception as e:
        print(f"Error terminating process {pid}: {e}")

def kill(port):
    pid = None
    if platform.system() == "Windows":
        pid = get_pid_on_windows(port)
    else:
        pid = get_pid_on_unix(port)
        print(f"pid={pid}")

    if pid:
        print(f"Terminating process with PID {pid}")
        terminate_process(pid)
    else:
        print(f"No process found on port {port}")