import csv
import sys
import tempfile
import unittest
from pathlib import Path
import pickle

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from survival_pipeline import (aalen_johansen_cif, build_survival_data,
                               integrate_competing_cumulative_hazards,
                               left_truncated_c_index,
                               load_model_bundle, month_index, month_string,
                               score_new_loans)


class ConstantCoxLikeModel:
    """Small deterministic cumulative-hazard stub for bundle/scoring tests."""
    def __init__(self, rate):
        self.rate = rate

    def predict_cumulative_hazard(self, features, times):
        values = np.tile(np.asarray(times, float)[:, None] * self.rate, (1, len(features)))
        return pd.DataFrame(values, index=times, columns=features.index)


def orig_row(loan_id, first_payment):
    row = [""] * 31
    row[1], row[19] = first_payment, loan_id
    return row


def perf_row(loan_id, period, status="00", age="1", mod="", code="", effective=""):
    row = [""] * 35
    row[0], row[1], row[3], row[4], row[7], row[8], row[9] = loan_id, period, status, age, mod, code, effective
    return row


class SurvivalPipelineTests(unittest.TestCase):
    def test_month_index_calendar_boundaries(self):
        self.assertEqual(month_index("202601") - month_index("202512"), 1)
        self.assertEqual(month_index("202403") - month_index("202402"), 1)
        for value in ("190001", "201502", "202612"):
            self.assertEqual(month_string(month_index(value)), value)
        for bad in ("202600", "202613", "20-01"):
            with self.assertRaises(ValueError):
                month_index(bad)

    def test_dataset_builder_handles_event_competing_tie_and_delayed_entry(self):
        root = Path(__file__).resolve().parent
        orig_path, perf_path, out_path = root / ".orig_fixture", root / ".perf_fixture", root / ".survival_fixture.csv"
        try:
            with orig_path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f, delimiter="|").writerows([orig_row(k, "201501") for k in "ABCD"])
            perf = [
                perf_row("A", "201501", age="1"), perf_row("A", "201502", age="2"),
                perf_row("A", "201503", status="03", age="3"),
                perf_row("B", "201501", age="1"), perf_row("B", "201502", age="2"),
                perf_row("B", "201503", age="3"), perf_row("B", "201504", age="4", code="01", effective="201504"),
                perf_row("C", "201501", age="1"), perf_row("C", "201502", status="03", age="2", code="09", effective="201502"),
                perf_row("D", "201502", age="2"),
            ]
            with perf_path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f, delimiter="|").writerows(perf)
            df, summary = build_survival_data(orig_path, perf_path, out_path)
            rows = df.set_index("loan_id")
            self.assertEqual((int(rows.loc["A", "event_cause"]), int(rows.loc["A", "event_time_months"])), (1, 3))
            self.assertEqual((int(rows.loc["B", "event_cause"]), rows.loc["B", "exit_type"]), (2, "zero_balance_01"))
            self.assertEqual(int(rows.loc["C", "event_cause"]), 2)
            self.assertEqual(int(rows.loc["C", "same_month_90plus_termination_tie"]), 1)
            self.assertEqual(int(rows.loc["D", "delayed_entry_months"]), 1)
            self.assertEqual(int(rows.loc["D", "event_time_months"]), 2)
            self.assertEqual(summary["same_month_ambiguities_treated_as_competing"], 1)
        finally:
            for p in (orig_path, perf_path, out_path):
                p.unlink(missing_ok=True)

    def test_aalen_johansen_exact_monthly_ties_and_probability_invariants(self):
        duration = np.array([1, 1, 2, 2])
        entry = np.array([0, 0, 0, 0])
        cause = np.array([1, 2, 1, 0])
        aj = aalen_johansen_cif(duration, entry, cause)
        # Month 1: one of four events of each type; month 2: one of two survivors is cause 1.
        np.testing.assert_allclose(aj.loc[0, ["survival_all", "cif_cause_1", "cif_cause_2"]].to_numpy(float), [.5, .25, .25])
        np.testing.assert_allclose(aj.loc[1, ["survival_all", "cif_cause_1", "cif_cause_2"]].to_numpy(float), [.25, .5, .25])
        np.testing.assert_allclose(aj.survival_all + aj.cif_cause_1 + aj.cif_cause_2, 1.0)
        self.assertTrue((aj.cif_cause_1.diff().dropna() >= 0).all())
        with self.assertRaises(ValueError):
            aalen_johansen_cif(np.array([1]), np.array([1]), np.array([1]))

    def test_piecewise_competing_hazards_match_constant_hazard_analytic_solution(self):
        # Lambda values are annual rates, converted to each monthly interval.
        lam_event, lam_competing = .12, .24
        months = 60
        increments = {
            1: np.full((2, months), lam_event / 12),
            2: np.full((2, months), lam_competing / 12),
        }
        entry = np.array([0, 6])
        horizons = [6, 12, 36, 60]
        cif = integrate_competing_cumulative_hazards(increments, entry, horizons)
        lam_total = lam_event + lam_competing
        expected_0 = [lam_event / lam_total * (1 - np.exp(-lam_total * h / 12)) for h in horizons]
        expected_6 = [0 if h <= 6 else lam_event / lam_total * (1 - np.exp(-lam_total * (h - 6) / 12)) for h in horizons]
        np.testing.assert_allclose(cif[0, :, 0], expected_0, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(cif[1, :, 0], expected_6, rtol=1e-12, atol=1e-12)
        # With equal hazards across loans, the cause incidences plus survival equal one.
        for hpos, h in enumerate(horizons):
            elapsed = h / 12
            s = np.exp(-lam_total * elapsed)
            f1 = lam_event / lam_total * (1 - s)
            f2 = lam_competing / lam_total * (1 - s)
            self.assertAlmostEqual(s + f1 + f2, 1.0, places=12)

    def test_left_truncated_concordance_hand_calculation(self):
        # Month-3 event has two eligible controls (one concordant, one tied).
        # Month-5 event has two eligible controls (one concordant, one discordant).
        cindex, pairs = left_truncated_c_index(
            duration=[3, 5, 6, 8], entry=[0, 0, 1, 4],
            event=[1, 1, 0, 0], risk=[.9, .7, .2, .9])
        self.assertEqual(pairs, 4)
        self.assertAlmostEqual(cindex, .75)

    def test_model_bundle_round_trip_and_new_loan_prediction(self):
        root = Path(__file__).resolve().parent
        path = root / ".model_bundle_test.pkl"
        bundle = {"models": {1: ConstantCoxLikeModel(.01), 2: ConstantCoxLikeModel(.02)},
                  "feature_columns": [], "transform": {"numeric": {}, "categorical": {}},
                  "use_cltv_sensitivity": False}
        row = {"loan_id": "NEW1", "delayed_entry_months": 3,
               "classic_fico": "700", "original_ltv": "80", "original_cltv": "80",
               "original_dti": "35", "original_upb": "200000", "original_interest_rate": "4.0",
               "original_loan_term": "360", "mi_percentage": "0"}
        try:
            with path.open("wb") as f:
                pickle.dump(bundle, f)
            loaded = load_model_bundle(path)
            scored = score_new_loans(loaded, pd.DataFrame([row]), [6, 12])
            expected6 = (1 / 3) * (1 - np.exp(-.03 * 3))
            self.assertEqual(scored.loc[0, "loan_id"], "NEW1")
            self.assertAlmostEqual(scored.loc[0, "predicted_cif_first_90plus_6m"], expected6, places=12)
            self.assertTrue(((scored.filter(like="predicted_cif_") >= 0) &
                             (scored.filter(like="predicted_cif_") <= 1)).all().all())
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
