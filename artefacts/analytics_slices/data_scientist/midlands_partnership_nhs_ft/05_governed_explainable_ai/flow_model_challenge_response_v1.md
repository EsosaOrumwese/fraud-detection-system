# Flow Model Challenge Response v1

Why trust this score?
- the target is authoritative fraud truth
- feature and target source rules were pinned before training
- model choice and threshold choice were documented explicitly

Why not trust it blindly?
- it is bounded to one governed slice
- it supports prioritisation, not autonomous decisioning
- comparison-only bank-view signals remain excluded from target logic

Why this model?
- selected because the validation uplift materially exceeded the simpler baseline despite the added governance and explanation burden

When should humans override it?
- whenever case context or broader governance signals outweigh the bounded score
