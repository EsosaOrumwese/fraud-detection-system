# Notes on this issue

## Design decisions (capture in ADR)
| Topic                        | Options                                                   | Recommended                                                                                |
|------------------------------|-----------------------------------------------------------|--------------------------------------------------------------------------------------------|
| **Currency**                 | AWS Budgets *always* stores in USD; display can show GBP. | Set limit **40** *“GBP”* in UI; Terraform `limit_amount = "40"` and comment the FX quirk.  |
| **Budget period**            | Monthly vs Quarterly vs Annually                          | **MONTHLY**, start of current month – matches pay cycle.                                   |
| **Alert channels**           | SNS email, Slack via webhook, SMS.                        | **SNS email** for sprint; can extend with Slack subscription later.                        |
| **Billing alarm duplicate?** | Budget alone vs add CloudWatch metrics alarm.             | Add **Billing alarm @ £40** — minimal extra cost, real-time.                               |
| **IAM policy**               | Who can publish to topic?                                 | Topic policy grants `sns:Publish` to `budgets.amazonaws.com` & `cloudwatch.amazonaws.com`. |
| **Delete protection**        | Leave default (*false*) vs enable.                        | **false** in sandbox (allows `terraform destroy`).                                         |

## Implementation steps
| Step                            | Command                                                                | Expected screen hint                                       |
|---------------------------------|------------------------------------------------------------------------|------------------------------------------------------------|
| 1. Create SNS topic             | Write `aws_sns_topic` in `budgets.tf`; `terraform plan`                | `+ aws_sns_topic.budget_alert`                             |
| 2. Add e-mail subscription      | `aws_sns_topic_subscription`                                           | Plan shows `endpoint = "your@email.com"`                   |
| 3. **Manually verify** e-mail   | AWS sends “Confirm subscription” → click link.                         | Console shows *confirmed*.                                 |
| 4. Budget resource              | `aws_budgets_budget` with two `notification` blocks (`30`, `60`, `90`) | Plan +3 resources including budget.                        |
| 5. Topic policy doc             | `aws_sns_topic_policy` referencing ARNs                                | If you forget, budget creation fails w `400 AccessDenied`. |
| 6. CloudWatch alarm             | Region us-east-1 provider alias; metric `AWS/Billing`, threshold `40`  | Plan +1 alarm; message includes topic ARN.                 |
| 7. `terraform apply`            | Should take \~15 s.                                                    | CLI prints “Apply complete! Resources: 5 added.”           |
| 8. **Manual test** (optional)   | In AWS Budgets console → *Edit* → “Send test alert”.                   | E-mail arrives within 1 min.                               |
| 9. `terraform destroy` (sanity) | Everything deletes cleanly.                                            | Budget deletion can take 1-2 m; no orphan SNS topic.       |

## What is Amazon SNS?
Amazon Simple Notification Service (Amazon SNS) is a fully managed service that provides message delivery from publishers (producers) to subscribers (consumers). Publishers communicate asynchronously with subscribers by sending messages to a topic, which is a logical access point and communication channel.

### How it works

In SNS, publishers send messages to a topic, which acts as a communication channel. The topic acts as a logical access point, ensuring messages are delivered to multiple subscribers across different platforms.

Subscribers to an SNS topic can receive messages through different endpoints, depending on their use case, such as:
* Amazon SQS
* Lambda
* HTTP(S) endpoints
* Email
* Mobile push notifications
* Mobile text messages (SMS)
* Amazon Data Firehose
* Service providers (For example, Datadog, MongoDB, Splunk)

SNS supports both Application-to-Application (A2A) and Application-to-Person (A2P) messaging, giving flexibility to send messages between different applications or directly to mobile phones, email addresses, and more.

<img src=https://docs.aws.amazon.com/images/sns/latest/dg/images/sns-delivery-protocols.png width="500" height="500"  alt="img"/>


## What is an SNS Topic?
An Amazon SNS topic is a logical access point that acts as a communication channel. A topic lets you group multiple endpoints (such as AWS Lambda, Amazon SQS, HTTP/S, or an email address).

To broadcast the messages of a message-producer system (for example, an e-commerce website) working with multiple other services that require its messages (for example, checkout and fulfillment systems), you can create a topic for your producer system.

The first and most common Amazon SNS task is creating a topic. This page shows how you can use the AWS Management Console, the AWS SDK for Java, and the AWS SDK for .NET to create a topic.

## Approach
Below is a **reinforced mentoring play-book** for **CST-01**—the same “extra-scaffolding” style you liked for IAC-01.
Follow it line-by-line and someone who has never touched FinOps or Budgets will still turn in a deliverable that impresses senior platform-engineers.

---

### 0 · What “stuns” senior cloud & FinOps folks

