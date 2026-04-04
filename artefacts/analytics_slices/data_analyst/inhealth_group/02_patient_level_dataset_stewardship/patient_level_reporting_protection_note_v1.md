# Patient-Level Reporting Protection Note v1

Protected downstream use:
- current-month reporting-safe summary for the InHealth `3.A` reporting lane

Protection result:
- the maintained dataset reproduces the current-month reporting lane exactly across `4/4` amount bands
- overall protected case-open rate: `9.63%`
- overall protected truth quality: `19.86%`

Why the maintained dataset matters:
- a direct join to the raw case timeline would work at the wrong grain
- the maintained dataset protects reporting by admitting one controlled case state per monthly flow record
