import random
from datetime import datetime, timedelta
from typing import List, Dict
from fraud_detection.simulator.config import GeneratorConfig
from fraud_detection.simulator.catalogs.entity_catalog import (
    CustomerCatalog,
    MerchantCatalog,
    CardCatalog,
)

class TransactionBuilder:
    def __init__(
        self,
        cfg: GeneratorConfig,
        customer_catalog: CustomerCatalog,
        merchant_catalog: MerchantCatalog,
        card_catalog: CardCatalog,
    ):
        self.cfg = cfg
        self.customer_catalog = customer_catalog
        self.merchant_catalog = merchant_catalog
        self.card_catalog = card_catalog
        # dedicated RNG for all transaction-level randomness
        self.rng = random.Random(cfg.seed + 1000)
        # sequential transaction IDs
        self.next_txn_id = 1

    def build_one(self) -> Dict:
        txn_id = self.next_txn_id
        self.next_txn_id += 1

        customer_id = self.customer_catalog.next_id()
        merchant_id = self.merchant_catalog.next_id()
        card_id = self.card_catalog.next_id()

        # uniform timestamp over 24h of start_date
        start_ts = datetime.combine(self.cfg.start_date, datetime.min.time())
        end_ts = start_ts + timedelta(days=1)
        delta_secs = (end_ts - start_ts).total_seconds()
        ts = start_ts + timedelta(seconds=self.rng.uniform(0, delta_secs))

        amount = round(self.rng.uniform(1.0, 500.0), 2)
        is_fraud = self.rng.random() < self.cfg.fraud_rate

        return {
            "transaction_id": txn_id,
            "customer_id": customer_id,
            "merchant_id": merchant_id,
            "card_id": card_id,
            "transaction_ts": ts.isoformat(),
            "amount": amount,
            "is_fraud": is_fraud,
        }

    def build_batch(self, batch_size: int) -> List[Dict]:
        return [self.build_one() for _ in range(batch_size)]
