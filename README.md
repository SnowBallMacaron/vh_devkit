# VirtualHome Dev Kit

This directory is a small interface for interacting with the VirtualHome Unity environment without needing to learn the rest of the repo.

It exposes a persistent JSONL stdin/stdout server with a very small command surface:

- `reset`
- `observe`
- `valid_actions`
- `step`
- `capture_image`
- `capture_images`
- `close`

## What It Assumes

Runtime assets are still separate:

- a dataset `.pik` file
- a Unity executable build

## Python Setup

This devkit was tested with Python `3.12` and the package versions pinned in [`requirements.txt`](./requirements.txt).

If you use `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

If you use standard `venv` + `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Start The Server

From the `vh_devkit` repo root, first download the runtime assets bundle here https://drive.google.com/file/d/1fjKpJ4qvFHMi8A7yqyArDVP-FN9YW6Ys/view?usp=drive_link and place the files so these paths exist:

```text
assets/datasets/env_task_set_50_simple_unseen_item.pik
assets/unity/linux_exec.v2.2.5_beta.x86_64
assets/unity/UnityPlayer.so
assets/unity/linux_exec.v2.2.5_beta_Data/
```

The expected layout is:

```text
vh_devkit/
  assets/
    datasets/
      env_task_set_50_simple_unseen_item.pik
    unity/
      linux_exec.v2.2.5_beta.x86_64
      UnityPlayer.so
      linux_exec.v2.2.5_beta_Data/
```

Then run:

```bash
python server.py --base_port 8085 --unity_port_id 5
```

If the assets are stored elsewhere, pass them explicitly:

```bash
python server.py \
  --dataset assets/datasets/env_task_set_50_simple_unseen_item.pik \
  --exec_path assets/unity/linux_exec.v2.2.5_beta.x86_64 \
  --base_port 8085 \
  --unity_port_id 5
```

On startup the server prints one JSON line describing the available commands.

## JSONL Protocol

Send one JSON object per line on stdin. The server responds with one JSON object per line on stdout.

### Reset A Task

```json
{"cmd":"reset","task_id":0}
```

### Inspect Current State

```json
{"cmd":"observe"}
```

To include the full graph and current partial observation:

```json
{"cmd":"observe","include_graph":true}
```

### Get Valid Actions

```json
{"cmd":"valid_actions"}
```

### Step The Environment

Use an exact action string returned by `valid_actions`:

```json
{"cmd":"step","action":"[walk] <kitchen> (11)"}
```

### Save An Image

```json
{"cmd":"capture_image","output_path":"tmp/task0.png","camera_id":2}
```

### Save Multiple Current-Frame Images

Save the current frame for each requested camera id.

```json
{"cmd":"capture_images","output_dir":"tmp/task0_views","camera_ids":[0,2,3]}
```

### Close The Server

```json
{"cmd":"close"}
```

## Example Python Client

```bash
python example_client.py
```

## Notes

- `camera_id=2` is first-person in this codebase.
- `valid_actions` returns the same string format used by the existing planners.
- `step` reports both `was_valid_action` and Unity-side `failed_exec`.
- If `python server.py` fails at startup, the first thing to check is that the downloaded assets are in the exact `assets/datasets/` and `assets/unity/` locations above.
  echo 'Package: libnvidia-* nvidia-* linux-modules-nvidia-* linux-objects-nvidia-* linux-signatures-nvidia-* xserver-xorg-video-nvidia*' | sudo tee /etc/apt/preferences.d/ubuntu-nvidia-drivers.pref

  echo 'Pin: origin developer.download.nvidia.com' | sudo tee -a /etc/apt/preferences.d/ubuntu-nvidia-drivers.pref

  echo 'Pin-Priority: -1' | sudo tee -a /etc/apt/preferences.d/ubuntu-nvidia-drivers.pref


python -m mcts.virtualhome.object_id_agent \
--model Qwen3.5-9B-VL-local \
--model_config models.yaml \
--log_dir virtualhome_objid \
--mode simple \
--image_width 512 \
--image_height 512 \
--camera_id 2 \
--num_views 6 \
--device cuda:0 \
--base_port 8085 \
--unity_port_id 4 \
--max_new_tokens 2048 \
--top_k 10 \
--presence_json_mode \
--debug

xvfb-run -a --server-args='-screen 0 1280x1024x24' python -m mcts.virtualhome.object_id_agent --model Qwen3.5-9B-VL-local --model_config models.yaml --log_dir virtualhome_objid --mode simple --image_width 512 --image_height 512 --camera_id 2 --num_views 6  --device cuda:0 --base_port 8085 --unity_port_id 4 --max_new_tokens 2048 --top_k 10 --presence_json_mode && xvfb-run -a --server-args='-screen 0 1280x1024x24' python -m mcts.virtualhome.step_policy_agent --model Qwen3.5-9B-VL-local --model_config models.yaml --log_dir qwen3.5-9b-vl-local --mode simple --batch_size 1 --device cuda:0 --unity_port_id 2 --image_width 512 --image_height 512 --camera_ids 2 --image_angles 000 --fewshot_examples 0 --strict_action_validation --use_images
