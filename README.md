# Cox competing-risks analysis of Freddie Mac 2015 loans

This project studies the time to a loan's **first reported 90+ day delinquency status** in Freddie Mac's 2015 Single-Family Loan-Level Dataset sample. It is a research proxy, not a legal default or a realized credit-loss label. Zero-balance terminations are modeled as competing exits, with their source codes retained.

## Run

Use Python 3.10 or newer in the project directory:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python src/survival_pipeline.py --bootstrap 100
python src/eda.py
```


## Data and references

The included files are Freddie Mac SFLLD Sample 2015, not LendingClub. Consult Freddie Mac's [dataset page](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset), [July 2026 General User Guide](https://www.freddiemac.com/fmac-resources/research/pdf/general_user_guide_july_2026.pdf), and [Release 47 disclosure changes](https://www.freddiemac.com/fmac-resources/research/pdf/disclosure-changes-summary.pdf). Follow the dataset's terms of use. Method references are Cox (1972), [Regression Models and Life-Tables](https://rss.onlinelibrary.wiley.com/doi/10.1111/j.2517-6161.1972.tb00899.x), and Aalen and Johansen (1978), [An empirical transition matrix for non-homogeneous Markov chains based on censored observations](https://gwern.net/doc/statistics/survival-analysis/1978-aalen.pdf).
