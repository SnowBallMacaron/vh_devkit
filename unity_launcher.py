from __future__ import annotations

import atexit
import glob
import os
import socket
import subprocess
from sys import platform


class UnityLauncher:
    def __init__(
        self,
        port: str = "8080",
        file_name: str | None = None,
        batch_mode: bool = True,
        x_display: str | None = None,
        no_graphics: bool = False,
        logging: bool = False,
        docker_enabled: bool = False,
    ) -> None:
        self.proc = None
        atexit.register(self.close)
        self.port_number = int(port)
        self.batchmode = batch_mode
        args = ["-screen-fullscreen", "0", "-screen-quality", "4", "-screen-width", "512", "-screen-height", "512"] if not no_graphics else []
        self.launch_executable(
            file_name=file_name,
            x_display=x_display,
            no_graphics=no_graphics,
            logging=logging,
            docker_enabled=docker_enabled,
            args=args,
        )

    def close(self) -> None:
        if self.proc is not None:
            self.proc.kill()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            self.proc = None

    def check_port(self, port_number: int) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if platform in ("linux", "linux2"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("localhost", port_number))
        except OSError as exc:
            raise RuntimeError(f"Couldn't launch the environment. Port {port_number} is already being used.") from exc
        finally:
            sock.close()

    def launch_executable(
        self,
        file_name: str | None,
        *,
        x_display: str | None = None,
        no_graphics: bool = False,
        docker_enabled: bool = False,
        logging: bool = False,
        args: list[str] | None = None,
    ) -> None:
        if docker_enabled:
            raise RuntimeError("Docker-enabled launch is not supported in vh_devkit.")
        if file_name is None:
            raise ValueError("A Unity executable path is required.")

        args = args or []
        cwd = os.getcwd()
        file_name = file_name.strip().replace(".app", "").replace(".exe", "").replace(".x86_64", "").replace(".x86", "")
        env = os.environ.copy()
        launch_string = None

        if platform in ("linux", "linux2"):
            self.check_port(self.port_number)
            candidates = glob.glob(os.path.join(cwd, file_name) + ".x86_64")
            if not candidates:
                candidates = glob.glob(os.path.join(cwd, file_name) + ".x86")
            if not candidates:
                candidates = glob.glob(file_name + ".x86_64")
            if not candidates:
                candidates = glob.glob(file_name + ".x86")
            if candidates:
                launch_string = candidates[0]
        elif platform == "darwin":
            true_filename = os.path.basename(os.path.normpath(file_name))
            candidates = glob.glob(os.path.join(cwd, file_name + ".app", "Contents", "MacOS", true_filename))
            if not candidates:
                candidates = glob.glob(os.path.join(file_name + ".app", "Contents", "MacOS", true_filename))
            if candidates:
                launch_string = candidates[0]
        elif platform in ("windows", "win32"):
            candidates = glob.glob(os.path.join(cwd, file_name) + ".exe")
            if candidates:
                launch_string = candidates[0]

        if launch_string is None:
            raise FileNotFoundError(f"Couldn't launch Unity. No executable matched: {file_name}")

        subprocess_args = [launch_string]
        if self.batchmode:
            subprocess_args.append("-batchmode")
        if no_graphics:
            subprocess_args.append("-nographics")
        file_path = os.getcwd()
        subprocess_args += [f"-http-port={self.port_number}", f"-logFile {file_path}/Player_{self.port_number}.log"]
        subprocess_args += args

        stdout_target = open(f"{file_path}/port_{self.port_number}.txt", "w+") if logging else subprocess.DEVNULL
        try:
            self.proc = subprocess.Popen(
                subprocess_args,
                env=env,
                stdout=stdout_target,
                start_new_session=True,
            )
        except Exception as exc:
            raise RuntimeError("Unity executable was found but could not be launched.") from exc
