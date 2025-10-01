# Mid-Level Architecture of Sections

## 1. Entry & Configuration
```text
                             ┌──────────────────────────────────────────────┐
                             │ generate.py (legacy entrypoint)              │
                             │ ── imports:                                  │
                             │    • core.generate_dataframe                 │
                             │    • core.write_parquet                      │
                             │    • cli.main as _cli_main                   │
                             │ ── if __name__ == "__main__":                │
                             │       call _cli_main()                       │
                             └─────────────────┬────────────────────────────┘
                                               │
                                               ▼
                             ┌───────────────────────────────────────────────┐
                             │ cli.py → main()                               │
                             │                                               │
                             │ 1) Argument parsing via argparse:             │
                             │    --config <path>                            │
                             │    --s3                                       │
                             │    --log-level <LEVEL>                        │
                             │    --num-workers <int>                        │
                             │    --batch-size <int>                         │
                             │    --realism <v1|v2>                          │
                             │                                               │
                             │ 2) Logging setup:                             │
                             │    logging.basicConfig(                       │
                             │      level=getattr(logging, args.log_level),  │
                             │      format="%(asctime)s %(levelname)s …"     │
                             │    )                                          │
                             │                                               │
                             │ 3) Load & validate YAML config:               │
                             │    cfg = load_config(args.config)             │
                             │      └─ config.py:                            │
                             │         • check file exists                   │
                             │         • yaml.safe_load()                    │
                             │         • GeneratorConfig.model_validate()    │
                             │         • return GeneratorConfig instance     │
                             │                                               │
                             │ 4) Apply CLI overrides to cfg:                │
                             │    if args.num_workers → cfg.num_workers      │
                             │    if args.batch_size → cfg.batch_size        │
                             │    if args.realism  → cfg.realism             │
                             │                                               │
                             │ 5) Determine upload flag:                     │
                             │    do_upload = args.s3 or cfg.s3_upload       │
                             │                                               │
                             │ 6) Log runtime settings (rows, rate, seed)    │
                             │                                               │
                             │ 7) Delegate to core:                          │
                             │    core.generate_dataframe(cfg)               │
                             └───────────────────────────────────────────────┘
```
---

## 2. Catalog Preparation
```text
                              ┌───────────────────────────────────────────┐
                              │          Catalog Preparation              │
                              └───────────────────┬───────────────────────┘
                                                  │
                                                  ▼
                                          ┌───────────────────┐
                                          │ Read cfg.catalog  │
                                          │ (CatalogConfig:   │
                                          │  num_customers,   │
                                          │  num_merchants,   │
                                          │  num_cards,       │
                                          │  Zipf exponents,  │
                                          │  risk α/β, sizes) │
                                          └─────────┬─────────┘
                                                    │
                                                    ▼
                               ┌────────────────────┴───────────────────┐
                               │ cfg.realism == "v2"?                   │
                               └───────────────┬────────────────────────┘
                                               │
                           ┌───────────Yes──────▼───────No───────────┐
                           │                                         │
               ┌───────────▼──────────┐                ┌─────────────▼───────────┐
               │ write_catalogs(dir,  │                │ Skip pre-build;         │
               │   cfg)               │                │ defer to per-chunk      │
               │ • generate_*_catalog │                │ catalog generation in   │
               │   (customer,…)       │                │ _generate_chunk()       │
               │ • write Parquet      │                └─────────────────────────┘
               │   (Snappy, row-group)│
               │ • enforce max_size_mb│
               └───────────┬──────────┘
                           │
                           ▼
               ┌───────────┴───────────┐
               │ load_catalogs(dir)    │
               │ • read customers.parq │
               │   merchants.parq      │
               │   cards.parq          │
               │ • return (cust_df,    │
               │   merch_df, card_df)  │
               └───────────┬───────────┘
                           │
                           ▼
               ┌───────────┴──────────┐
               │ Pool initializer     │
               │ _init_worker(cust,   │
               │  merch, card)        │
               │ • assign module      │
               │   globals (_CUST_CAT,│
               │   _MERCH_CAT,        │
               │   _CARD_CAT)         │
               └──────────────────────┘

```
---

