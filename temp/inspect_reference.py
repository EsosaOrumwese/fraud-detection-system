from pathlib import Path
import polars as pl

root = Path(r'c:/Users/LEGION/Documents/Data Science/Python & R Scripts/fraud-detection-system')

# GDP dataset stats
gdp_path = root / 'reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet'
gdp = pl.read_parquet(gdp_path)
print('GDP rows:', gdp.height)
print('GDP distinct ISO:', gdp.select(pl.col('country_iso').n_unique()).item())
print('GDP null counts:', gdp.null_count().to_dict())
print('GDP year min/max:', gdp.select([
    pl.col('observation_year').min().alias('min_year'),
    pl.col('observation_year').max().alias('max_year')
]).to_dicts())

# Merchant dataset stats
merch_path = root / 'reference/layer1/transaction_schema_merchant_ids/v2025-10-07/transaction_schema_merchant_ids.parquet'
merch = pl.read_parquet(merch_path)
print('Merchants rows:', merch.height)
print('Merchants distinct ISO:', merch.select(pl.col('home_country_iso').n_unique()).item())
counts = merch.group_by('home_country_iso').len()
per_iso = counts['len']
print('Merchants per ISO min/max:', int(per_iso.min()), int(per_iso.max()))
print('Channel distribution:', merch.group_by('channel').len().to_dicts())
