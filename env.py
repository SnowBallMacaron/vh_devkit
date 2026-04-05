from __future__ import annotations

import copy
from typing import Any

from graph_utils import check_progress, convert_action, get_visible_nodes, inside_not_trans, separate_new_ids_graph
from unity_comm import UnityCommunication


class UnityTaskEnvironment:
    def __init__(
        self,
        env_task_set,
        *,
        num_agents: int = 1,
        max_episode_length: int = 100,
        observation_types: list[str] | None = None,
        base_port: int = 8085,
        unity_port_id: int = 5,
        executable_args: dict[str, Any] | None = None,
        seed: int = 13,
    ) -> None:
        import random
        import numpy as np

        self.num_agents = num_agents
        self.max_episode_length = max_episode_length
        self.env_task_set = env_task_set
        self.observation_types = observation_types or ["partial" for _ in range(num_agents)]
        self.agent_goals = ["full" for _ in range(num_agents)]
        self.recording_options = {"recording": False, "output_folder": None, "file_name_prefix": None, "cameras": "PERSON_FROM_BACK", "modality": "normal"}
        self.base_port = base_port
        self.port_id = unity_port_id
        self.executable_args = executable_args or {}
        self.seed = seed
        self.rnd = random.Random(seed)
        np.random.seed(seed)

        self.task_goal, self.goal_spec = {0: {}, 1: {}}, {0: {}, 1: {}}
        self.full_graph = None
        self.steps = 0
        self.prev_reward = 0.0
        self.env_id = None
        self.max_ids: dict[int, int] = {}
        self.num_camera_per_agent = 6
        self.default_image_width = 300
        self.default_image_height = 300
        self.agent_info = {0: "Chars/Female1", 1: "Chars/Male1"}
        self.changed_graph = True
        self.rooms = None
        self.id2node = None
        self.num_static_cameras = None

        self.comm = UnityCommunication(port=str(base_port + unity_port_id), **self.executable_args)

    def close(self) -> None:
        self.comm.close()

    def get_goal(self, task_spec: dict[str, int], agent_goal: str):
        if agent_goal == "full":
            return {goal_k: [goal_c, True, 2] for goal_k, goal_c in task_spec.items()}
        raise NotImplementedError

    def reward(self):
        reward = 0.0
        done = True
        satisfied, unsatisfied = check_progress(self.get_graph(), self.goal_spec[0])
        for key, value in satisfied.items():
            preds_needed, mandatory, reward_per_pred = self.goal_spec[0][key]
            value_pred = min(len(value), preds_needed)
            reward += value_pred * reward_per_pred
            if mandatory and unsatisfied[key] > 0:
                done = False
        self.prev_reward = reward
        return reward, done, {"satisfied_goals": satisfied}

    def reset(self, environment_graph=None, task_id: int | None = None):
        if task_id is None:
            task_id = self.rnd.choice(list(range(len(self.env_task_set))))
        env_task = self.env_task_set[task_id]
        self.task_index = task_id
        self.task_id = env_task["task_id"]
        self.init_graph = copy.deepcopy(env_task["init_graph"])
        self.init_rooms = env_task["init_rooms"]
        self.task_goal = env_task["task_goal"]
        self.task_name = env_task["task_name"]

        self.env_id = env_task["env_id"]
        self.goal_spec = {agent_id: self.get_goal(self.task_goal[agent_id], self.agent_goals[agent_id]) for agent_id in range(self.num_agents)}
        self.comm.reset(self.env_id)

        _, graph = self.comm.environment_graph()
        if self.env_id not in self.max_ids:
            self.max_ids[self.env_id] = max(node["id"] for node in graph["nodes"])
        max_id = self.max_ids[self.env_id]

        updated_graph = environment_graph if environment_graph is not None else self.init_graph
        updated_graph = separate_new_ids_graph(updated_graph, max_id)
        success, _ = self.comm.expand_scene(updated_graph)
        if not success:
            return None

        self.num_static_cameras = self.comm.camera_count()[1]
        rooms = list(self.init_rooms) if self.init_rooms and self.init_rooms[0] in ["kitchen", "bedroom", "livingroom", "bathroom"] else self.rnd.sample(["kitchen", "bedroom", "livingroom", "bathroom"], 2)
        for i in range(self.num_agents):
            if i in self.agent_info:
                self.comm.add_character(self.agent_info[i], initial_room=rooms[i])
            else:
                self.comm.add_character()

        _, self.init_unity_graph = self.comm.environment_graph()
        self.changed_graph = True
        graph = self.get_graph()
        self.rooms = [(node["class_name"], node["id"]) for node in graph["nodes"] if node["category"] == "Rooms"]
        self.id2node = {node["id"]: node for node in graph["nodes"]}
        obs = self.get_observations()
        self.steps = 0
        self.prev_reward = 0.0
        return obs

    def get_graph(self):
        if self.changed_graph:
            success, graph = self.comm.environment_graph()
            if not success:
                return None
            self.graph = graph
            self.changed_graph = False
        return self.graph

    def get_observation(self, agent_id: int, obs_type: str, info: dict | None = None):
        info = info or {}
        if obs_type == "partial":
            curr_graph = self.get_graph()
            curr_graph = inside_not_trans(curr_graph)
            self.full_graph = curr_graph
            return get_visible_nodes(curr_graph, agent_id=agent_id + 1)
        if obs_type == "full":
            curr_graph = self.get_graph()
            curr_graph = inside_not_trans(curr_graph)
            self.full_graph = curr_graph
            return curr_graph
        if obs_type == "image":
            camera_ids = [self.num_static_cameras + agent_id * self.num_camera_per_agent + info["camera_id"]]
            image_width = info.get("image_width", self.default_image_width)
            image_height = info.get("image_height", self.default_image_height)
            success, images = self.comm.camera_image(camera_ids, mode=info["mode"], image_width=image_width, image_height=image_height)
            if not success:
                return None
            return images[0]
        raise NotImplementedError

    def get_observations(self):
        return {agent_id: self.get_observation(agent_id, self.observation_types[agent_id]) for agent_id in range(self.num_agents)}

    def step(self, action_dict: dict[int, str | None]):
        script_list = convert_action(action_dict)
        failed_execution = False
        message = ""
        if script_list and len(script_list[0]) > 0:
            success, message = self.comm.render_script(script_list, recording=False, image_synthesis=[], skip_animation=True)
            if not success:
                failed_execution = True
            else:
                self.changed_graph = True
        reward, done, info = self.reward()
        graph = self.get_graph()
        self.steps += 1
        obs = self.get_observations()
        info["finished"] = done
        info["graph"] = graph
        info["failed_exec"] = failed_execution
        info["message"] = message
        if self.steps == self.max_episode_length:
            done = True
        return obs, reward, done, info
