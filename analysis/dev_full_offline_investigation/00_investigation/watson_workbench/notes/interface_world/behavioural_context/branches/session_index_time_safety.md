# Branch Investigation: Session Index and Time Safety

## Branch question

The parent behavioural-context investigation established that `s1_session_index_6B` is the session-level context surface exposed in the interface pack. This branch asks:

> Why is session context useful for offline fraud analytics, but dangerous if treated as a live decision-time feature source?

The answer is that `s1_session_index_6B` is a completed-session index. It is valuable because it compresses the arrival world into session units and tells us how many arrivals each completed session carried, when the session began, when it ended, and which merchant/customer-side entities were attached to it. That makes it useful for offline reconstruction, case review, replay analysis, session-level exposure, and post-hoc behavioural summaries.

But the same fields that make it useful offline make it unsafe for live-time modelling if used naively. `session_end_utc` and `arrival_count` require knowledge of the full completed session. At the moment the first arrival in a session is being authorized, the platform cannot know whether that session will end immediately, continue for another arrival, or continue for several more arrivals. So this surface must be treated as offline/session-closure context, not as a hot RTDL feature table.

## Evidence used

Primary report:

- [`../behavioural_context_investigation.md`](../behavioural_context_investigation.md)

Contract references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`](../../../../../../../../docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml)
- [`docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`](../../../../../../../../docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml)
- [`docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`](../../../../../../../../docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml)

Pinned data surface:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s1_session_index_6B`](../../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s1_session_index_6B)

Parent exports:

- [`session_index_schema.csv`](../../../../exports/interface_world/behavioural_context/session_index_schema.csv)
- [`session_index_profile.csv`](../../../../exports/interface_world/behavioural_context/session_index_profile.csv)
- [`session_index_nulls.csv`](../../../../exports/interface_world/behavioural_context/session_index_nulls.csv)
- [`session_index_arrival_count_summary.csv`](../../../../exports/interface_world/behavioural_context/session_index_arrival_count_summary.csv)

Branch exports:

- [`session_time_safety_profile.csv`](../../../../exports/interface_world/behavioural_context/branches/session_index_time_safety/session_time_safety_profile.csv)
- [`session_arrival_count_distribution.csv`](../../../../exports/interface_world/behavioural_context/branches/session_index_time_safety/session_arrival_count_distribution.csv)
- [`session_duration_by_arrival_count_band.csv`](../../../../exports/interface_world/behavioural_context/branches/session_index_time_safety/session_duration_by_arrival_count_band.csv)
- [`session_live_safety_classification.csv`](../../../../exports/interface_world/behavioural_context/branches/session_index_time_safety/session_live_safety_classification.csv)

The branch uses compact session summaries and one targeted scan of `s1_session_index_6B` to quantify session closure, duration, and arrival-count structure. It does not scan the behavioural streams or truth products because this branch is about whether the session index itself is time-safe.

## What this surface is

The contract describes `s1_session_index_6B` as one row per session. Its primary key is:

- `seed`
- `manifest_fingerprint`
- `scenario_id`
- `session_id`

The observed columns are:

