#!/usr/bin/env python3
"""Deploy and control the BoAYo shell on the lab PYNQ-Z2."""

from __future__ import annotations

import argparse
import json
import math
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
FILES = ("boayo_ui.py", "boayo_shell.py", "boayo_app_window.py", "boayo_sdk.py", "boayo_desktop.py", "boayo_native_desktop.py", "boayo_example_app.py", "boayo_telemetry_app.py", "boayo_pulse_app.py", "bosio_view_simulator.py", "wait_for_bosio.py", "apps.json", "boayo-desktop.service")
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
            mode = "0755" if name in ("boayo_example_app.py", "boayo_telemetry_app.py", "boayo_pulse_app.py") else "0644"
            command(ssh, f"install -m {mode} {temporary} {REMOTE_APP}/{name} && rm -f {temporary}")
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
    command(ssh, f"sudo -n install -m 0644 {REMOTE_APP}/boayo-desktop.service /etc/systemd/system/boayo-desktop.service")
    command(ssh, "sudo -n systemctl daemon-reload && sudo -n systemctl enable boayo-desktop.service")
    print(f"DEPLOYED {REMOTE_APP}")


def start(ssh):
    command(ssh, "pkill -TERM -f '[b]oayo_desktop.py' || true")
    command(ssh, "sudo -n systemctl restart boayo-desktop.service")
    _, output, _ = command(ssh, "sleep 2; systemctl is-active boayo-desktop.service; pgrep -af '[b]oayo_desktop.py' || true; journalctl -u boayo-desktop.service -n 10 --no-pager || true")
    print(output)


def run_pulse(ssh):
    """Launch the SDK demo at the board's current sensor gaze."""
    _, output, _ = command(
        ssh,
        f"cd {REMOTE_ROOT} && {PYTHON} -c 'import json; from bosio_wm_client import BosioWMClient; "
        "c=BosioWMClient(\"pulse-launch\"); print(json.dumps(c.get_state()[\"output\"])); c.close()'",
    )
    sensor = json.loads(output)
    azimuth = math.degrees(sensor["sensor_yaw_mrad"] / 1000.0)
    elevation = math.degrees(sensor["sensor_pitch_mrad"] / 1000.0)
    command(ssh, "sudo -n systemctl stop boayo-sdk-pulse.service || true", check=False)
    command(ssh, "sudo -n systemctl reset-failed boayo-sdk-pulse.service || true", check=False)
    _, output, _ = command(
        ssh,
        "sudo -n systemd-run --unit=boayo-sdk-pulse --uid=xilinx --gid=xilinx "
        f"--working-directory={REMOTE_APP} "
        f"--setenv=PYTHONPATH={REMOTE_APP}:{REMOTE_ROOT} "
        f"--setenv=BOAYO_APP_AZIMUTH={azimuth:.3f} "
        f"--setenv=BOAYO_APP_ELEVATION={elevation:.3f} "
        f"{PYTHON} -u {REMOTE_APP}/boayo_pulse_app.py",
    )
    command(ssh, "sudo -n systemctl kill --signal=SIGUSR1 --kill-who=main boayo-desktop.service")
    print(f"SDK PULSE azimuth={azimuth:.2f} elevation={elevation:.2f}: {output}")


def pulse_status(ssh):
    _, output, _ = command(
        ssh,
        f"cd {REMOTE_ROOT} && {PYTHON} -c 'import json; from bosio_wm_client import BosioWMClient; "
        "c=BosioWMClient(\"pulse-status\"); s=c.get_state(); "
        "print(json.dumps({\"generation\":s[\"generation\"],\"windows\":s[\"windows\"],\"output\":s[\"output\"]})); c.close()'",
    )
    state = json.loads(output)
    _, service, _ = command(ssh, "systemctl is-active boayo-sdk-pulse.service", check=False)
    print(json.dumps({"service": service, **state}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("inspect", "status", "deploy", "start", "deploy-start", "run-pulse", "pulse-status", "reboot"))
    args = parser.parse_args()
    ssh = connect()
    try:
        if args.action == "inspect":
            inspect(ssh)
        elif args.action == "status":
            status(ssh)
        elif args.action == "run-pulse":
            run_pulse(ssh)
        elif args.action == "pulse-status":
            pulse_status(ssh)
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

