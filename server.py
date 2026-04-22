#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np
from imageio import v2 as imageio

DEVKIT_ROOT = Path(__file__).resolve().parent
from env import UnityTaskEnvironment
from graph_utils import get_goal_language, get_valid_actions

DEFAULT_DATASET_PATH = DEVKIT_ROOT / "assets/datasets/env_task_set_50_simple_unseen_item.pik"
DEFAULT_EXEC_PATH = DEVKIT_ROOT / "assets/unity/linux_exec.v2.2.5_beta.x86_64"


def _resolve_path(path_str: str | Path) -> Path:
    path = Path(path_str)
    return path


def _bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3 and image.shape[2] == 3:
        return image[:, :, ::-1]
    return image


def _graph_stats(graph: dict[str, Any]) -> dict[str, int]:
    return {"nodes": len(graph.get("nodes", [])), "edges": len(graph.get("edges", []))}


def _visible_objects_summary(partial_obs: dict[int, dict[str, Any]], agent_id: int = 0) -> list[str]:
    graph = partial_obs[agent_id]
    return sorted({node["class_name"] for node in graph.get("nodes", [])})


def _format_valid_actions(obs: list[dict[str, Any]], agent_id: int = 0) -> list[str]:
    valid_action_space: list[str] = []
    valid_action_space_dict = get_valid_actions(obs, agent_id)
    for action, interact_item_idxs in valid_action_space_dict.items():
        action = action.replace("walktowards", "walk")
        if interact_item_idxs is None or interact_item_idxs == [] or interact_item_idxs == [(None, None)]:
            valid_action_space.append(f"[{action}]")
        elif "put" in action:
            valid_action_space.extend(
                f"[{action}] <{grab_name}> ({grab_id}) <{item_name}> ({item_id})"
                for grab_id, grab_name, item_id, item_name in interact_item_idxs
            )
        else:
            valid_action_space.extend(
                f"[{action}] <{item_name}> ({item_id})"
                for item_id, item_name in interact_item_idxs
                if item_name not in ["wall", "floor", "ceiling", "curtain", "window"]
            )
    return valid_action_space


class VirtualHomeDevServer:
    def __init__(
        self,
        dataset: str | Path,
        *,
        exec_path: str | Path,
        base_port: int,
        unity_port_id: int,
        image_width: int,
        image_height: int,
        image_mode: str,
        use_editor: bool,
        no_graphics: bool,
        batch_mode: bool,
    ) -> None:
        dataset_path = _resolve_path(dataset)
        with dataset_path.open("rb") as f:
            self.env_task_set = pickle.load(f)

        self.dataset_path = dataset_path
        self.image_width = image_width
        self.image_height = image_height
        self.image_mode = image_mode
        self.current_task_index: int | None = None

        executable_args = {"batch_mode": batch_mode, "no_graphics": no_graphics}
        if not use_editor:
            executable_args["file_name"] = str(_resolve_path(exec_path))
        self.env = UnityTaskEnvironment(
            env_task_set=self.env_task_set,
            num_agents=1,
            max_episode_length=100,
            base_port=base_port,
            unity_port_id=unity_port_id,
            observation_types=["partial"],
            executable_args=executable_args,
            seed=13,
        )

    def close(self) -> None:
        self.env.close()

    def _goal_text(self, graph: dict[str, Any]) -> str:
        return ", ".join(get_goal_language(self.env.task_goal[0], graph))

    def _snapshot(self, obs: dict[int, dict[str, Any]] | None = None, include_graph: bool = False) -> dict[str, Any]:
        obs = obs if obs is not None else self.env.get_observations()
        graph = self.env.get_graph()
        valid_actions = _format_valid_actions(obs, agent_id=0)
        payload: dict[str, Any] = {
            "task_index": self.current_task_index,
            "task_id": self.env.task_id,
            "task_name": self.env.task_name,
            "env_id": self.env.env_id,
            "goal": self._goal_text(graph),
            "graph_stats": _graph_stats(graph),
            "visible_objects": _visible_objects_summary(obs, agent_id=0),
            "valid_actions": valid_actions,
            "valid_action_count": len(valid_actions),
        }
        if include_graph:
            payload["graph"] = graph
            payload["partial_observation"] = obs[0]
        return payload

    def reset(self, task_id: int = 0, include_graph: bool = False) -> dict[str, Any]:
        obs = self.env.reset(task_id=task_id)
        self.current_task_index = task_id
        return self._snapshot(obs=obs, include_graph=include_graph)

    def observe(self, include_graph: bool = False) -> dict[str, Any]:
        return self._snapshot(obs=self.env.get_observations(), include_graph=include_graph)

    def valid_actions(self) -> dict[str, Any]:
        obs = self.env.get_observations()
        valid_actions = _format_valid_actions(obs, agent_id=0)
        return {
            "task_index": self.current_task_index,
            "valid_actions": valid_actions,
            "valid_action_count": len(valid_actions),
        }

    def step(self, action: str, include_graph: bool = False) -> dict[str, Any]:
        obs_before = self.env.get_observations()
        valid_actions_before = _format_valid_actions(obs_before, agent_id=0)
        obs, reward, done, info = self.env.step({0: action})
        payload = self._snapshot(obs=obs, include_graph=include_graph)
        payload.update(
            {
                "action": action,
                "was_valid_action": action in valid_actions_before,
                "reward": reward,
                "done": bool(done),
                "failed_exec": bool(info.get("failed_exec")) if isinstance(info, dict) else False,
                "message": info.get("message") if isinstance(info, dict) else None,
                "satisfied_goals": info.get("satisfied_goals") if isinstance(info, dict) else None,
            }
        )
        return payload

    def capture_image(
        self,
        output_path: str | Path,
        *,
        camera_id: int = 2,
        image_width: int | None = None,
        image_height: int | None = None,
        image_mode: str | None = None,
    ) -> dict[str, Any]:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        image = self.env.get_observation(
            agent_id=0,
            obs_type="image",
            info={
                "image_width": image_width or self.image_width,
                "image_height": image_height or self.image_height,
                "camera_id": camera_id,
                "mode": image_mode or self.image_mode,
            },
        )
        image_arr = _bgr_to_rgb(np.asarray(image))
        imageio.imwrite(path, image_arr)
        return {
            "task_index": self.current_task_index,
            "output_path": str(path),
            "shape": list(image_arr.shape),
            "camera_id": camera_id,
            "mode": image_mode or self.image_mode,
        }

    def capture_images(
        self,
        output_dir: str | Path,
        *,
        camera_ids: list[int],
        image_width: int | None = None,
        image_height: int | None = None,
        image_mode: str | None = None,
        filename_prefix: str = "image",
    ) -> dict[str, Any]:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)

        saved_images: list[dict[str, Any]] = []
        for camera_id in camera_ids:
            image_path = output_root / f"{filename_prefix}_cam_{camera_id}.png"
            result = self.capture_image(
                output_path=image_path,
                camera_id=camera_id,
                image_width=image_width,
                image_height=image_height,
                image_mode=image_mode,
            )
            saved_images.append(result)

        return {
            "task_index": self.current_task_index,
            "output_dir": str(output_root),
            "images": saved_images,
        }


