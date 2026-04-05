from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any


RESOURCE_DIR = Path(__file__).resolve().parent / "resources"


def load_object_info() -> dict[str, list[str]]:
    with (RESOURCE_DIR / "object_info.json").open() as f:
        return json.load(f)


OBJECT_INFO = load_object_info()


def parse_language_from_goal_script(goal_script: str, goal_num: int, init_graph: dict[str, Any], template: int = 0) -> str:
    goal_script_split = goal_script.split("_")
    if "closed" in goal_script.lower():
        obj = goal_script_split[1]
        tar_node = [node for node in init_graph["nodes"] if node["id"] == int(obj)]
        if template == 1:
            goal_language = f"could you please close the {tar_node[0]['class_name']}"
        elif template == 2:
            goal_language = f"please close the {tar_node[0]['class_name']}"
        else:
            goal_language = f"close {tar_node[0]['class_name']}"
    elif "turnon" in goal_script.lower():
        obj = goal_script_split[1]
        tar_node = [node for node in init_graph["nodes"] if node["id"] == int(obj)]
        if template == 1:
            goal_language = f"could you please turn on the {tar_node[0]['class_name']}"
        elif template == 2:
            goal_language = f"next turn on the {tar_node[0]['class_name']}"
        else:
            goal_language = f"turn on {tar_node[0]['class_name']}"
    elif "on_" in goal_script.lower() or "inside_" in goal_script.lower():
        rel, obj, tar = goal_script_split[0], goal_script_split[1], goal_script_split[2]
        tar_node = [node for node in init_graph["nodes"] if node["id"] == int(tar)]
        if template == 1:
            goal_language = f"could you please place {goal_num} {obj} {rel} the {tar_node[0]['class_name']}"
        elif template == 2:
            goal_language = f"get {goal_num} {obj} and put it {rel} the {tar_node[0]['class_name']}"
        else:
            goal_language = f"put {goal_num} {obj} {rel} the {tar_node[0]['class_name']}"
    else:
        raise ValueError(f"Unsupported goal script: {goal_script}")
    return goal_language.lower()


def get_goal_language(task_goal: dict[str, int], init_graph: dict[str, Any], template: int = 0) -> list[str]:
    return [parse_language_from_goal_script(subgoal, subgoal_count, init_graph, template=template) for subgoal, subgoal_count in task_goal.items()]


def convert_action(action_dict: dict[int, str | None]) -> list[str]:
    agent_do = [item for item, action in action_dict.items() if action is not None]
    if len(action_dict.keys()) > 1:
        if None not in list(action_dict.values()) and sum(["walk" in x for x in action_dict.values() if x]) < 2:
            objects_interaction = [x.split("(")[1].split(")")[0] for x in action_dict.values() if x]
            if len(set(objects_interaction)) == 1:
                agent_do = [random.choice([0, 1])]
    script_list = [""]
    for agent_id in agent_do:
        script = action_dict[agent_id]
        if script is None:
            continue
        current_script = [f"<char{agent_id}> {script}"]
        script_list = [x + "|" + y if len(x) > 0 else y for x, y in zip(script_list, current_script)]
    return script_list


def separate_new_ids_graph(graph: dict[str, Any], max_id: int) -> dict[str, Any]:
    new_graph = copy.deepcopy(graph)
    for node in new_graph["nodes"]:
        if node["id"] > max_id:
            node["id"] = node["id"] - max_id + 1000
    for edge in new_graph["edges"]:
        if edge["from_id"] > max_id:
            edge["from_id"] = edge["from_id"] - max_id + 1000
        if edge["to_id"] > max_id:
            edge["to_id"] = edge["to_id"] - max_id + 1000
    return new_graph


