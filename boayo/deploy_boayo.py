#!/usr/bin/env python3
"""Deploy and control the BoAYo shell on the lab PYNQ-Z2."""

from __future__ import annotations

import argparse
import os
import posixpath
from pathlib import Path

import paramiko


HOST = os.environ.get("BOAYO_PYNQ_HOST", "192.168.2.99")
USER = os.environ.get("BOAYO_PYNQ_USER", "xilinx")
PASSWORD = os.environ.get("BOAYO_PYNQ_PASSWORD")
REMOTE_ROOT = "/home/xilinx/bosio_v2"
REMOTE_APP = posixpath.join(REMOTE_ROOT, "boayo")
BITSTREAM = posixpath.join(REMOTE_ROOT, "bitstream/bosio_output_disp.bit")
PYTHON = "/usr/local/share/pynq-venv/bin/python3"
FILES = ("boayo_ui.py", "boayo_shell.py", "boayo_desktop.py", "bosio_view_simulator.py", "apps.json")
PY_FILES = tuple(name for name in FILES if name.endswith(".py"))


def command(ssh, text, check=True):
    _, stdout, stderr = ssh.exec_command(text)
    output = stdout.read().decode(errors="replace").strip()
    error = stderr.read().decode(errors="replace").strip()
    status = stdout.channel.recv_exit_status()
    if check and status:
        raise RuntimeError(f"remote command failed ({status}): {error or output}")
    return status, output, error


def connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    options = {"username": USER, "timeout": 10}
    if PASSWORD:
        options["password"] = PASSWORD
    client.connect(HOST, **options)
    return client


def inspect(ssh):
    _, output, _ = command(
        ssh,
        f"printf 'BITSTREAM='; test -f {BITSTREAM} && echo yes || echo no; "
        "printf 'DRIVER='; test -f /home/xilinx/bosio_v2/bosio_driver_v2.py && echo yes || echo no; "
        "printf 'PROCESSES\\n'; pgrep -af 'bosio|boayo' || true",
    )
    print(output)


def status(ssh):
    _, output, _ = command(
        ssh,
        f"tail -n 20 /tmp/boayo.log 2>/dev/null || true; cd {REMOTE_ROOT} && {PYTHON} -c \""
        "from bosio_wm_client import BosioWMClient; c=BosioWMClient('status'); "
        "print('PING',c.ping()); s=c.get_state(); print('SCENE_OWNER',s.get('scene_owner')); "
        "print('OUTPUT',s.get('output')); c.close()\"",
    )
    print(output)


def deploy(ssh):
    source = Path(__file__).resolve().parent
    command(ssh, f"mkdir -p {REMOTE_APP}")
    sftp = ssh.open_sftp()
    try:
        for name in FILES:
            temporary = f"/tmp/{name}.upload"
            sftp.put(str(source / name), temporary)
            command(ssh, f"install -m 0644 {temporary} {REMOTE_APP}/{name} && rm -f {temporary}")
    finally:
        sftp.close()
    command(
        ssh,
        f"ln -sfn {REMOTE_ROOT}/bosio_geometry_v2.py {REMOTE_APP}/bosio_geometry_v2.py; "
        f"ln -sfn {REMOTE_ROOT}/bosio_buttons.py {REMOTE_APP}/bosio_buttons.py; "
        f"ln -sfn {REMOTE_ROOT}/bosio_window_gui.py {REMOTE_APP}/bosio_window_gui.py; "
        f"ln -sfn {REMOTE_ROOT}/bosio_wm_client.py {REMOTE_APP}/bosio_wm_client.py; "
        f"ln -sfn {REMOTE_ROOT}/bosio_driver_v2.py {REMOTE_APP}/bosio_driver_v2.py; "
        f"ln -sfn {REMOTE_ROOT}/bosio_native_compositor.py {REMOTE_APP}/bosio_native_compositor.py; "
        f"ln -sfn {REMOTE_ROOT}/libbosio_compositor.so {REMOTE_APP}/libbosio_compositor.so",
    )
    command(ssh, f"cd {REMOTE_APP} && {PYTHON} -m py_compile {' '.join(PY_FILES)}")
    print(f"DEPLOYED {REMOTE_APP}")


def start(ssh):
    command(ssh, "pkill -TERM -f '[b]oayo_desktop.py' || true")
    launch = (
        f"cd {REMOTE_APP} && setsid -f {PYTHON} -u boayo_desktop.py --m 32 --launcher --apps {REMOTE_APP}/apps.json "
        "> /tmp/boayo.log 2>&1 < /dev/null &"
    )
    command(ssh, launch)
    _, output, _ = command(ssh, "sleep 2; pgrep -af '[b]oayo_desktop.py' || true; tail -n 20 /tmp/boayo.log || true")
    print(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("inspect", "status", "deploy", "start", "deploy-start", "reboot"))
    args = parser.parse_args()
    ssh = connect()
    try:
        if args.action == "inspect":
            inspect(ssh)
        elif args.action == "status":
            status(ssh)
        elif args.action == "reboot":
            command(ssh, "sudo -n reboot", check=False)
        else:
            if args.action in ("deploy", "deploy-start"):
                deploy(ssh)
            if args.action in ("start", "deploy-start"):
                start(ssh)
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
