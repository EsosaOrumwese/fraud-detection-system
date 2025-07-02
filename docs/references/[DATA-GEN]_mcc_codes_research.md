# MCC Code Weights Research

This document summarizes the industry‐average fraud (chargeback) rates used to assign weights to each MCC code in `mcc_codes.py`. These weights reflect the relative likelihood of fraud per industry, drawn from published chargeback‐rate studies.

---

## Data Sources

1. **Swipesum, _Chargeback Rate by Industry and Business Type_**  
   https://www.swipesum.com/insights/chargeback-rate-by-industry-and-business-type/
2. **Clearly Payments, _Chargeback Rate by Industry and Business Type_**  
   https://www.clearlypayments.com/blog/chargeback-rate-by-industry-and-business-type/  
3. **OKLLC on LinkedIn, _The Essential Guide to Choosing the Best Payment Gateway for E-Commerce_** (2022 gambling rate)  
   https://www.linkedin.com/pulse/essential-guide-choosing-best-payment-gateway-okllc 

---

## Methodology

1. **Industry Breakdown:** We grouped MCCs by business category (e.g., Restaurants, Retail, Travel).  
2. **Chargeback Rates:** We used the average chargeback rates for each category (percent of transactions resulting in chargeback) from Swipesum [1].  
3. **Default Rate:** For “other” & mixed‐services categories, we applied the overall industry average (0.60%) from Clearly Payments [2].  
4. **Gambling & Betting:** Assigned the higher risk rate (1.50%) drawn from OKLLC’s 2022 benchmark for the gambling industry [3].  
5. **Decimal Conversion:** Rates were divided by 100 to convert percentages to decimal weights.

---

## Category Rates & Weights

| Category                                  | Chargeback Rate (%) | Weight (decimal) |
|-------------------------------------------|---------------------|------------------|
| **Restaurants & Bars**                    | 0.12 %              | 0.0012           |
| **Retail (incl. Grocery, Apparel, etc.)** | 0.52 %              | 0.0052           |
| **Travel & Hospitality**                  | 0.89 %              | 0.0089           |
| **Health & Wellness**                     | 0.86 %              | 0.0086           |
| **Gaming & Digital Goods**                | 0.83 %              | 0.0083           |
| **Software & SaaS**                       | 0.66 %              | 0.0066           |
| **Media & Entertainment**                 | 0.56 %              | 0.0056           |
| **Financial Services**                    | 0.55 %              | 0.0055           |
| **Education & Training**                  | 1.02 %              | 0.0102           |
| **Gambling & Betting**                    | 1.50 %              | 0.0150           |
| **Default / Misc. Services & Gov’t**      | 0.60 %              | 0.0060           |

---

## How to Use

In your sampling code, index the weight by the position of the MCC in `MCC_CODES`:

```python
from .mcc_codes import MCC_CODES, MCC_CODE_WEIGHTS

def fraud_weight_for_mcc(mcc: int) -> float:
    idx = MCC_CODES.index(mcc)
    return MCC_CODE_WEIGHTS[idx]