def inside_not_trans(graph: dict[str, Any]) -> dict[str, Any]:
    id2node = {node["id"]: node for node in graph["nodes"]}
    parents: dict[int, list[int]] = {}
    grabbed_objs: list[int] = []
    for edge in graph["edges"]:
        if edge["relation_type"] == "INSIDE":
            parents.setdefault(edge["from_id"], []).append(edge["to_id"])
        elif edge["relation_type"].startswith("HOLDS"):
            grabbed_objs.append(edge["to_id"])

    edges = []
    for edge in graph["edges"]:
        if edge["relation_type"] == "INSIDE" and id2node[edge["to_id"]]["category"] == "Rooms":
            if len(parents[edge["from_id"]]) == 1:
                edges.append(edge)
        else:
            edges.append(edge)
    graph["edges"] = edges

    parent_for_node = {}
    char_close = {1: [], 2: []}
    for char_id in range(1, 3):
        for edge in graph["edges"]:
            if edge["relation_type"] == "CLOSE":
                if edge["from_id"] == char_id and edge["to_id"] not in char_close[char_id]:
                    char_close[char_id].append(edge["to_id"])
                elif edge["to_id"] == char_id and edge["from_id"] not in char_close[char_id]:
                    char_close[char_id].append(edge["from_id"])

    objects_to_check = []
    for edge in list(graph["edges"]):
        if edge["relation_type"] == "INSIDE":
            parent_for_node[edge["from_id"]] = edge["to_id"]
            if id2node[edge["to_id"]]["class_name"] in ["fridge", "kitchencabinet", "cabinet", "microwave", "dishwasher", "stove"]:
                objects_to_check.append(edge["from_id"])
                for char_id in range(1, 3):
                    if edge["to_id"] in char_close[char_id] and edge["from_id"] not in char_close[char_id]:
                        graph["edges"].append({"from_id": edge["from_id"], "relation_type": "CLOSE", "to_id": char_id})
                        graph["edges"].append({"from_id": char_id, "relation_type": "CLOSE", "to_id": edge["from_id"]})

    nodes_not_rooms = [node["id"] for node in graph["nodes"] if node["category"] not in ["Rooms", "Doors"]]
    nodes_without_parent = list(set(nodes_not_rooms) - set(parent_for_node.keys()))
    nodes_without_parent = [node for node in nodes_without_parent if node not in grabbed_objs]
    if nodes_without_parent:
        pass
    graph["edges"] = [edge for edge in graph["edges"] if not (edge["from_id"] in objects_to_check and edge["relation_type"] == "ON")]
    return graph


def get_visible_nodes(graph: dict[str, Any], agent_id: int) -> dict[str, Any]:
    state = graph
    id2node = {node["id"]: node for node in state["nodes"]}
    rooms_ids = [node["id"] for node in graph["nodes"] if node["category"] == "Rooms"]
    character = id2node[agent_id]
    character_id = character["id"]
    inside_of: dict[int, int] = {}
    is_inside: dict[int, list[int]] = {}
    grabbed_ids: list[int] = []
    for edge in state["edges"]:
        if edge["relation_type"] == "INSIDE":
            is_inside.setdefault(edge["to_id"], []).append(edge["from_id"])
            inside_of[edge["from_id"]] = edge["to_id"]
        elif "HOLDS" in edge["relation_type"] and edge["from_id"] == character["id"]:
            grabbed_ids.append(edge["to_id"])
    room_id = inside_of[character_id]
    object_in_room_ids = list(is_inside[room_id])
    curr_objects = list(object_in_room_ids)
    while curr_objects:
        objects_inside = []
        for curr_obj_id in curr_objects:
            objects_inside += is_inside.get(curr_obj_id, [])
        object_in_room_ids += list(objects_inside)
        curr_objects = list(objects_inside)
    def object_hidden(obj_id: int) -> bool:
        return inside_of[obj_id] not in rooms_ids and "OPEN" not in id2node[inside_of[obj_id]]["states"]
    observable_object_ids = [object_id for object_id in object_in_room_ids if not object_hidden(object_id)] + rooms_ids
    observable_object_ids += grabbed_ids
    return {
        "edges": [edge for edge in state["edges"] if edge["from_id"] in observable_object_ids and edge["to_id"] in observable_object_ids],
        "nodes": [id2node[id_node] for id_node in observable_object_ids],
    }