def _reply(payload: dict[str, Any]) -> None:
    def convert(value: Any):
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [convert(v) for v in value]
        if isinstance(value, tuple):
            return [convert(v) for v in value]
        if isinstance(value, np.generic):
            return value.item()
        return value

    sys.stdout.write(json.dumps(convert(payload)) + "\n")
    sys.stdout.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal JSONL interface for interacting with VirtualHome.")
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        type=str,
        help="Path to a VirtualHome env_task_set .pik file.",
    )
    parser.add_argument(
        "--exec_path",
        default=str(DEFAULT_EXEC_PATH),
        type=str,
        help="Path to the Unity executable.",
    )
    parser.add_argument("--base_port", default=8085, type=int, help="Base port for Unity executable.")
    parser.add_argument("--unity_port_id", default=5, type=int, help="Port offset for Unity executable.")
    parser.add_argument("--image_width", default=512, type=int, help="Default image width.")
    parser.add_argument("--image_height", default=512, type=int, help="Default image height.")
    parser.add_argument("--image_mode", default="normal", type=str, help="Default image mode.")
    parser.add_argument("--use_editor", action="store_true", help="Connect to a Unity editor instead of an executable.")
    parser.add_argument("--no_graphics", action="store_true", help="Launch Unity with no graphics.")
    parser.add_argument("--batch_mode", action="store_true", help="Launch Unity in batch mode.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = VirtualHomeDevServer(
        dataset=args.dataset,
        exec_path=args.exec_path,
        base_port=args.base_port,
        unity_port_id=args.unity_port_id,
        image_width=args.image_width,
        image_height=args.image_height,
        image_mode=args.image_mode,
        use_editor=args.use_editor,
        no_graphics=args.no_graphics,
        batch_mode=args.batch_mode,
    )
    _reply(
        {
            "ok": True,
            "result": {
                "message": "VirtualHome dev server ready",
                "dataset": str(server.dataset_path),
                "commands": [
                    "reset",
                    "observe",
                "valid_actions",
                "step",
                "capture_image",
                "capture_images",
                "close",
            ],
        },
        }
    )

    try:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            request = json.loads(line)
            cmd = request.get("cmd")
            if cmd == "reset":
                result = server.reset(
                    task_id=int(request.get("task_id", 0)),
                    include_graph=bool(request.get("include_graph", False)),
                )
            elif cmd == "observe":
                result = server.observe(include_graph=bool(request.get("include_graph", False)))
            elif cmd == "valid_actions":
                result = server.valid_actions()
            elif cmd == "step":
                result = server.step(
                    action=str(request["action"]),
                    include_graph=bool(request.get("include_graph", False)),
                )
            elif cmd == "capture_image":
                result = server.capture_image(
                    output_path=request["output_path"],
                    camera_id=int(request.get("camera_id", 2)),
                    image_width=int(request["image_width"]) if "image_width" in request else None,
                    image_height=int(request["image_height"]) if "image_height" in request else None,
                    image_mode=request.get("image_mode"),
                )
            elif cmd == "capture_images":
                camera_ids = request.get("camera_ids", [2])
                result = server.capture_images(
                    output_dir=request["output_dir"],
                    camera_ids=[int(camera_id) for camera_id in camera_ids],
                    image_width=int(request["image_width"]) if "image_width" in request else None,
                    image_height=int(request["image_height"]) if "image_height" in request else None,
                    image_mode=request.get("image_mode"),
                    filename_prefix=str(request.get("filename_prefix", "image")),
                )
            elif cmd == "close":
                server.close()
                _reply({"ok": True, "result": {"message": "closed"}})
                return 0
            else:
                raise ValueError(f"Unknown command: {cmd}")
            _reply({"ok": True, "result": result})
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
