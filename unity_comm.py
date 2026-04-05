from __future__ import annotations

import base64
import json
import time
from collections.abc import Iterable

import cv2
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from unity_launcher import UnityLauncher


class UnityEngineException(Exception):
    pass


class UnityCommunicationException(Exception):
    pass


class UnityCommunication:
    def __init__(
        self,
        url: str = "127.0.0.1",
        port: str = "8080",
        file_name: str | None = None,
        x_display: str | None = None,
        no_graphics: bool = False,
        logging: bool = True,
        timeout_wait: int = 30,
        docker_enabled: bool = False,
        batch_mode: bool = True,
    ) -> None:
        self._address = f"http://{url}:{port}"
        self.port = port
        self.launcher = None
        self.timeout_wait = timeout_wait
        if file_name is not None:
            self.launcher = UnityLauncher(
                port=port,
                file_name=file_name,
                x_display=x_display,
                no_graphics=no_graphics,
                logging=logging,
                docker_enabled=docker_enabled,
                batch_mode=batch_mode,
            )
            succeeded = False
            for _ in range(5):
                try:
                    self.check_connection()
                    succeeded = True
                    break
                except Exception:
                    time.sleep(2)
            if not succeeded:
                raise RuntimeError("Unable to connect to Unity after launch.")

    def requests_retry_session(self, retries: int = 5, backoff_factor: int = 2, status_forcelist: tuple[int, ...] = (500, 502, 504), session=None):
        session = session or requests.Session()
        retry = Retry(total=retries, read=retries, connect=retries, backoff_factor=backoff_factor, status_forcelist=status_forcelist)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        return session

    def close(self) -> None:
        if self.launcher is not None:
            self.launcher.close()

    def post_command(self, request_dict: dict, repeat: bool = False) -> dict:
        try:
            if repeat:
                resp = self.requests_retry_session().post(self._address, json=request_dict)
            else:
                resp = requests.post(self._address, json=request_dict, timeout=self.timeout_wait)
            if resp.status_code != requests.codes.ok:
                raise UnityEngineException(f"Unity status {resp.status_code}: {resp.text}")
            return resp.json()
        except requests.exceptions.RequestException as exc:
            raise UnityCommunicationException(str(exc)) from exc

    def check_connection(self) -> bool:
        response = self.post_command({"id": str(time.time()), "action": "idle"}, repeat=True)
        return response["success"]

    def add_character(self, character_resource: str = "Chars/Male1", position=None, initial_room: str = "") -> bool:
        mode = "random"
        pos = [0, 0, 0]
        if position is not None:
            mode = "fix_position"
            pos = position
        elif initial_room:
            mode = "fix_room"
        response = self.post_command(
            {
                "id": str(time.time()),
                "action": "add_character",
                "stringParams": [
                    json.dumps(
                        {
                            "character_resource": character_resource,
                            "mode": mode,
                            "character_position": {"x": pos[0], "y": pos[1], "z": pos[2]},
                            "initial_room": initial_room,
                        }
                    )
                ],
            }
        )
        return response["success"]

    def reset(self, scene_index: int | None = None) -> bool:
        response = self.post_command({"id": str(time.time()), "action": "reset", "intParams": [] if scene_index is None else [scene_index]})
        return response["success"]

    def fast_reset(self) -> bool:
        response = self.post_command({"id": str(time.time()), "action": "fast_reset", "intParams": []})
        return response["success"]

    def camera_count(self):
        response = self.post_command({"id": str(time.time()), "action": "camera_count"})
        return response["success"], response["value"]

    def camera_image(self, camera_indexes, mode: str = "normal", image_width: int = 640, image_height: int = 480):
        if not isinstance(camera_indexes, Iterable):
            camera_indexes = [camera_indexes]
        params = {"mode": mode, "image_width": image_width, "image_height": image_height}
        response = self.post_command(
            {"id": str(time.time()), "action": "camera_image", "intParams": list(camera_indexes), "stringParams": [json.dumps(params)]}
        )
        return response["success"], _decode_image_list(response["message_list"])

    def environment_graph(self):
        response = self.post_command({"id": str(time.time()), "action": "environment_graph"})
        return response["success"], json.loads(response["message"])

    def expand_scene(self, new_graph: dict, randomize: bool = False, random_seed: int = -1, animate_character: bool = False, ignore_placing_obstacles: bool = False, prefabs_map=None, transfer_transform: bool = True):
        config = {
            "randomize": randomize,
            "random_seed": random_seed,
            "animate_character": animate_character,
            "ignore_obstacles": ignore_placing_obstacles,
            "transfer_transform": transfer_transform,
        }
        string_params = [json.dumps(config), json.dumps(new_graph)]
        if prefabs_map is not None:
            string_params.append(json.dumps(prefabs_map))
        response = self.post_command({"id": str(time.time()), "action": "expand_scene", "stringParams": string_params})
        try:
            message = json.loads(response["message"])
        except ValueError:
            message = response["message"]
        return response["success"], message

    def render_script(
        self,
        script: list[str],
        randomize_execution: bool = False,
        random_seed: int = -1,
        processing_time_limit: int = 10,
        skip_execution: bool = False,
        find_solution: bool = False,
        output_folder: str = "Output/",
        file_name_prefix: str = "script",
        frame_rate: int = 5,
        image_synthesis=None,
        save_pose_data: bool = False,
        image_width: int = 640,
        image_height: int = 480,
        recording: bool = False,
        save_scene_states: bool = False,
        camera_mode=None,
        time_scale: float = 1.0,
        skip_animation: bool = False,
    ):
        params = {
            "randomize_execution": randomize_execution,
            "random_seed": random_seed,
            "processing_time_limit": processing_time_limit,
            "skip_execution": skip_execution,
            "output_folder": output_folder,
            "file_name_prefix": file_name_prefix,
            "frame_rate": frame_rate,
            "image_synthesis": image_synthesis or ["normal"],
            "find_solution": find_solution,
            "save_pose_data": save_pose_data,
            "save_scene_states": save_scene_states,
            "camera_mode": camera_mode or ["AUTO"],
            "recording": recording,
            "image_width": image_width,
            "image_height": image_height,
            "time_scale": time_scale,
            "skip_animation": skip_animation,
        }
        response = self.post_command({"id": str(time.time()), "action": "render_script", "stringParams": [json.dumps(params)] + script})
        try:
            message = json.loads(response["message"])
        except ValueError:
            message = response["message"]
        return response["success"], message


def _decode_image(img_string: str):
    img_bytes = base64.b64decode(img_string)
    if img_bytes[1:4] == b"PNG":
        return cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    return cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_ANYDEPTH + cv2.IMREAD_ANYCOLOR)


def _decode_image_list(img_string_list: list[str]):
    return [_decode_image(img_string) for img_string in img_string_list]