def check_progress(state: dict[str, Any], goal_spec: dict[str, list[Any]]):
    unsatisfied = {}
    satisfied = {}
    id2node = {node["id"]: node for node in state["nodes"]}
    for key, value in goal_spec.items():
        elements = key.split("_")
        unsatisfied[key] = value[0] if elements[0] not in ["offOn", "offInside"] else 0
        satisfied[key] = []
        for edge in state["edges"]:
            if elements[0] in ["on", "inside"]:
                if edge["relation_type"].lower() == elements[0] and edge["to_id"] == int(elements[2]) and (id2node[edge["from_id"]]["class_name"] == elements[1] or str(edge["from_id"]) == elements[1]):
                    predicate = f"{elements[0]}_{edge['from_id']}_{elements[2]}"
                    satisfied[key].append(predicate)
                    unsatisfied[key] -= 1
            elif elements[0] == "offOn":
                if edge["relation_type"].lower() == "on" and edge["to_id"] == int(elements[2]) and (id2node[edge["from_id"]]["class_name"] == elements[1] or str(edge["from_id"]) == elements[1]):
                    unsatisfied[key] += 1
            elif elements[0] == "offInside":
                if edge["relation_type"].lower() == "inside" and edge["to_id"] == int(elements[2]) and (id2node[edge["from_id"]]["class_name"] == elements[1] or str(edge["from_id"]) == elements[1]):
                    unsatisfied[key] += 1
            elif elements[0] == "holds":
                if edge["relation_type"].lower().startswith("holds") and id2node[edge["to_id"]]["class_name"] == elements[1] and edge["from_id"] == int(elements[2]):
                    predicate = f"{elements[0]}_{edge['to_id']}_{elements[2]}"
                    satisfied[key].append(predicate)
                    unsatisfied[key] -= 1
            elif elements[0] == "sit":
                if edge["relation_type"].lower().startswith("sit") and edge["to_id"] == int(elements[2]) and edge["from_id"] == int(elements[1]):
                    predicate = f"{elements[0]}_{edge['to_id']}_{elements[2]}"
                    satisfied[key].append(predicate)
                    unsatisfied[key] -= 1
        if elements[0] == "turnOn" and "ON" in id2node[int(elements[1])]["states"]:
            predicate = f"{elements[0]}_{elements[1]}_1"
            satisfied[key].append(predicate)
            unsatisfied[key] -= 1
    return satisfied, unsatisfied


