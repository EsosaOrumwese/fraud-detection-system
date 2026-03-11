# A Production Wiring Notes

## 2026-03-11 17:41:02 +00:00 - Opening the A-notebook means pinning the baseline foundation before readiness-era reasoning starts to distort it
The first thing that needs to stay disciplined in this notebook is the boundary between `A` and `Bi`.

`A` is not the current readiness-shaped platform. It is the baseline engineered foundation that was wired to make the full `dev_full` platform exist as a real system in the first place. That means the notes here need to stay anchored to the baseline wiring object and the wiring-era decision trail, even when later readiness work gives better hindsight about why some choices mattered.

The immediate source set for this notebook is therefore:

- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.impl_actual.md`
- relevant `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M*.build_plan.md` files where the original wiring choices, path selections, and tradeoffs were made explicit

The working object this notebook will keep interrogating is the baseline wired platform:

- what paths had to exist for `dev_full` to be a serious platform foundation at all
- why those paths were wired in that shape
- why those concrete services and runtime surfaces were selected
- what truth boundaries were being protected
- what constraints and tradeoffs were already known and accepted at wiring time

One thing is already clear from the build record: the baseline platform was not wired as a loose collection of services. It was wired under a small number of strong operating laws that explain much of the shape of the network:

- managed-first runtime posture
- no laptop runtime compute
- fail-closed progression
- single active runtime path per phase/run
- Oracle Store seated as read-only warm source-of-stream boundary
- explicit run identity and control authority
- separated truth ownership across ingress, RTDL, case, label, learning, registry, and governance surfaces

That matters because it means the baseline graph should be read as a path-governed foundation, not as an inventory diagram. The next useful move is to walk the baseline platform path by path and keep asking four questions of each path:

1. what real platform job does this path exist to do
2. why is it wired this way rather than some simpler or more fashionable alternative
3. what truth does it own or protect
4. what tradeoff or constraint is already visible in the wiring choice

Judgment at this point:

- the notebook is now pinned to the correct evidential object for `A`
- the build ledger will be used as the reasoning trail behind the baseline network
- readiness-era graphs and hardening deltas should not be allowed to rewrite the foundation story inside this file