| Wow-factor                                       | Why they care                                                                     |
|--------------------------------------------------|-----------------------------------------------------------------------------------|
| **Dual guard-rail** (Budget *and* Billing Alarm) | Budget e-mails can lag; CloudWatch alarm fires near-real-time.                    |
| **Named SNS topic + strict policy**              | Shows you understand *who* may publish and *why*—least-privilege even for alerts. |
| **Two threshold tiers (60 %, 90 %)**             | Gives teams time to react before a hard stop.                                     |
| **Currency clarity & FX note**                   | Budgets store in USD internally; explaining the quirk shows depth.                |
| **Delete-safe but DRY Terraform**                | `terraform destroy` leaves no orphan pieces; variables, not copy-paste.           |

Strive to hit every bullet.

---

### 1 · Pre-flight study list (≈ 45 min)

| Link                                                    | Sections to read ↷            | Bullet you must capture in notes                                                                            |
|---------------------------------------------------------|-------------------------------|-------------------------------------------------------------------------------------------------------------|
| **AWS Budgets User Guide**                              | “Cost budget → Notifications” | `threshold_type` can be `PERCENTAGE` or `ABSOLUTE`; values are *numbers*, not strings.                      |
| **Terraform `aws_budgets_budget` doc**                  | “Notification” block          | Each notification needs `comparison_operator`, `threshold`, `threshold_type`, ***and*** an `sns_topic_arn`. |
| **AWS Billing & Cost Mgmt → CloudWatch Billing alarms** | Entire page (short)           | Billing metrics exist **only in us-east-1**; they’re global for the account.                                |
| **Terraform `aws_cloudwatch_metric_alarm` doc**         | Arguments table               | `namespace = "AWS/Billing"`, `metric_name = "EstimatedCharges"`; dimension `Currency = GBP or USD`.         |
| **SNS Developer Guide**                                 | “Access control”              | Topic policy must allow the two AWS services to publish.                                                    |
| **tfsec rule set → AWS → SNS**                          | quick scan                    | Learn which HIGH severities apply to topics.                                                                |

> Dump concise bullets into `/docs/references/CST-01_notes.md` so you have sources when writing ADR-0004.

---

### 2 · Decisions to lock in (write ADR-0004)

| Decision                | Choice (& why)                                                                                             |
|-------------------------|------------------------------------------------------------------------------------------------------------|
| **Budget period**       | `MONTHLY`, starting first day of month. Maps to your pay cycle & AWS default.                              |
| **Currency display**    | Input limit `50` with unit `GBP`. Note in ADR that AWS stores USD internally but honours display currency. |
| **Thresholds**          | 60 % & 90 % (percentage) – early and late warning.                                                         |
| **Alert channel**       | SNS e-mail (simple, no token). Slack can be added later via subscription.                                  |
| **Billing alarm**       | Duplicate at 100 % (50 GBP) for near-real-time alert.                                                      |
| **Encryption on topic** | Skip KMS for now to avoid extra cost, explain trade-off; tfsec MEDIUM accepted.                            |
| **Delete-protection**   | Keep default `false` in sandbox to allow `terraform destroy`.                                              |

---

### 3 · Repo prep (10 min)

1. Create new TF files:

```
infra/terraform/
├── budgets.tf      # AWS Budget + SNS
└── alarms.tf       # CloudWatch Billing alarm
```

2. Extend `variables.tf`:

```hcl
variable "alert_email" {
  description = "Primary FinOps alert recipient"
  type        = string
}
variable "monthly_budget_gbp" {
  description = "Cost ceiling for sandbox"
  type        = number
  default     = 50
}
```

Add your email in `terraform.tfvars` (git-ignored).

---

### 4 · Incremental build (with **expected CLI output**)

#### 4.1 SNS Topic + Subscription (15 min)

```hcl
resource "aws_sns_topic" "budget_alerts" {
  name = "fraud-budget-alerts"
}

resource "aws_sns_topic_subscription" "email_primary" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
```

**Terminal checkpoints**

```bash
terraform init
terraform plan
```

Expected lines (abbrev.):

```
+ aws_sns_topic.budget_alerts
+ aws_sns_topic_subscription.email_primary
Plan: 2 to add.
```

Apply → check e-mail inbox → **Confirm subscription** → Console shows *Confirmed*.

#### 4.2 Topic policy (5 min)

```hcl
data "aws_iam_policy_document" "budget_topic_policy" {
  statement {
    sid = "AllowBudgetAndCWPublish"
    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com", "cloudwatch.amazonaws.com"]
    }
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.budget_alerts.arn]
  }
}

resource "aws_sns_topic_policy" "budget_topic_access" {
  arn    = aws_sns_topic.budget_alerts.arn
  policy = data.aws_iam_policy_document.budget_topic_policy.json
}
```

`terraform plan` should now add **+1** policy resource.

> **Fail-fast clue:** If you skip this, the Budget resource will error “AccessDenied – cannot publish to topic”.