## 3. Transaction Assembly
```text
                                  ┌───────────────────────────────────┐
                                  │ core.generate_dataframe(cfg)      │
                                  └────────────────────┬──────────────┘
                                                       │
                        ┌──────────────────────────────▼──────────────────────────────┐
                        │                Is cfg.num_workers > 1?                      │
                        └────────────────────────────────┬────────────────────────────┘
                                                         │
                                       ┌────────Yes──────▼───────No───────────┐
                                       │                                      │
             ┌─────────────────────────▼─────────────────────────┐        ┌───▼──────────────────────────┐
             │ Parallel Mode: use multiprocessing.Pool           │        │ Single-Process Mode:         │
             │ - Compute chunk args list: (chunk_size, cfg, seed)│        │ - Optionally set globals     │
             │ - Pool.imap_unordered(_chunk_worker, args)        │        │ - Call                       │
             │                                                   │        │   _generate_chunk(total_rows,│
             │                                                   │        │          cfg, cfg.seed)      │
             └─────────────────────────┬─────────────────────────┘        └──────────────────────────────┘
                                       │
        ┌──────────────────────────────▼─────────────────────────────────────────────────┐
        │ Collect each returned chunk DataFrame into list `dfs`, then:                   │
        │   df = pl.concat(dfs, rechunk=False)                                           │
        └────────────────────────────────────────────────────────────────────────────────┘

                     Detailed per-chunk pipeline in _generate_chunk(chunk_rows, cfg, seed)

┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1) Seed setup: unpack cfg.temporal.start_date/end_date; seed Python random, Faker, and NumPy RNGs │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2) Timestamp sampling:                                                                            │
│    timestamps = sample_timestamps(chunk_rows, start_date, end_date, seed)                         │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3) Catalog access:                                                                                │
│    if cfg.realism == "v2" and globals loaded: use preloaded _CUST_CAT, _MERCH_CAT, _CARD_CAT      │
│    else: regenerate catalogs via generate_customer_catalog, generate_merchant_catalog,            │
│          generate_card_catalog with seeded parameters                                             │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4) Entity sampling:                                                                               │
│    cust_ids, merch_ids, card_ids = sample_entities(catalog_df, entity_col, chunk_rows, seed)      │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 5) Risk extraction:                                                                               │
│    m_risk = _MERCH_CAT['risk'][merch_ids]; c_risk = _CARD_CAT['risk'][card_ids]                   │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 6) Numeric features:                                                                              │
│    time_offset = rng.integers(-720, +840, size=chunk_rows)                                        │
│    amount = sample per cfg.feature.amount_distribution (lognormal/normal/uniform) rounded         │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 7) Categorical features:                                                                          │
│    device_type, card_scheme, channel, pos_entry_mode, is_recurring drawn vectorized               │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 8) Geo & currency:                                                                                │
│    sample country_code; currency from Eurozone list; mcc_code lookup from merchant catalog        │
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 9) Ancillary IDs:                                                                                 │
│    pan_hash from card catalog; latitude & longitude arrays; transaction_id = UUID4 array          │
│    device_id: ~90% UUID4, rest None; ip_address & user_agent from Faker pools                     │ 
├───────────────────────────────────────────────────────────────────────────────────────────────────┤
│10) DataFrame assembly:                                                                            │
│    return pl.DataFrame({ all generated arrays mapped to schema fields })                          │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘

```
---

