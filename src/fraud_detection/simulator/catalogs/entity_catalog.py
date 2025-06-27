import random
from typing import Iterator

class CustomerCatalog:
    def __init__(self, count: int, seed: int):
        self.count = count
        self.rng = random.Random(seed)
        # Pre-generate & shuffle to ensure uniform coverage
        self._ids = list(range(1, count + 1))
        self.rng.shuffle(self._ids)
        self._ptr = 0

    def next_id(self) -> int:
        if self._ptr >= self.count:
            self._ptr = 0
            self.rng.shuffle(self._ids)
        cid = self._ids[self._ptr]
        self._ptr += 1
        return cid

class MerchantCatalog:
    def __init__(self, count: int, seed: int):
        self.count = count
        self.rng = random.Random(seed)
        self._ids = list(range(1, count + 1))
        self.rng.shuffle(self._ids)
        self._ptr = 0

    def next_id(self) -> int:
        if self._ptr >= self.count:
            self._ptr = 0
            self.rng.shuffle(self._ids)
        mid = self._ids[self._ptr]
        self._ptr += 1
        return mid

class CardCatalog:
    def __init__(self, count: int, seed: int):
        self.count = count
        self.rng = random.Random(seed)
        self._ids = list(range(1, count + 1))
        self.rng.shuffle(self._ids)
        self._ptr = 0

    def next_id(self) -> int:
        if self._ptr >= self.count:
            self._ptr = 0
            self.rng.shuffle(self._ids)
        card = self._ids[self._ptr]
        self._ptr += 1
        return card