| Field | Operating meaning in this platform | Time-safety read |
|---|---|---|
| `session_id` | The handle that identifies a session. | Safe as an identifier after it is emitted/known. |
| `session_start_utc` | The timestamp at which the session began. | Safe only once the session has started. |
| `session_end_utc` | The timestamp at which the completed session ended. | Offline closure field; unsafe at session start or before session close. |
| `arrival_count` | The total number of arrivals in the completed session. | Offline closure field; unsafe before the session is complete. |
| `merchant_id` | Merchant attached to the session row. | Context field, but its live safety depends on when the session row is being used. |
| `party_id` | Party attached to the session row. | Context field, but not a substitute for arrival-grain identity binding. |
| `account_id` | Account attached to the session row. | Context field, but not a substitute for fanout evidence. |
| `instrument_id` | Instrument attached to the session row. | Context field, but not a substitute for fanout evidence. |
| `device_id` | Device attached to the session row. | Context field, but not a substitute for fanout evidence. |
| lineage fields | `seed`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`. | Needed for run identity and reproducibility. |

The important distinction is between a session identifier and a completed-session summary. A live system can attach an event to a known `session_id` if the session state is maintained online. That does not mean the final `arrival_count` or final `session_end_utc` is available at the time of the first request.

This is the core time-safety issue. A final session index is a good offline reconstruction surface, but a bad live feature source unless each feature is explicitly converted into an as-of-time version.

## Physical profile

The pinned session index contains:

| Metric | Value |
|---|---:|
| Sessions / rows | `184,820,742` |
| Represented arrivals | `236,691,694` |
| Merchants | `4,050` |
| Minimum session start | `2026-01-01T00:00:00.001940Z` |
| Maximum session end | `2026-03-31T23:59:59.944516Z` |
| Negative-duration sessions | `0` |
| Zero-duration sessions | `141,986,429` |
| Positive-duration sessions | `42,834,313` |
| Single-arrival sessions | `141,986,429` |
| Multi-arrival sessions | `42,834,313` |
| Arrivals inside multi-arrival sessions | `94,705,265` |
| Approx median duration | `0` seconds |
| Approx P95 duration | `45,041` seconds |
| Approx P99 duration | `66,945` seconds |
| Maximum duration | `86,386` seconds |

The surface is complete in required fields and internally coherent: the sum of `arrival_count` exactly reconstructs the `236,691,694` arrival rows. It also has no negative durations. So the issue is not data corruption. The issue is feature timing.

The zero-duration count is exactly the single-arrival session count. That means a session with one arrival is represented as starting and ending at the same timestamp. This is coherent as a completed-session record. It is not safe as a live-time feature because knowing that a session has ended at the first arrival means knowing that no later arrival will occur in that session.

## Arrival-count shape

The arrival-count distribution is:

| Arrival count | Sessions | Session share | Represented arrivals | Represented arrival share |
|---:|---:|---:|---:|---:|
| `1` | `141,986,429` | `76.82%` | `141,986,429` | `59.99%` |
| `2` | `35,140,408` | `19.01%` | `70,280,816` | `29.69%` |
| `3` | `6,525,895` | `3.53%` | `19,577,685` | `8.27%` |
| `4` | `1,013,373` | `0.55%` | `4,053,492` | `1.71%` |
| `5+` | `154,637` | `0.08%` | `793,272` | `0.34%` |

Most sessions are short. `76.82%` of sessions have one arrival, and `95.84%` have one or two arrivals. At arrival grain, single-arrival sessions still represent `59.99%` of arrivals, while two-arrival sessions represent another `29.69%`. So session context exists across the whole operating world, but most of it is not a long behavioural chain.

This matters for stakeholder-facing analytics. If we later say "session behaviour," we should not let the term imply a long web-session journey for most traffic. In this extract, a session is usually a very short operating unit. Session-level analysis can still be valuable, but the evidence says it is mostly useful for short-window reconstruction, not for long-horizon behavioural narratives.

## Duration and closure behaviour

Duration follows the arrival-count structure:

| Arrival-count band | Sessions | Represented arrivals | Approx median duration | Approx P95 duration | Approx P99 duration | Max duration |
|---|---:|---:|---:|---:|---:|---:|
| `1` | `141,986,429` | `141,986,429` | `0s` | `0s` | `0s` | `0s` |
| `2` | `35,140,408` | `70,280,816` | `22,839s` | `62,417s` | `75,367s` | `86,386s` |
| `3` | `6,525,895` | `19,577,685` | `38,367s` | `71,525s` | `79,885s` | `86,385s` |
| `4` | `1,013,373` | `4,053,492` | `47,452s` | `75,623s` | `81,717s` | `86,363s` |
| `5+` | `154,637` | `793,272` | `54,314s` | `78,217s` | `82,882s` | `86,334s` |

The duration profile is coherent. More arrivals per session generally means longer sessions. The maximum duration is just under one day, which suggests the session construction is bounded inside a daily-style operating horizon rather than allowing arbitrarily long sessions.

That coherence is exactly why the index is useful offline. It lets us reconstruct completed session windows and inspect how traffic clusters inside them. For case review, this can answer questions such as:

- was this flow isolated or part of a short repeated session?
- how many arrivals occurred in the same completed session?
- was the session a single-arrival event or a multi-arrival sequence?
- how long did the completed session last?
- which merchant and customer-side handles were attached to the session row?

But this same coherence is why the surface is dangerous for live-time features. If a model uses final duration, final `arrival_count`, or final `session_end_utc` while scoring the first or middle arrival, it has been given information from the future. The model would learn from a completed-session outcome that was not available at the time of decision.

## Why `arrival_count` is the clearest leakage field

`arrival_count` looks harmless because it is just a count. It is not harmless.

At live time, the count the platform can know is an as-of count: how many arrivals have occurred in this session up to the current event. The `arrival_count` in `s1_session_index_6B` is different. It is the final count after the session has ended.

For a session with `arrival_count = 3`, using that value on the first arrival tells the model that two more arrivals will happen later. For a session with `arrival_count = 1`, using that value on the first arrival tells the model that no later arrival will happen. Both are future knowledge. The single-arrival case is easy to overlook because the value is small, but it is still a completed-session fact.

So the problem is not only the `42.83M` multi-arrival sessions. The closure field exists on all `184.82M` session rows. The analytical rule is:

- final `arrival_count` is valid for offline reconstruction, labelling, case review, and post-hoc analysis
- final `arrival_count` is not valid as a live decision-time feature unless transformed into an as-of count from online state

## Why `session_end_utc` is also unsafe

`session_end_utc` has the same issue in timestamp form.

At session start, the platform can know the start time. It cannot know the final end time unless the session has already ended. If a live feature uses the final session end, final duration, or any derivative such as "session length" before closure, the feature leaks future session state.

For one-arrival sessions, `session_end_utc` equals `session_start_utc`. That is coherent after the fact. It is not a safe live signal at the moment of authorization because it says the session closes immediately. For multi-arrival sessions, the end timestamp can be many hours after the first arrival. The duration table shows approximate P95 duration of `62,417s` for two-arrival sessions and `78,217s` for `5+` sessions. Those end times are plainly unavailable at the beginning of the session.

So `session_end_utc` should be read as a session-closure timestamp. It is valuable offline, but it is not a live feature source.

## What remains useful for live-time reasoning

This does not mean sessions are useless to the live fraud platform. It means the final session index is the wrong object to use directly.

A live-safe session feature would need to be built as an online/as-of projection, for example:

- current known `session_id`
- session age so far
- arrivals seen so far in the current session
- time since previous arrival in the same session
- rolling amount or count up to the current event
- current merchant/account/device/session state as of the event timestamp

Those features are not the same as the final `arrival_count`, final duration, or final `session_end_utc` in `s1_session_index_6B`. The distinction is not technical pedantry. It is the difference between a model that could run honestly in the live fraud decisioning path and a model that only performs well because it sees the future.

The current branch does not verify whether such online session projections already exist elsewhere. It only classifies `s1_session_index_6B` itself.

## A small contract caution

The dataset dictionary description says the session index includes party/device/IP relationships and anchor metadata. The observed schema and parent export include `party_id`, `account_id`, `instrument_id`, `device_id`, and `merchant_id`, but not `ip_id`.

That means `s1_session_index_6B` should not be used as the sole source for session-IP analysis. IP context is available on `s1_arrival_entities_6B`, and any session-IP claim should be built by joining or grouping from arrival-grain context rather than assuming the session index directly carries IP.

This is not a blocker for the current branch, but it is a useful traceability note. The session index is a session closure surface, not a complete identity graph.

## What this surface can and cannot support

The session index can support:

- offline session reconstruction
- case review around completed sessions
- replay/debug context after the fact
- session-level exposure summaries
- post-hoc comparison of single-arrival and multi-arrival sessions
- offline training labels or features only when the modelling question explicitly allows completed-session knowledge

The session index cannot safely support:

- live RTDL features using final `arrival_count`
- live RTDL features using final `session_end_utc`
- live RTDL features using final session duration
- claims about real-time model behaviour unless features are rebuilt as as-of-time projections
- IP-session analytics without joining back to arrival entity context

The safe analytical wording is therefore not "session features are bad." The correct wording is "completed-session features are offline-only unless converted into live as-of features."

## Leads exposed by this branch

1. **As-of session feature branch.** If we later need live session features, the next question is how to derive online-safe versions such as arrivals-so-far and session-age-so-far.

2. **Session versus fraud branch.** The current branch does not join to truth products. A later branch can test whether fraud flows are more likely to sit in single-arrival or multi-arrival sessions, but it must state whether the view is offline-only.

3. **Session-IP bridge.** Since `s1_session_index_6B` does not directly carry `ip_id`, session-IP analysis should be built through `s1_arrival_entities_6B`.

4. **Session duration realism.** Multi-arrival sessions can span many hours, with upper bounds just under a day. That may be acceptable for the synthetic operating world, but it is a realism point worth remembering before making strong stakeholder claims about user session behaviour.

## Working conclusion

`s1_session_index_6B` is a coherent completed-session surface. It covers `184.82M` sessions, reconstructs `236.69M` arrivals through `arrival_count`, has no required-field missingness, and has no negative durations. It is therefore useful for offline reconstruction, case review, replay, and post-hoc session analytics.

It is not live-safe as a direct feature source. The fields that make it analytically useful, especially `arrival_count`, `session_end_utc`, and final duration, are closure fields. They tell us what the session became after completion, not what the platform could know at the moment of authorization.

The practical rule for the fraud decisioning platform is simple: use `session_id` and online-maintained as-of session state in live paths; use `s1_session_index_6B` for offline reconstruction and completed-session analysis. Mixing those two would create temporal leakage and would overstate what the live system could honestly know.
