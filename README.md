# VirtualHome Dev Kit

This directory is a small interface for interacting with the VirtualHome Unity environment without needing to learn the rest of the repo.

It exposes a persistent JSONL stdin/stdout server with a very small command surface:

- `reset`
- `observe`
- `valid_actions`
- `step`
- `capture_image`
- `close`

## What It Assumes

Runtime assets are still separate:

- a dataset `.pik` file
- a Unity executable build

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
