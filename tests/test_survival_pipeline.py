import csv
import sys
import tempfile
import unittest
from pathlib import Path
import pickle

import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from survival_pipeline import (aalen_johansen_cif, administrative_brier_terms,
                               bootstrap_metric_intervals,
                               calendar_cohort_split,
                               conditional_aj_cif, build_survival_data,
                               integrate_competing_cumulative_hazards,
                               cif_ipcw_brier,
                               paired_bootstrap_mean_difference,
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
                csv.writer(f, delimiter="|").writerows([orig_row(k, "201501") for k in "ABCD"] +
                                                          [orig_row("E", "201503"), orig_row("F", "201503")])
            perf = [
                perf_row("A", "201501", age="1"), perf_row("A", "201502", age="2"),
                perf_row("A", "201503", status="03", age="3"),
                perf_row("B", "201501", age="1"), perf_row("B", "201502", age="2"),
                perf_row("B", "201503", age="3"), perf_row("B", "201504", age="4", code="01", effective="201504"),
                perf_row("C", "201501", age="1"), perf_row("C", "201502", status="03", age="2", code="09", effective="201502"),
                perf_row("D", "201502", age="2"),
                # A terminal exit before the declared First Payment Date is outside the risk cohort.
                perf_row("E", "201502", age="0", code="01", effective="201502"),
                # A pre-origin status is ignored; later 90+ remains the first at-risk event.
                perf_row("F", "201502", status="03", age="0"), perf_row("F", "201503", age="1"),
                perf_row("F", "201504", status="03", age="2"),
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
            self.assertNotIn("E", rows.index)
            self.assertEqual(int(rows.loc["F", "event_cause"]), 1)
            self.assertEqual(rows.loc["F", "first_90plus_period"], "201504")
            self.assertEqual(summary["loans_excluded_terminal_before_time_origin"], 1)
            self.assertEqual(summary["pre_origin_90plus_rows_ignored"], 1)
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
        self.assertTrue((aj.cif_cause_2.diff().dropna() >= 0).all())
        self.assertTrue((aj[["cif_cause_1", "cif_cause_2"]].to_numpy() >= 0).all())
        self.assertTrue((aj.cif_cause_1 + aj.cif_cause_2 <= 1 + 1e-12).all())
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
        self.assertTrue((np.diff(cif, axis=1) >= -1e-12).all())
        self.assertTrue((cif >= -1e-12).all() and (cif <= 1 + 1e-12).all())
        self.assertTrue((cif.sum(axis=2) <= 1 + 1e-12).all())
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

    def test_piecewise_competing_hazards_zero_total_increment_is_identity(self):
        increments = {1: np.zeros((2, 4)), 2: np.zeros((2, 4))}
        entry = np.array([0, 2])
        horizons = [1, 2, 3, 4]
        cif = integrate_competing_cumulative_hazards(increments, entry, horizons)
        self.assertTrue(np.isfinite(cif).all())
        np.testing.assert_array_equal(cif, np.zeros_like(cif))

    def test_left_truncated_concordance_hand_calculation(self):
        # Month-3 event has two eligible controls (one concordant, one tied).
        # Month-5 event has two eligible controls (one concordant, one discordant).
        cindex, pairs = left_truncated_c_index(
            duration=[3, 5, 6, 8], entry=[0, 0, 1, 4],
            event=[1, 1, 0, 0], risk=[.9, .7, .2, .9])
        self.assertEqual(pairs, 4)
        self.assertAlmostEqual(cindex, .75)

    def test_test_loan_bootstrap_is_deterministic_for_fixed_seed(self):
        args = ([3, 5, 6, 8], [0, 0, 1, 4], [1, 1, 0, 0], [.9, .7, .2, .9], [3],
                {3: (np.array([.1, .2, .0, .0]), np.array([True, True, False, False]))}, 20, 17)
        first = bootstrap_metric_intervals(*args)
        second = bootstrap_metric_intervals(*args)
        pd.testing.assert_frame_equal(first, second)

    def test_calendar_cohort_split_is_outcome_blind_and_partitions_rows(self):
        train, test = calendar_cohort_split([201512, 201601, 201503, 201701], "201512")
        np.testing.assert_array_equal(train, [0, 2])
        np.testing.assert_array_equal(test, [1, 3])

    def test_paired_bootstrap_resamples_model_reference_losses_together(self):
        model = np.array([.1, .2, .3, 10.0])
        reference = np.array([.2, .1, .4, 0.0])
        valid = np.array([True, True, True, False])
        first = paired_bootstrap_mean_difference(model, reference, valid, 100, 23)
        second = paired_bootstrap_mean_difference(model, reference, valid, 100, 23)
        self.assertAlmostEqual(first["difference"], -1 / 30)
        self.assertEqual(first["n_valid"], 3)
        self.assertEqual(first["successful_replicates"], 100)
        self.assertEqual(first, second)

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
            scored_default = score_new_loans(loaded, pd.DataFrame([row]))
            self.assertIn("predicted_cif_first_90plus_120m", scored_default.columns)
        finally:
            path.unlink(missing_ok=True)

    @staticmethod
    def km_no_censoring():
        km = KaplanMeierFitter()
        km.fit([4, 5], event_observed=[False, False], entry=[0, 0])
        return km

    def test_brier_only_primary_event_hand_calculation(self):
        # Event at 2 gives y=1; still-event-free at 4 gives y=0. G=1.
        score, y, w = cif_ipcw_brier([2, 4], [0, 0], [1, 0], 3, [.8, .2], self.km_no_censoring())
        np.testing.assert_array_equal(y, [1, 0]); np.testing.assert_array_equal(w, [1, 1])
        self.assertAlmostEqual(score, ((1 - .8) ** 2 + .2 ** 2) / 2)

    def test_brier_only_competing_event_is_known_target_nonevent(self):
        score, y, w = cif_ipcw_brier([2, 4], [0, 0], [2, 0], 3, [.2, .3], self.km_no_censoring())
        np.testing.assert_array_equal(y, [0, 0]); np.testing.assert_array_equal(w, [1, 1])
        self.assertAlmostEqual(score, (.2 ** 2 + .3 ** 2) / 2)

    def test_brier_drops_censor_before_horizon_from_loss_not_denominator(self):
        # Training reverse-KM has G(3-)=1/2; the censored test loan at 2 is unknown.
        km = KaplanMeierFitter().fit([2, 5], event_observed=[True, False], entry=[0, 0])
        score, y, w = cif_ipcw_brier([3, 4, 2], [0, 0, 0], [1, 0, 0], 3,
                                     [.8, .2, .9], km)
        np.testing.assert_array_equal(y, [1, 0, 0]); np.testing.assert_allclose(w, [2, 2, 0])
        self.assertAlmostEqual(score, (.04 * 2 + .04 * 2) / 3)

    def test_brier_event_exactly_at_horizon_is_a_case_not_a_control(self):
        # Monthly endpoint status is observed through month 3; event at 3 is positive.
        score, y, w = cif_ipcw_brier([3], [0], [1], 3, [.7], self.km_no_censoring())
        np.testing.assert_array_equal(y, [1]); np.testing.assert_array_equal(w, [1])
        self.assertAlmostEqual(score, .3 ** 2)

    def test_brier_competing_event_exactly_at_horizon_is_a_nonevent(self):
        score, y, w = cif_ipcw_brier([3], [0], [2], 3, [.7], self.km_no_censoring())
        np.testing.assert_array_equal(y, [0]); np.testing.assert_array_equal(w, [1])
        self.assertAlmostEqual(score, .7 ** 2)

    def test_brier_censor_exactly_at_horizon_is_known_through_observed_month(self):
        score, y, w = cif_ipcw_brier([3], [0], [0], 3, [.3], self.km_no_censoring())
        np.testing.assert_array_equal(y, [0]); np.testing.assert_array_equal(w, [1])
        self.assertAlmostEqual(score, .3 ** 2)

    def test_brier_no_event_before_horizon_including_competing_after_horizon(self):
        score, y, w = cif_ipcw_brier([4, 5], [0, 0], [0, 2], 3, [.1, .2], self.km_no_censoring())
        np.testing.assert_array_equal(y, [0, 0]); np.testing.assert_array_equal(w, [1, 1])
        self.assertAlmostEqual(score, (.1 ** 2 + .2 ** 2) / 2)

    def test_brier_delayed_entry_uses_conditional_censor_survival_ratio(self):
        # Reverse-KM G(2-)=G(3-)=1/2. Conditional on entry at 2, both weights are 1.
        km = KaplanMeierFitter().fit([1, 5], event_observed=[True, False], entry=[0, 0])
        score, y, w = cif_ipcw_brier([3, 5], [2, 2], [1, 0], 4, [.8, .2], km)
        np.testing.assert_array_equal(y, [1, 0]); np.testing.assert_allclose(w, [1, 1])
        self.assertAlmostEqual(score, .04)

    def test_brier_returns_undefined_when_censoring_support_is_zero(self):
        km = KaplanMeierFitter().fit([2], event_observed=[True], entry=[0])
        score, _, weights = cif_ipcw_brier([2, 3], [0, 0], [0, 0], 3, [.2, .3], km)
        self.assertTrue(np.isnan(score))
        np.testing.assert_array_equal(weights, [0, 0])

    def test_brier_keeps_large_finite_ipcw_weights_without_arbitrary_cutoff(self):
        # Reverse-KM G(3-)=1/25; both observed statuses get weight 25, not zeroed.
        km = KaplanMeierFitter().fit([2] * 24 + [5], event_observed=[True] * 24 + [False], entry=[0] * 25)
        score, y, w = cif_ipcw_brier([4, 6], [0, 0], [1, 0], 4, [.8, .2], km)
        np.testing.assert_array_equal(y, [1, 0]); np.testing.assert_allclose(w, [25, 25])
        self.assertAlmostEqual(score, 1.0)

    def test_brier_entry_at_or_after_horizon_is_ineligible(self):
        # At e=h the subject is not at risk for any post-entry interval by h.
        score, y, w = cif_ipcw_brier([4, 5], [3, 4], [1, 0], 3, [.7, .2], self.km_no_censoring())
        self.assertTrue(np.isnan(score))
        np.testing.assert_array_equal(y, [0, 0])
        np.testing.assert_array_equal(w, [0, 0])

    def test_administrative_brier_hand_example_and_unknown_censor_exclusion(self):
        # At h=3: target case, competing negative, known event-free, censor at h,
        # unknown censor before h, and entry at h (ineligible). No censor weights.
        d = [2, 2, 4, 3, 1, 4]
        e = [0, 0, 0, 0, 0, 3]
        c = [1, 2, 0, 0, 0, 0]
        p = [.8, .2, .1, .3, .9, .5]
        score, valid, y, losses = administrative_brier_terms(d, e, c, 3, p)
        np.testing.assert_array_equal(valid, [1, 1, 1, 1, 0, 0])
        np.testing.assert_array_equal(y, [1, 0, 0, 0, 0, 0])
        np.testing.assert_allclose(losses[valid], [.04, .04, .01, .09])
        self.assertAlmostEqual(score, .045)

    def test_conditional_training_aj_reference_hand_calculation(self):
        # Synthetic curve from manual product-limit arithmetic:
        # month 1: risk 4, one event of each cause -> S=.5,F1=.25;
        # month 2: risk 2, one event of cause 1 -> S=.25,F1=.5.
        aj = aalen_johansen_cif([1, 1, 2, 2], [0, 0, 0, 0], [1, 2, 1, 0])
        pred = conditional_aj_cif(aj, [0, 1], 2)
        # Entrant at 0: F1(2)=.5. Conditional on event-free through month 1:
        # (.5-.25)/.5=.5.
        np.testing.assert_allclose(pred, [.5, .5])

    def test_marginal_censor_survival_does_not_recover_known_admin_followup(self):
        # Loan A is administratively observed through h=3 (C=5); loan B's
        # administration ends at 2. Conditioning on their known calendar cutoffs
        # gives A weight 1 and B is not scoreable. A marginal reverse-KM gives
        # A weight 2, showing the assumption the production IPCW needs.
        km = KaplanMeierFitter().fit([2, 5], event_observed=[True, True], entry=[0, 0])
        score, y, w = cif_ipcw_brier([4, 2], [0, 0], [0, 0], 3, [.2, .9], km)
        self.assertAlmostEqual(w[0], 2.0)
        self.assertAlmostEqual(w[1], 0.0)
        self.assertAlmostEqual(score, .04)
        admin_score, known, _, _ = administrative_brier_terms([4, 2], [0, 0], [0, 0], 3, [.2, .9])
        self.assertAlmostEqual(admin_score, .04)
        np.testing.assert_array_equal(known, [True, False])

    def test_duplicate_monthly_record_is_rejected_without_changing_loan_unit(self):
        root = Path(__file__).resolve().parent
        orig_path, perf_path, out_path = root / ".orig_dup_fixture", root / ".perf_dup_fixture", root / ".survival_dup_fixture.csv"
        try:
            with orig_path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f, delimiter="|").writerow(orig_row("A", "201501"))
            duplicate = perf_row("A", "201501", age="1")
            with perf_path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f, delimiter="|").writerows([duplicate, duplicate])
            with self.assertRaisesRegex(ValueError, "Duplicate or unsorted monthly row"):
                build_survival_data(orig_path, perf_path, out_path)
        finally:
            for p in (orig_path, perf_path, out_path):
                p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
