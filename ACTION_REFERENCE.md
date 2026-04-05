# VirtualHome Planning DSL

This file defines the action language exposed by `vh_devkit`.

The server returns concrete action strings through `valid_actions`, and `step` expects one of those strings.

## State Model

Use these predicates when reasoning about actions:

- `visible(x)`: object or room `x` is present in the current partial observation.
- `close(agent, x)`: the observation contains a `CLOSE` relation between the agent and `x`.
- `holding(agent, x)`: the observation contains a `HOLDS_*` relation between the agent and `x`.
- `hands_free(agent)`: the agent is holding fewer than two objects.
- `open(x)`: node `x` has state `OPEN`.
- `closed(x)`: node `x` has state `CLOSED`.
- `class(x)`: class name of `x`.
- `room(agent)`: current room containing the agent.

The current valid actions are generated directly from the real partial observation, not from a sampled or symbolic graph.

## Action Forms

```text
[turnleft]
[turnright]
[walkforward]
[walk] <target> (id)
[grab] <object> (id)
[open] <container> (id)
[close] <container> (id)
[switchon] <object> (id)
[putin] <held_object> (held_id) <container> (target_id)
[putback] <held_object> (held_id) <surface> (target_id)
```

## Transition Rules

### `turnleft`

```text
action turnleft()
pre  true
post orientation(agent) := orientation(agent) - 90 degrees
```

### `turnright`

```text
action turnright()
pre  true
post orientation(agent) := orientation(agent) + 90 degrees
```

### `walkforward`

```text
action walkforward()
pre  true
post agent moves forward by one step if Unity can execute it
```

### `walk(target)`

```text
action walk(target)
pre  visible(target)
post agent is moved toward target by Unity
post if Unity succeeds, target typically becomes close(agent, target)
```

Notes:

- `target` may be a room or an object.
- Candidate generation excludes a few clutter classes such as `door`, `walllamp`, `ceilinglamp`, `candle`, and `powersocket`.

### `grab(object)`

```text
action grab(object)
pre  visible(object)
pre  close(agent, object)
pre  class(object) in objects_grab
pre  hands_free(agent)
post holding(agent, object)
post object is no longer on or inside its previous support
```

Notes:

- The devkit only offers `grab` for objects from the `objects_grab` set.
- `radio` is explicitly excluded from generated `grab` candidates.

### `open(container)`

```text
action open(container)
pre  visible(container)
pre  close(agent, container)
pre  class(container) in objects_inside
pre  closed(container)
post open(container)
post not closed(container)
```

### `close(container)`

```text
action close(container)
pre  visible(container)
pre  close(agent, container)
pre  class(container) in objects_inside
pre  open(container)
post closed(container)
post not open(container)
```

### `switchon(object)`

```text
action switchon(object)
pre  visible(object)
pre  close(agent, object)
pre  class(object) in objects_switchonoff
pre  object is currently OFF
post object becomes ON if Unity succeeds
```

### `putin(held_object, container)`

```text
action putin(held_object, container)
pre  holding(agent, held_object)
pre  visible(container)
pre  close(agent, container)
pre  class(container) in objects_inside
pre  open(container)
post not holding(agent, held_object)
post inside(held_object, container)
```

Notes:

- `held_object` must be the single object currently held by the agent for this action to be generated.
- Some object-target pairs are blocked by handcrafted filters. See `Pair Filters`.

### `putback(held_object, surface)`

```text
action putback(held_object, surface)
pre  holding(agent, held_object)
pre  visible(surface)
pre  close(agent, surface)
pre  class(surface) in objects_surface
post not holding(agent, held_object)
post on(held_object, surface)
```

Notes:

- `held_object` must be the single object currently held by the agent for this action to be generated.
- Some object-target pairs are blocked by handcrafted filters. See `Pair Filters`.

## Type Sets

### `objects_inside`

```text
bathroom_cabinet
bathroom_counter
bathroomcabinet
cabinet
dishwasher
fridge
kitchencabinet
microwave
oven
stove
```

### `objects_surface`

```text
bathroomcounter
bed
bookshelf
cabinet
coffeetable
cuttingboard
floor
fryingpan
kitchencounter
kitchentable
nightstand
sofa
stove
```

### `objects_switchonoff`

This set is loaded from [`resources/object_info.json`](./resources/object_info.json).

### `objects_grab`

This set is also loaded from [`resources/object_info.json`](./resources/object_info.json).

It contains 85 allowed grabbable class names.

## Pair Filters

The current action generator suppresses these placements:

```text
(fryingpan, kitchencounter)
(mug, sofa)
(pillow, kitchencounter)
(pillow, sofa)
(pillow, fridge)
(pillow, kitchencabinet)
(pillow, coffeetable)
(pillow, bathroomcabinet)
(keyboard, coffeetable)
(keyboard, bathroomcabinet)
(keyboard, cabinet)
(keyboard, sofa)
(dishbowl, bathroomcabinet)
(hairproduct, sofa)
```

These filters apply during candidate generation for `putin` and `putback`.

