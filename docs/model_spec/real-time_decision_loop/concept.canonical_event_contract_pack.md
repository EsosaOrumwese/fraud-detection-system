Here's still another conceptual doc meant to align the contracts in the components within real-time decision loop and the ingestion gate

## What changed from v0 → v1 (tightening)

* `contract_version` bumps to **`rt_canonical_events_v1`**
* `decision_made.payload.provenance` is now a **strict, explicit schema** (DL + OFP + IEG + DF stage/timing + errors)
* `action_intent` / `action_outcome` payloads are now fully pinned to the v0 Actions contract shapes
* `transaction_event` now **requires** `observed_identifiers[]` at the envelope level (so IEG/OFP update consumers can stay envelope-driven)

---

## v1 JSON Schema (single file)

Save as: `contracts/rt_canonical_events_v1.schema.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "rt_canonical_events_v1.schema.json",
  "title": "Real-Time Canonical Event Contract Pack v1",
  "type": "object",

  "$defs": {
    "UtcTimestamp": { "type": "string", "format": "date-time" },

    "ContextPins": {
      "type": "object",
      "additionalProperties": false,
      "required": ["scenario_id", "run_id", "manifest_fingerprint", "parameter_hash"],
      "properties": {
        "scenario_id": { "type": "string" },
        "run_id": { "type": "string" },
        "manifest_fingerprint": { "type": "string" },
        "parameter_hash": { "type": "string" }
      }
    },

    "ObservedIdentifier": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id_kind", "id_value"],
      "properties": {
        "id_kind": { "type": "string" },
        "id_value": { "type": "string" },
        "namespace": { "type": "string" }
      }
    },

    "ProducerRef": {
      "type": "object",
      "additionalProperties": false,
      "required": ["producer_component", "produced_at_utc"],
      "properties": {
        "producer_component": {
          "type": "string",
          "enum": [
            "ingestion_gate",
            "degrade_ladder",
            "decision_fabric",
            "actions_layer",
            "decision_log_audit"
          ]
        },
        "produced_at_utc": { "$ref": "#/$defs/UtcTimestamp" },
        "producer_instance_id": { "type": "string" }
      }
    },

    "Causation": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "causation_event_id": { "type": "string" },
        "correlation_id": { "type": "string" }
      }
    },

    "PayloadKind": {
      "type": "string",
      "enum": [
        "transaction_event",
        "degrade_decision",
        "decision_made",
        "action_intent",
        "action_outcome"
      ]
    },

    "DecisionOutcome": {
      "type": "string",
      "enum": ["APPROVE", "DECLINE", "STEP_UP", "REVIEW"]
    },

    "KeyType": {
      "type": "string",
      "enum": ["account", "card", "customer", "merchant", "device"]
    },

    "FeatureKey": {
      "type": "object",
      "additionalProperties": false,
      "required": ["key_type", "key_id"],
      "properties": {
        "key_type": { "$ref": "#/$defs/KeyType" },
        "key_id": { "type": "string" }
      }
    },

    "FeatureGroupVersion": {
      "type": "object",
      "additionalProperties": false,
      "required": ["group_name", "group_version"],
      "properties": {
        "group_name": { "type": "string" },
        "group_version": { "type": "string" }
      }
    },

    "FreshnessBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["group_name", "group_version", "ttl_seconds", "stale"],
      "properties": {
        "group_name": { "type": "string" },
        "group_version": { "type": "string" },
        "ttl_seconds": { "type": "integer", "minimum": 0 },
        "last_update_event_time": { "$ref": "#/$defs/UtcTimestamp" },
        "age_seconds": { "type": "integer", "minimum": 0 },
        "stale": { "type": "boolean" }
      }
    },

    "WatermarkBasis": {
      "type": "object",
      "additionalProperties": { "type": "integer", "minimum": 0 }
    },

    "InputBasis": {
      "type": "object",
      "additionalProperties": false,
      "required": ["stream_name", "watermark_basis"],
      "properties": {
        "stream_name": { "type": "string" },
        "watermark_basis": { "$ref": "#/$defs/WatermarkBasis" }
      }
    },

    "GraphVersion": {
      "type": "object",
      "additionalProperties": false,
      "required": ["graph_version", "stream_name", "watermark_basis"],
      "properties": {
        "graph_version": { "type": "string" },
        "stream_name": { "type": "string" },
        "watermark_basis": { "$ref": "#/$defs/WatermarkBasis" }
      }
    },

    "DegradeMode": {
      "type": "string",
      "enum": ["NORMAL", "DEGRADED_1", "DEGRADED_2", "FAIL_CLOSED"]
    },

    "ActionPosture": {
      "type": "string",
      "enum": ["NORMAL", "STEP_UP_ONLY"]
    },

    "CapabilityMask": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "allow_ieg",
        "allowed_feature_groups",
        "allow_model_primary",
        "allow_model_stage2",
        "allow_fallback_heuristics",
        "action_posture"
      ],
      "properties": {
        "allow_ieg": { "type": "boolean" },
        "allowed_feature_groups": {
          "type": "array",
          "items": { "type": "string" }
        },
        "allow_model_primary": { "type": "boolean" },
        "allow_model_stage2": { "type": "boolean" },
        "allow_fallback_heuristics": { "type": "boolean" },
        "action_posture": { "$ref": "#/$defs/ActionPosture" }
      }
    },

    "Trigger": {
      "type": "object",
      "additionalProperties": false,
      "required": ["signal_name", "comparison", "triggered_at_utc"],
      "properties": {
        "signal_name": { "type": "string" },
        "observed_value": {},
        "threshold": {},
        "comparison": { "type": "string" },
        "triggered_at_utc": { "$ref": "#/$defs/UtcTimestamp" }
      }
    },

    "ActionType": {
      "type": "string",
      "enum": [
        "APPROVE_TRANSACTION",
        "DECLINE_TRANSACTION",
        "STEP_UP_AUTH",
        "QUEUE_CASE"
      ]
    },

    "OutcomeStatus": {
      "type": "string",
      "enum": ["SUCCEEDED", "FAILED"]
    },

    "ActionIntentLite": {
      "type": "object",
      "additionalProperties": false,
      "required": ["action_type", "idempotency_key", "parameters"],
      "properties": {
        "action_type": { "$ref": "#/$defs/ActionType" },
        "idempotency_key": { "type": "string" },
        "parameters": { "type": "object" }
      }
    },

    "StageStatus": {
      "type": "string",
      "enum": ["ran", "skipped", "failed"]
    },

    "StageSummaryEntry": {
      "type": "object",
      "additionalProperties": false,
      "required": ["stage", "status"],
      "properties": {
        "stage": { "type": "string" },
        "status": { "$ref": "#/$defs/StageStatus" },
        "reason": { "type": "string" },
        "note": { "type": "string" }
      }
    },

    "TimingBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["started_at_utc", "ended_at_utc"],
      "properties": {
        "started_at_utc": { "$ref": "#/$defs/UtcTimestamp" },
        "ended_at_utc": { "$ref": "#/$defs/UtcTimestamp" }
      }
    },

    "ErrorAnnotation": {
      "type": "object",
      "additionalProperties": false,
      "required": ["error_code", "message", "retryable"],
      "properties": {
        "error_code": { "type": "string" },
        "message": { "type": "string" },
        "retryable": { "type": "boolean" }
      }
    },

    "OFPUsedBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["used"],
      "properties": {
        "used": { "type": "boolean" },

        "feature_snapshot_hash": { "type": "string" },
        "feature_keys_used": {
          "type": "array",
          "items": { "$ref": "#/$defs/FeatureKey" }
        },
        "group_versions_used": {
          "type": "array",
          "items": { "$ref": "#/$defs/FeatureGroupVersion" }
        },
        "freshness": {
          "type": "array",
          "items": { "$ref": "#/$defs/FreshnessBlock" }
        },
        "input_basis": { "$ref": "#/$defs/InputBasis" },

        "reason": { "type": "string" }
      },
      "allOf": [
        {
          "if": { "properties": { "used": { "const": true } } },
          "then": {
            "required": [
              "feature_snapshot_hash",
              "feature_keys_used",
              "group_versions_used",
              "freshness",
              "input_basis"
            ]
          },
          "else": { "required": ["reason"] }
        }
      ]
    },

    "IEGUsedBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["used"],
      "properties": {
        "used": { "type": "boolean" },
        "graph_version": { "$ref": "#/$defs/GraphVersion" },
        "reason": { "type": "string" }
      },
      "allOf": [
        {
          "if": { "properties": { "used": { "const": true } } },
          "then": { "required": ["graph_version"] },
          "else": { "required": ["reason"] }
        }
      ]
    },

    "DegradeUsedBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["degrade_mode", "capabilities_mask", "decided_at_utc", "triggers"],
      "properties": {
        "degrade_mode": { "$ref": "#/$defs/DegradeMode" },
        "capabilities_mask": { "$ref": "#/$defs/CapabilityMask" },
        "decided_at_utc": { "$ref": "#/$defs/UtcTimestamp" },
        "triggers": {
          "type": "array",
          "items": { "$ref": "#/$defs/Trigger" }
        },
        "degrade_decision_id": { "type": "string" }
      }
    },

    "DecisionProvenance": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "degrade",
        "ofp",
        "ieg",
        "df_policy_ref",
        "stage_summary",
        "timings",
        "as_of_time_utc"
      ],
      "properties": {
        "as_of_time_utc": { "$ref": "#/$defs/UtcTimestamp" },

        "degrade": { "$ref": "#/$defs/DegradeUsedBlock" },
        "ofp": { "$ref": "#/$defs/OFPUsedBlock" },
        "ieg": { "$ref": "#/$defs/IEGUsedBlock" },

        "df_policy_ref": { "type": "string" },

        "stage_summary": {
          "type": "array",
          "items": { "$ref": "#/$defs/StageSummaryEntry" }
        },

        "timings": { "$ref": "#/$defs/TimingBlock" },

        "error": { "$ref": "#/$defs/ErrorAnnotation" }
      }
    },

    "TransactionEventPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": ["txn_id", "amount_minor", "currency"],
      "properties": {
        "txn_id": { "type": "string" },
        "amount_minor": { "type": "integer" },
        "currency": { "type": "string" },
        "attributes": { "type": "object" }
      }
    },

    "DegradeDecisionPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": ["degrade_mode", "capabilities_mask", "decided_at_utc", "triggers"],
      "properties": {
        "degrade_mode": { "$ref": "#/$defs/DegradeMode" },
        "capabilities_mask": { "$ref": "#/$defs/CapabilityMask" },
        "decided_at_utc": { "$ref": "#/$defs/UtcTimestamp" },
        "triggers": {
          "type": "array",
          "items": { "$ref": "#/$defs/Trigger" }
        },
        "degrade_decision_id": { "type": "string" }
      }
    },

    "DecisionMadePayload": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "decision_id",
        "request_id",
        "stimulus_event_ref",
        "stimulus_event_time_utc",
        "stimulus_event_type",
        "decision_outcome",
        "actions",
        "provenance"
      ],
      "properties": {
        "decision_id": { "type": "string" },
        "request_id": { "type": "string" },

        "stimulus_event_ref": { "type": "string" },
        "stimulus_event_time_utc": { "$ref": "#/$defs/UtcTimestamp" },
        "stimulus_event_type": { "type": "string" },

        "decision_outcome": { "$ref": "#/$defs/DecisionOutcome" },

        "actions": {
          "type": "array",
          "items": { "$ref": "#/$defs/ActionIntentLite" }
        },

        "provenance": { "$ref": "#/$defs/DecisionProvenance" }
      }
    },

    "ActionIntentPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": ["decision_id", "request_id", "action_type", "idempotency_key", "parameters"],
      "properties": {
        "decision_id": { "type": "string" },
        "request_id": { "type": "string" },
        "action_type": { "$ref": "#/$defs/ActionType" },
        "idempotency_key": { "type": "string" },
        "parameters": { "type": "object" }
      }
    },

    "ActionOutcomePayload": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "decision_id",
        "request_id",
        "action_type",
        "idempotency_key",
        "attempt",
        "outcome_status",
        "started_at_utc",
        "ended_at_utc",
        "emitted_at_utc"
      ],
      "properties": {
        "decision_id": { "type": "string" },
        "request_id": { "type": "string" },

        "action_type": { "$ref": "#/$defs/ActionType" },
        "idempotency_key": { "type": "string" },
        "attempt": { "type": "integer", "minimum": 1 },

        "outcome_status": { "$ref": "#/$defs/OutcomeStatus" },

        "started_at_utc": { "$ref": "#/$defs/UtcTimestamp" },
        "ended_at_utc": { "$ref": "#/$defs/UtcTimestamp" },
        "emitted_at_utc": { "$ref": "#/$defs/UtcTimestamp" },

        "error_category": { "type": "string" },
        "retryable": { "type": "boolean" },
        "external_ref": {}
      },
      "allOf": [
        {
          "if": { "properties": { "outcome_status": { "const": "FAILED" } } },
          "then": { "required": ["error_category", "retryable"] }
        }
      ]
    },

    "CanonicalEventBase": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "kind",
        "contract_version",
        "payload_kind",
        "payload_version",
        "context_pins",
        "event_id",
        "event_time_utc",
        "ingest_time_utc",
        "producer",
        "payload"
      ],
      "properties": {
        "kind": { "const": "rt_event" },
        "contract_version": { "const": "rt_canonical_events_v1" },

        "payload_kind": { "$ref": "#/$defs/PayloadKind" },
        "payload_version": { "type": "string" },

        "context_pins": { "$ref": "#/$defs/ContextPins" },

        "event_id": { "type": "string" },
        "event_time_utc": { "$ref": "#/$defs/UtcTimestamp" },
        "ingest_time_utc": { "$ref": "#/$defs/UtcTimestamp" },

        "producer": { "$ref": "#/$defs/ProducerRef" },
        "causation": { "$ref": "#/$defs/Causation" },

        "observed_identifiers": {
          "type": "array",
          "items": { "$ref": "#/$defs/ObservedIdentifier" }
        },

        "extensions": { "type": "object" },

        "payload": { "type": "object" }
      }
    }
  },

  "allOf": [
    { "$ref": "#/$defs/CanonicalEventBase" },

    {
      "if": { "properties": { "payload_kind": { "const": "transaction_event" } } },
      "then": {
        "required": ["observed_identifiers"],
        "properties": { "payload": { "$ref": "#/$defs/TransactionEventPayload" } }
      }
    },
    {
      "if": { "properties": { "payload_kind": { "const": "degrade_decision" } } },
      "then": { "properties": { "payload": { "$ref": "#/$defs/DegradeDecisionPayload" } } }
    },
    {
      "if": { "properties": { "payload_kind": { "const": "decision_made" } } },
      "then": { "properties": { "payload": { "$ref": "#/$defs/DecisionMadePayload" } } }
    },
    {
      "if": { "properties": { "payload_kind": { "const": "action_intent" } } },
      "then": { "properties": { "payload": { "$ref": "#/$defs/ActionIntentPayload" } } }
    },
    {
      "if": { "properties": { "payload_kind": { "const": "action_outcome" } } },
      "then": { "properties": { "payload": { "$ref": "#/$defs/ActionOutcomePayload" } } }
    }
  ]
}
```

### v1 alignment notes (important)

* **Envelope `event_id`** is the unique ID of *this* emitted event instance.
* **Decision correlation** lives in payload fields (`decision_id`, `request_id`, plus `stimulus_event_ref/time/type` on `decision_made`). This avoids confusing envelope event_id with DF’s “request_id = stimulus event id” posture.
* EB offsets/partitions remain **outside** the envelope (in EB DeliveredRecord), preserving bus immutability.

