# Exploratory data analysis

The cohort contains 49,980 loans. Event causes are coded 0=right-censored, 1=first 90+ delinquency, and 2=zero-balance termination.
Cause counts: {'0': 10656, '1': 2019, '2': 37305}. Delayed entry applies to 2,736 loans.
Loans excluded for zero-balance effective dates before First Payment Date: 20.
First performance month relative to First Payment Date: {'before': 43823, 'at': 3441, 'after': 2736}.
Median observed follow-up is 62 months; maximum is 134 months.
Special codes were converted to missing only for documented fields. VantageScore 4.0 is entirely unavailable in this cohort.
The Kaplan–Meier plot treats competing exits as censored and describes cause-specific net survival. The Aalen–Johansen plot estimates observed CIFs under delayed-entry risk sets.
Occupancy-specific curves are descriptive and do not imply causal effects.

![Follow-up](figures/followup_duration.png)

![Aalen–Johansen CIF](figures/aalen_johansen_cif.png)

![CIF by occupancy](figures/cif_by_occupancy.png)
