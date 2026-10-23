# Data audit

Source/schema: Freddie Mac SFLLD Sample 2015; physical schema matches Release 47 (July 2026)

- Origination: 50,000 rows, 31 columns, 50,000 unique loans.
- Performance: 3,467,166 rows, 35 columns, 50,000 unique loans.
- Matched IDs: 50,000; origination only: 0; performance only: 0.
- Reporting window: 201501–202603 (135 calendar months).
- Duplicate loan-month rows: 0; per-loan calendar gaps: 2 intervals across 2 loans.
- Raw files are pipe-delimited, headerless; audit streamed rows without editing inputs.

## Column missingness

### Origination

| # | Field | Missing |
|---:|---|---:|
| 1 | Credit Score | 0 (0.000%) |
| 2 | First Payment Date | 0 (0.000%) |
| 3 | First Time Homebuyer Flag | 0 (0.000%) |
| 4 | Maturity Date | 0 (0.000%) |
| 5 | Metropolitan Statistical Area (MSA) | 5,604 (11.208%) |
| 6 | Mortgage Insurance Percentage | 0 (0.000%) |
| 7 | Number of Units | 0 (0.000%) |
| 8 | Occupancy Status | 0 (0.000%) |
| 9 | Original Combined Loan-to-Value (CLTV) | 0 (0.000%) |
| 10 | Original Debt-to-Income (DTI) | 0 (0.000%) |
| 11 | Original UPB | 0 (0.000%) |
| 12 | Original Loan-to-Value (LTV) | 0 (0.000%) |
| 13 | Original Interest Rate | 0 (0.000%) |
| 14 | Channel | 0 (0.000%) |
| 15 | Prepayment Penalty Indicator | 0 (0.000%) |
| 16 | Amortization Type | 0 (0.000%) |
| 17 | Property State | 0 (0.000%) |
| 18 | Property Type | 0 (0.000%) |
| 19 | Postal Code | 0 (0.000%) |
| 20 | Loan Sequence Number | 0 (0.000%) |
| 21 | Loan Purpose | 0 (0.000%) |
| 22 | Original Loan Term | 0 (0.000%) |
| 23 | Number of Borrowers | 0 (0.000%) |
| 24 | Seller Name | 0 (0.000%) |
| 25 | Super Conforming Flag | 0 (0.000%) |
| 26 | Pre-HARP Loan Sequence Number | 45,983 (91.966%) |
| 27 | Special Eligibility Program | 49,675 (99.350%) |
| 28 | HARP Indicator | 0 (0.000%) |
| 29 | Property Valuation Method | 0 (0.000%) |
| 30 | Interest Only Indicator | 0 (0.000%) |
| 31 | VantageScore 4.0 | 0 (0.000%) |

### Performance

