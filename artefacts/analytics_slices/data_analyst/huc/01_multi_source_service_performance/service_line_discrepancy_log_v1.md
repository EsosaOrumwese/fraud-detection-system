# Service Line Discrepancy Log v1

## Issue 1
- issue: bank-view outcome logic materially disagrees with authoritative truth on case-opened flows
- likely cause: bank view is an operational comparison surface rather than the authoritative outcome-quality source
- affected KPI: outcome quality
- severity: high
- action: use authoritative truth as the only outcome-quality KPI source

## Issue 2
- issue: the highest-conversion amount segment returns weaker authoritative truth quality than lower-amount segments
- likely cause: escalation into case work is not tightly aligned with outcome quality in that segment
- affected KPI: conversion into case work, outcome quality
- severity: medium
- action: review escalation or review rules for the higher-amount segment