#### 4.3 AWS Budget resource (20 min)

```hcl
resource "aws_budgets_budget" "monthly_cost" {
  name              = "fraud-sbx-monthly"
  budget_type       = "COST"
  limit_amount      = var.monthly_budget_gbp              # 50
  limit_unit        = "GBP"
  time_unit         = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 60
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 90
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
  }
}
```

**Plan output** should include `+ aws_budgets_budget.monthly_cost`.

#### 4.4 CloudWatch Billing alarm (us-east-1) (15 min)

Add provider alias:

```hcl
provider "aws" {
  alias  = "us"
  region = "us-east-1"
}
```

Then alarm resource:

```hcl
resource "aws_cloudwatch_metric_alarm" "billing_100pct" {
  provider         = aws.us
  alarm_name       = "fraud-sbx-billing-50gbp"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  statistic           = "Maximum"
  threshold           = var.monthly_budget_gbp
  dimensions = {
    Currency = "GBP"
  }
  alarm_actions = [aws_sns_topic.budget_alerts.arn]
}
```

`terraform plan` ⇒ **+1** new alarm.

#### 4.5 Apply & verify

```bash
terraform apply -auto-approve
```

Expected final line:

```
Apply complete! Resources: 5 added, 0 changed, 0 destroyed.
```

Console: **Budgets → cost budgets** shows “fraud-sbx-monthly”.
Click *Send test alert* → e-mail arrives within 1 min.

---

### 5 · Tests & CI

1. **`pre-commit run --all-files`** ⇒ should re-format `.tf` files (indent, sort).
2. Push branch → **GitHub Actions**: lint → tfsec / Checkov.

   * tfsec MEDIUM: “SNS Topic not encrypted” → accept or suppress with comment:

   ```hcl
   #tfsec:ignore:AWS016  # encryption is optional for e-mail topics, documented in ADR-0004
   resource "aws_sns_topic" "budget_alerts" { … }
   ```

---

### 6 · Definition-of-Done (Sprint-01 checklist)

* [ ] Budget limit **£50** + two percentage notifications.
* [ ] SNS topic confirmed; e-mail test reached inbox (screenshot).
* [ ] CloudWatch alarm exists (us-east-1) & targets same topic.
* [ ] ADR-0004 explains currency quirk, encryption trade-off, deletion rationale.
* [ ] tfsec / Checkov: **0 HIGH**, **≤ 1 MEDIUM** (documented).
* [ ] PR merged; **CST-01** card → **Done**.

---

### 7 · Common pitfalls & self-diagnosis

| Error / Symptom                               | Probable cause                                          | Fix                                                     |
|-----------------------------------------------|---------------------------------------------------------|---------------------------------------------------------|
| Budget apply fails `PermissionDenied`         | Topic policy missing `budgets.amazonaws.com` publisher. | Add policy doc (Section 4.2).                           |
| SNS subscription stuck *Pending confirmation* | Didn’t click verify link.                               | Find AWS e-mail, click *Confirm subscription*, re-plan. |
| Billing alarm throws `SNS topic not found`    | Used default provider (EU) instead of us-east-1.        | Add provider alias, reference it.                       |
| tfsec HIGH: “Budget has no notifications”     | Misspelled `notification` block.                        | Ensure two blocks with correct fields.                  |

---

### 8 · Level-up extras (choose if buffer hours remain)

| Extra                    | Effort | Senior-level shine                                                     |
|--------------------------|--------|------------------------------------------------------------------------|
| **Infracost comment**    | 10 min | PR shows cost delta vs budget in £.                                    |
| **SMS alert**            | 5 min  | Add phone subscription; shows multi-channel awareness.                 |
| **KMS-encrypted SNS**    | 15 min | Satisfies tfsec rule AWS016; teaches KMS policy nuances.               |
| **Cost Allocation Tags** | 10 min | Turn on “project=fraud” tag → later, Cost Explorer reports by project. |

---

### 9 · Reflection prompts (journal answers)

1. *Why does CloudWatch Billing alarm lag ≤ 2 h whereas Budgets lag ≤ 8 h?*
2. *Under what circumstances would you move alerts into an Org-wide “management” account instead of the workload account?*
3. *What trade-offs exist in leaving SNS unencrypted for public e-mail vs encrypting with KMS?*
4. *How would you auto-shut-off non-prod SageMaker endpoints if the 90 % threshold triggers?*

---

#### Next move for you

1. Follow Sections 1–4, capturing screenshots of test e-mails & console budget.
2. Commit, open PR → CI green.
3. Move **CST-01** to **Done** and note the wins in `/docs/sprint-reports/Sprint-01.md`.
4. Tag me here when merged; I’ll drop a concise reference implementation in the next response, then we pivot to **DAT-01** (synthetic schema design).