| # | Field | Missing |
|---:|---|---:|
| 1 | Loan Sequence Number | 0 (0.000%) |
| 2 | Monthly Reporting Period | 0 (0.000%) |
| 3 | Current Actual UPB | 0 (0.000%) |
| 4 | Current Loan Delinquency Status | 0 (0.000%) |
| 5 | Loan Age | 0 (0.000%) |
| 6 | Remaining Months to Legal Maturity | 0 (0.000%) |
| 7 | Defect Settlement Date | 3,467,127 (99.999%) |
| 8 | Modification Flag | 3,447,815 (99.442%) |
| 9 | Zero Balance Code | 3,428,675 (98.890%) |
| 10 | Zero Balance Effective Date | 3,428,675 (98.890%) |
| 11 | Current Interest Rate | 0 (0.000%) |
| 12 | Current Non-Interest Bearing UPB | 0 (0.000%) |
| 13 | Due Date of Last Paid Installment | 3,442,762 (99.296%) |
| 14 | MI Recoveries | 3,467,032 (99.996%) |
| 15 | Net Sales Proceeds | 3,467,032 (99.996%) |
| 16 | Non-MI Recoveries | 3,467,032 (99.996%) |
| 17 | Total Expenses | 3,467,032 (99.996%) |
| 18 | Legal Costs | 3,467,032 (99.996%) |
| 19 | Maintenance and Preservation Costs | 3,467,032 (99.996%) |
| 20 | Taxes and Insurance | 3,467,032 (99.996%) |
| 21 | Miscellaneous Expenses | 3,467,032 (99.996%) |
| 22 | Actual Loss | 3,467,032 (99.996%) |
| 23 | Cumulative Modification Costs | 0 (0.000%) |
| 24 | Interest Rate Step Indicator | 3,447,815 (99.442%) |
| 25 | Payment Deferral Flag | 3,430,025 (98.929%) |
| 26 | Estimated Loan-to-Value (ELTV) | 0 (0.000%) |
| 27 | Zero Balance Removal UPB | 3,428,675 (98.890%) |
| 28 | Delinquent Accrued Interest | 3,467,032 (99.996%) |
| 29 | Delinquency Due to Disaster | 3,448,710 (99.468%) |
| 30 | Borrower Assistance Plan | 3,446,668 (99.409%) |
| 31 | Current Period Modification Costs | 3,412,300 (98.418%) |
| 32 | Current Interest Bearing UPB | 0 (0.000%) |
| 33 | Mortgage Insurance Cancellation Indicator | 0 (0.000%) |
| 34 | Servicer Name | 0 (0.000%) |
| 35 | Bankruptcy Cramdown Costs | 3,396,380 (97.958%) |

## Delinquency status rows

| Code | Rows |
|---|---:|
| 00 | 3,415,433 |
| 01 | 23,522 |
| 02 | 6,686 |
| 03 | 3,756 |
| 04 | 2,597 |
| 05 | 2,151 |
| 06 | 1,654 |
| 07 | 1,427 |
| 08 | 1,182 |
| 09 | 1,029 |
| 10 | 925 |
| 11 | 836 |
| 12 | 742 |
| 13 | 633 |
| RA | 567 |
| 14 | 527 |
| 15 | 461 |
| 16 | 419 |
| 17 | 381 |
| 18 | 345 |
| 19 | 259 |
| 20 | 236 |
| 21 | 192 |
| 22 | 151 |
| 23 | 130 |
| 24 | 110 |
| 25 | 102 |
| 26 | 91 |
| 27 | 86 |
| 28 | 60 |
| 29 | 49 |
| 30 | 48 |
| 31 | 44 |
| 32 | 36 |
| 33 | 35 |
| 34 | 32 |
| 35 | 24 |
| 36 | 21 |
| 37 | 17 |
| 38 | 17 |
| 39 | 16 |
| 40 | 14 |
| 41 | 14 |
| 42 | 11 |
| 44 | 8 |
| 45 | 8 |
| 43 | 7 |
| 46 | 7 |
| 47 | 7 |
| 48 | 7 |
| 49 | 6 |
| 50 | 5 |
| 51 | 5 |
| 52 | 5 |
| 53 | 3 |
| 54 | 2 |
| 55 | 2 |
| 56 | 2 |
| 57 | 2 |
| 58 | 2 |
| 59 | 2 |
| 60 | 2 |
| 61 | 2 |
| 62 | 2 |
| 63 | 2 |
| 64 | 2 |
| 65 | 2 |
| 66 | 2 |
| 67 | 1 |
| 68 | 1 |
| 69 | 1 |
| 70 | 1 |

## Zero-balance code rows

| Code | Rows |
|---|---:|
| 01 | 38,212 |
| 16 | 108 |
| 09 | 55 |
| 02 | 45 |
| 96 | 35 |
| 15 | 18 |
| 03 | 18 |

## Survival cohort construction

- Loans in source origination/performance files: 50,000.
- Loans excluded because zero-balance effective date precedes First Payment Date: 20 ({'01': 19, '96': 1}).
- Analysis loans: 49,980; first 90+ events: 2,019; competing exits: 37,305; right-censored: 10,656.
- First performance month relative to First Payment Date (before/at/after): {'before': 43823, 'at': 3441, 'after': 2736}.
- Pre-origin 90+ status rows ignored: 0; same-month 90+/termination ties assigned to competing exit: 30.