## 4. Labeling
```text
                              ┌────────────────────────────────────┐
                              │ labeler.py: label_fraud(df, fr, s) │
                              └───────────────┬────────────────────┘
                                              │                                              
                   ┌──────────────────────────▼───────────────────┐
                   │ Extract N=df.height and arrays:              │
                   │   • amount, merch_risk, card_risk            │
                   │   • timestamps (ns since epoch)              │
                   └──────────────────────────┬───────────────────┘
                                              │
                   ┌──────────────────────────▼───────────────────┐
                   │ Compute logistic probabilities:              │
                   │   intercept = log(fr/(1–fr))                 │
                   │   logit = intercept                          │
                   │     + w_amount·log(amount+1)                 │
                   │     + w_mrisk·merch_risk                     │
                   │     + w_crisk·card_risk                      │
                   │     + w_night·(hour<6)                       │
                   │   p = expit(logit)                           │
                   │   labels = rng.binomial(p)                   │
                   └──────────────────────────┬───────────────────┘
                                              │
                   ┌──────────────────────────▼───────────────────┐
                   │ Compare to target count:                     │
                   │   target = round(fr·N)                       │
                   │   actual = sum(labels)                       │
                   └──────────────────────────┬───────────────────┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    │                                                   │
      ┌─────────────▼───────────────────┐                    ┌──────────▼─────────────────────┐
      │ Overshoot? (actual > target)    │                    │ Undershoot? (actual < target)  │
      └───────────────┬─────────────────┘                    └──────────────┬─────────────────┘
                      │                                                     │
    ┌─────────────────▼────────────────────┐             ┌──────────────────▼────────────────────┐
    │ Overshoot correction:                │             │ Burst‐clustering correction:          │
    │   excess = actual – target           │             │   missing = target – actual           │
    │   pick ‘excess’ True labels at       │             │   num_waves = max(1, missing//bf)     │
    │     random via rng.choice            │             │   for each wave:                      │
    │   set those labels to False          │             │     sample wave time wt               │
    │                                      │             │     sample merchant wm by m_risk      │
    └──────────────────────────────────────┘             │     find candidates within ±window    │
                                                         │     if ≥bf: label bf of them          │
                                                         │      else: label all + fill shortfall │
                                                         └─────────────────────┬─────────────────┘
                                                                               │
                                                     ┌─────────────────────────▼───────────┐
                                                     │ Final fallback if still short:      │
                                                     │   label randomly among remaining    │
                                                     └────────────────────────┬────────────┘
                                                                              │
                                                     ┌────────────────────────▼────────────┐
                                                     │ Attach array as df['label_fraud']   │
                                                     │ Return augmented DataFrame          │
                                                     └─────────────────────────────────────┘

```
---

## 5. Post-processing & Delivery
```text
                              ┌───────────────────────────────────────────┐
                              │ core.generate_dataframe(cfg)              │
                              │ └─> returns full Polars DataFrame (df)    │
                              └──────────────────────┬────────────────────┘
                                                     │
                                                     ▼
                              ┌───────────────────────────────────────────┐
                              │              cli.py:main()                │
                              │              receives df                  │
                              └──────────────────────┬────────────────────┘
                                                     │
                                                     ▼
         ┌──────────────────────────────────────────────────────────────────┐
         │ Schema Enforcement & Column Casting                              │
         │ - Load _POLARS_SCHEMA and _COLUMNS from schema YAML              │
         │ - df = df.with_columns([pl.col(c).cast(_POLARS_SCHEMA[c]) ...])  │
         │ - df = df.select(_COLUMNS)                                       │
         └──────────────────────────────────────────────────────────────────┘
                                                     │
                                                     ▼
         ┌──────────────────────────────────────────────────────────────────┐
         │ Local Parquet Output                                             │
         │ - today = date.today(); year, month = today.year, pad(month)     │
         │ - local_dir = cfg.out_dir/"payments"/"year=…"/"month=…"          │
         │ - filename = f"payments_{rows}_{today.isoformat()}.parquet"      │
         │ - write_parquet(df, local_dir/filename) → returns file Path      │
         └──────────────────────────────────────────────────────────────────┘
                                                     │
                                                     ▼
         ┌──────────────────────────────────────────────────────────────────┐
         │ Optional S3 Upload (if args.s3 or cfg.s3_upload)                 │
         │ - s3 = boto3.client("s3")                                        │
         │ - bucket ← get_param("/fraud/raw_bucket_name")                   │
         │ - tx_key = "payments/year=…/month=…/filename"                    │
         │ - s3.upload_file(local_path, bucket, tx_key)                     │
         │ - if realism=="v2":                                              │
         │     for each *.parquet in cfg.out_dir/"catalog":                 │
         │       upload to artifacts bucket under "catalogues/"             │
         └──────────────────────────────────────────────────────────────────┘
                                                     │
                                                     ▼
         ┌──────────────────────────────────────────────────────────────────┐
         │ Error Handling & Exit Codes                                      │
         │ - try: write_parquet & (optional) s3.upload_file                 │
         │ - except ClientError: log “S3 upload failed”; sys.exit(2)        │
         │ - except Exception: log traceback; sys.exit(1)                   │
         └──────────────────────────────────────────────────────────────────┘
```