def get_valid_actions(obs: dict[int, dict[str, Any]] | list[dict[str, Any]], agent_id: int = 0) -> dict[str, list]:
    if isinstance(obs, dict):
        obs_list = [obs[k] for k in sorted(obs.keys())]
    else:
        obs_list = obs
    objects_grab = OBJECT_INFO["objects_grab"]
    objects_inside = OBJECT_INFO["objects_inside"]
    objects_surface = OBJECT_INFO["objects_surface"]
    objects_switchonoff = OBJECT_INFO["objects_switchonoff"]

    valid_action_space: dict[str, list] = {}
    node_id_name_dict = {node["id"]: node["class_name"] for node in obs_list[0]["nodes"]}
    valid_action_space["turnleft"] = [(None, None)]
    valid_action_space["turnright"] = [(None, None)]
    valid_action_space["walkforward"] = [(None, None)]

    for agent_action in ["walk", "grab", "putback", "putin", "switchon", "open", "close"]:
        if agent_action == "walk":
            ignore_objs = ["walllamp", "doorjamb", "ceilinglamp", "door", "curtains", "candle", "wallpictureframe", "powersocket"]
            interacted_object_idxs = [(node["id"], node["class_name"]) for idx, node in enumerate(obs_list[agent_id]["nodes"]) if node["class_name"] not in ignore_objs]
        elif agent_action == "grab":
            agent_edge = [edge for edge in obs_list[agent_id]["edges"] if edge["from_id"] == agent_id + 1 or edge["to_id"] == agent_id + 1]
            agent_obj_hold_edge = [edge for edge in agent_edge if "HOLD" in edge["relation_type"]]
            if len(agent_obj_hold_edge) > 1:
                continue
            ignore_objs = ["radio"]
            ignore_objs_id = [node["id"] for node in obs_list[agent_id]["nodes"] if node["class_name"] in ignore_objs]
            grabbable_object_ids = [node["id"] for node in obs_list[agent_id]["nodes"] if node["class_name"] in objects_grab and node["id"] not in ignore_objs_id]
            agent_obj_edge = [edge for edge in agent_edge if edge["from_id"] in grabbable_object_ids or edge["to_id"] in grabbable_object_ids]
            agent_obj_close_edge = [edge for edge in agent_obj_edge if edge["relation_type"] == "CLOSE"]
            if not agent_obj_close_edge:
                continue
            interacted_object_ids = sorted({edge["from_id"] for edge in agent_obj_close_edge} | {edge["to_id"] for edge in agent_obj_close_edge})
            interacted_object_ids = [obj_id for obj_id in interacted_object_ids if obj_id != agent_id + 1]
            interacted_object_idxs = [(node["id"], node["class_name"]) for node in obs_list[agent_id]["nodes"] if node["id"] in interacted_object_ids]
        elif agent_action in {"open", "close"}:
            agent_edge = [edge for edge in obs_list[agent_id]["edges"] if edge["from_id"] == agent_id + 1 or edge["to_id"] == agent_id + 1]
            container_nodes = [node for node in obs_list[agent_id]["nodes"] if node["class_name"] in objects_inside]
            if agent_action == "close":
                container_nodes = [node for node in container_nodes if "OPEN" in node["states"]]
            container_ids = [node["id"] for node in container_nodes]
            agent_obj_edge = [edge for edge in agent_edge if edge["from_id"] in container_ids or edge["to_id"] in container_ids]
            agent_obj_close_edge = [edge for edge in agent_obj_edge if edge["relation_type"] == "CLOSE"]
            if not agent_obj_close_edge:
                continue
            interacted_object_ids = sorted({edge["from_id"] for edge in agent_obj_close_edge} | {edge["to_id"] for edge in agent_obj_close_edge})
            interacted_object_ids = [obj_id for obj_id in interacted_object_ids if obj_id != agent_id + 1]
            interacted_object_idxs = [(node["id"], node["class_name"]) for node in obs_list[agent_id]["nodes"] if node["id"] in interacted_object_ids]
        elif agent_action == "switchon":
            agent_edge = [edge for edge in obs_list[agent_id]["edges"] if edge["from_id"] == agent_id + 1 or edge["to_id"] == agent_id + 1]
            switch_nodes = [node for node in obs_list[agent_id]["nodes"] if node["class_name"] in objects_switchonoff and "OFF" in node["states"]]
            switch_ids = [node["id"] for node in switch_nodes]
            agent_obj_edge = [edge for edge in agent_edge if edge["from_id"] in switch_ids or edge["to_id"] in switch_ids]
            agent_obj_close_edge = [edge for edge in agent_obj_edge if edge["relation_type"] == "CLOSE"]
            if not agent_obj_close_edge:
                continue
            interacted_object_ids = sorted({edge["from_id"] for edge in agent_obj_close_edge} | {edge["to_id"] for edge in agent_obj_close_edge})
            interacted_object_ids = [obj_id for obj_id in interacted_object_ids if obj_id != agent_id + 1]
            interacted_object_idxs = [(node["id"], node["class_name"]) for node in obs_list[agent_id]["nodes"] if node["id"] in interacted_object_ids]
        elif agent_action in {"putin", "putback"}:
            agent_edge = [edge for edge in obs_list[agent_id]["edges"] if edge["from_id"] == agent_id + 1 or edge["to_id"] == agent_id + 1]
            agent_obj_hold_edge = [edge for edge in agent_edge if "HOLD" in edge["relation_type"]]
            ignore_objs_tars = [
                ("fryingpan", "kitchencounter"), ("mug", "sofa"), ("pillow", "kitchencounter"), ("pillow", "sofa"),
                ("pillow", "fridge"), ("pillow", "kitchencabinet"), ("pillow", "coffeetable"), ("pillow", "bathroomcabinet"),
                ("keyboard", "coffeetable"), ("keyboard", "bathroomcabinet"), ("keyboard", "cabinet"), ("keyboard", "sofa"),
                ("dishbowl", "bathroomcabinet"), ("hairproduct", "sofa"),
            ]
            if len(agent_obj_hold_edge) != 1:
                continue
            holding_obj_name = node_id_name_dict[agent_obj_hold_edge[0]["to_id"]]
            ignore_tar = [tem[1] for tem in ignore_objs_tars if tem[0] == holding_obj_name]
            holding_obj_id = agent_obj_hold_edge[0]["to_id"]
            if agent_action == "putin":
                container_nodes = [node for node in obs_list[agent_id]["nodes"] if node["class_name"] in objects_inside and node["class_name"] not in ignore_tar and "OPEN" in node["states"]]
            else:
                container_nodes = [node for node in obs_list[agent_id]["nodes"] if node["class_name"] in objects_surface and node["class_name"] not in ignore_tar]
            container_ids = [node["id"] for node in container_nodes]
            agent_obj_edge = [edge for edge in agent_edge if edge["from_id"] in container_ids or edge["to_id"] in container_ids]
            agent_obj_close_edge = [edge for edge in agent_obj_edge if edge["relation_type"] == "CLOSE"]
            if not agent_obj_close_edge:
                continue
            interacted_object_ids = sorted({edge["from_id"] for edge in agent_obj_close_edge} | {edge["to_id"] for edge in agent_obj_close_edge})
            interacted_object_ids = [obj_id for obj_id in interacted_object_ids if obj_id != agent_id + 1]
            interacted_object_idxs = [(holding_obj_id, holding_obj_name, node["id"], node["class_name"]) for node in obs_list[agent_id]["nodes"] if node["id"] in interacted_object_ids]
        else:
            continue
        if interacted_object_idxs:
            valid_action_space[agent_action] = interacted_object_idxs
    return valid_action_space
