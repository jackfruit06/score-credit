import csv
import tempfile
import unittest
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter, CoxTimeVaryingFitter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import survival_pipeline as sp
from test_survival_pipeline import orig_row, perf_row


class AuditRegressions(unittest.TestCase):
    def build(self, orig, perf):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root = Path(tmp)
            for name, rows in (("orig", orig), ("perf", perf)):
                with (root / name).open("w", newline="", encoding="utf-8") as f:
                    csv.writer(f, delimiter="|").writerows(rows)
            return sp.build_survival_data(root / "orig", root / "perf", root / "out.csv")

    def test_breslow_risk_set_hand_calculation(self):
        # t=1 excludes the subject entering at 1: sum risk=2+1, not 7.
        result = sp.delayed_entry_baseline([1, 3, 3], [0, 1, 0], [1, 1, 0], [2, 4, 1])
        np.testing.assert_allclose(result.to_numpy().ravel(), [0, 1/3, 0, 1/5])

    def test_actual_fitter_prediction_uses_corrected_baseline_and_zero_origin(self):
        data = pd.DataFrame({"x": [-1, 0, 1, -1, 0, 1, -.5, .5],
                             "T": [1, 2, 3, 4, 5, 6, 7, 8],
                             "L": [0, 0, 2, 0, 0, 2, 0, 0],
                             "E": [1, 0, 1, 1, 0, 1, 1, 0]})
        model = CoxPHFitter().fit(data, "T", "E", entry_col="L")
        x = data[["x"]]
        risk = model.predict_partial_hazard(x).to_numpy()
        expected = 1 / risk[data.L.to_numpy() < 1].sum()
        sp.correct_delayed_entry_baseline(model, x, data["T"], data.L, data.E)
        self.assertAlmostEqual(model.baseline_hazard_.loc[1].iloc[0], expected)
        prediction = model.predict_cumulative_hazard(x.iloc[:1], times=[0, 1, 2])
        np.testing.assert_allclose(prediction.to_numpy().ravel(), [0, expected*risk[0], expected*risk[0]])
        cif = sp.competing_cox_cif({1: model}, x.iloc[:1], [0], [1])
        self.assertAlmostEqual(cif[0, 0], 1-np.exp(-expected*risk[0]))

    def test_partial_likelihood_entry_and_efron_against_finite_difference(self):
        x = np.array([[-1.], [0.], [1.], [.5]])
        t, l, event = np.array([2., 2., 4., 5.]), np.array([0., 0., 2., 0.]), np.array([1, 1, 1, 0], bool)
        def likelihood(beta):
            # At 2, subject index 2 has not entered; two Efron tied deaths.
            w = np.exp(x[:, 0]*beta)
            return (-beta - np.log(w[0]+w[1]+w[3])
                    - np.log(w[0]+w[1]+w[3]-(w[0]+w[1])/2)
                    + beta - np.log(w[2]+w[3]))
        b, eps = .17, 1e-5
        hess, grad, ll = CoxTimeVaryingFitter._get_gradients(x, event, l, t, np.ones(4), np.array([b]))
        self.assertAlmostEqual(ll, likelihood(b), places=12)
        self.assertAlmostEqual(grad[0], (likelihood(b+eps)-likelihood(b-eps))/(2*eps), places=8)
        self.assertAlmostEqual(hess[0, 0], (likelihood(b+eps)-2*likelihood(b)+likelihood(b-eps))/eps**2, places=4)

    def test_sparse_aj_keeps_intermediate_events(self):
        aj = sp.aalen_johansen_cif([1, 2], [0, 0], [1, 0], times=np.array([2]))
        self.assertAlmostEqual(aj.cif_cause_1.iloc[0], .5)

    def test_fallback_count_excludes_nonterminal_loans(self):
        _, summary = self.build([orig_row("A", "201501"), orig_row("B", "201501")],
                                [perf_row("A", "201501"), perf_row("B", "201501", code="01")])
        self.assertEqual(summary["zero_balance_effective_date_missing_fallback_to_report_month"], 1)

    def test_terminal_before_entry_is_excluded_not_shifted(self):
        df, summary = self.build([orig_row("A", "201501"), orig_row("B", "201501")],
                                [perf_row("A", "201503", code="01", effective="201502"), perf_row("B", "201501")])
        self.assertEqual(df.loan_id.tolist(), ["B"])
        self.assertEqual(summary["loans_excluded_terminal_before_entry"], 1)

    def test_unknown_status_is_not_silently_event_free(self):
        for status in ("XX", "", "100", "BAD"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.build([orig_row("A", "201501")], [perf_row("A", "201501", status=status)])

    def test_effective_after_report_is_preserved_and_flagged(self):
        df, summary = self.build([orig_row("A", "201501")],
                                [perf_row("A", "201510", code="01", effective="201511")])
        self.assertEqual(int(df.event_time_months.iloc[0]), 11)
        self.assertEqual(summary["terminal_effective_after_last_report"], 1)

    def test_cleaning_float_and_string_sentinels_are_equal(self):
        base = {"classic_fico": "9999", "original_ltv": "999", "original_cltv": "999",
                "original_dti": "999", "mi_percentage": "999", "original_upb": "200000",
                "original_interest_rate": "4", "original_loan_term": "360",
                "number_of_borrowers": "99", "number_of_units": "1", "occupancy_status": None}
        strings = sp._clean_original(pd.DataFrame([base]))
        floats = sp._clean_original(pd.DataFrame([{k: float(v) if v is not None else np.nan for k, v in base.items()}]))
        for col in ("classic_fico", "original_ltv", "original_cltv", "original_dti", "mi_percentage", "number_of_borrowers", "occupancy_status"):
            self.assertTrue(strings[col].isna().all(), col)
            self.assertTrue(floats[col].isna().all(), col)
        self.assertEqual(strings.number_of_units.iloc[0], floats.number_of_units.iloc[0])

    def test_censor_at_entry_is_already_conditioned_out(self):
        km = KaplanMeierFitter().fit([2, 5], event_observed=[1, 0], entry=[0, 0])
        score, _, weights = sp.cif_ipcw_brier([4], [2], [1], 4, [.8], km)
        self.assertAlmostEqual(weights[0], 1)
        self.assertAlmostEqual(score, .04)

    def test_monthly_censor_ties_event_before_censor(self):
        # At 2: risk=3, one cause event leaves, one censor among the other two.
        km = sp.fit_monthly_censoring([2, 2, 4], [0, 0, 0], [1, 0, 2])
        self.assertAlmostEqual(sp._km_survival_before(km, 2), 1)
        self.assertAlmostEqual(sp._km_survival_before(km, 3), .5)

    def test_calendar_split_rejects_invalid_month(self):
        with self.assertRaises(ValueError):
            sp.calendar_cohort_split([201512, 201601], "201513")

    def test_preprocessing_is_train_only_and_roundtrips(self):
        n = 240
        df = pd.DataFrame({c: ["N"]*n for c in sp.CATEGORICAL})
        for col, value in {"classic_fico": 700, "original_ltv": 80, "original_cltv": 85,
                           "original_dti": 35, "original_upb": 200000,
                           "original_interest_rate": 4, "original_loan_term": 360,
                           "mi_percentage": 20}.items():
            df[col] = value + np.arange(n) % 7
        df["number_of_borrowers"], df["number_of_units"] = "1", "1"
        df["occupancy_status"] = ["I", "P"]*120
        df.loc[:35, "original_dti"] = 999
        tr, te = np.arange(200), np.arange(200, 240)
        xtr, xte, transform, _ = sp.prepare_features(df, tr, te)
        scored = sp.transform_new_features(df.iloc[te], transform, list(xtr.columns))
        pd.testing.assert_frame_equal(xte, scored.reset_index(drop=True))
        changed = df.copy()
        changed.loc[te, "classic_fico"] = 500
        changed.loc[te, "occupancy_status"] = "S"
        xtr2, _, transform2, _ = sp.prepare_features(changed, tr, te)
        pd.testing.assert_frame_equal(xtr, xtr2)
        self.assertEqual(transform, transform2)

    def test_nonpositive_original_upb_is_rejected(self):
        df = pd.DataFrame({c: [1] for c in ["classic_fico", "original_ltv", "original_cltv", "original_dti",
                                           "original_interest_rate", "original_loan_term", "mi_percentage"]})
        df["original_upb"] = -1
        with self.assertRaises(ValueError):
            sp._clean_original(df)

    def test_fractional_entry_cannot_be_silently_rounded_for_cif(self):
        from test_survival_pipeline import ConstantCoxLikeModel
        with self.assertRaises(ValueError):
            sp.competing_cox_cif({1: ConstantCoxLikeModel(.1)}, pd.DataFrame(index=[0]), [.5], [2])


class TargetedFixRegressions(unittest.TestCase):
    @staticmethod
    def original_row():
        return {"classic_fico": "700", "original_ltv": "80", "original_cltv": "85",
                "original_dti": "35", "mi_percentage": "0", "original_upb": "200000",
                "original_interest_rate": "4", "original_loan_term": "360"}

    def test_all_categorical_sentinel_representations(self):
        fields = {k: codes for k, codes in sp.SENTINELS.items() if k in sp.CATEGORICAL}
        for field, codes in fields.items():
            for code in codes:
                for value in (code, int(code), float(code), code + ".0", code + ".00", None, np.nan, pd.NA, ""):
                    with self.subTest(field=field, value=repr(value)):
                        row = self.original_row() | {field: value}
                        self.assertTrue(pd.isna(sp._clean_original(pd.DataFrame([row]))[field].iloc[0]))

    def test_sentinel_features_and_predictions_are_equivalent(self):
        class FeatureHazard:
            def predict_cumulative_hazard(self, features, times):
                risk = np.exp(features.to_numpy().sum(axis=1))
                return pd.DataFrame(np.asarray(times)[:, None] * .01 * risk[None, :])

        for field in (k for k in sp.SENTINELS if k in sp.CATEGORICAL):
            code = next(iter(sp.SENTINELS[field]))
            rows = [self.original_row() | {field: v} for v in (code, int(code), float(code), code + ".00", None)]
            transform = {"numeric": {}, "categorical": {field: {
                "levels": ["Valid", "Unknown"], "reference": "Valid", "rare_values": []}}}
            columns = [field + "_Unknown"]
            data = pd.DataFrame(rows)
            x = sp.transform_new_features(data, transform, columns)
            np.testing.assert_array_equal(x.to_numpy(), np.ones((len(rows), 1)))
            bundle = {"transform": transform, "feature_columns": columns, "models": {1: FeatureHazard()}}
            pred = sp.score_new_loans(bundle, data, [1, 3])
            np.testing.assert_allclose(pred.filter(like="predicted_cif_").to_numpy(),
                                       np.tile([1-np.exp(-.01*np.e), 1-np.exp(-.03*np.e)], (len(rows), 1)))

    def test_valid_and_unspecified_categories_preserved(self):
        for field, values in {
            "first_time_homebuyer": ["Y", "N", "9.5", "09", "9e0", "BAD"],
            "occupancy_status": ["P", "I", "S", "9.5"],
            "loan_purpose": ["P", "C", "N", "9.5"],
            "property_type": ["SF", "CO", "PU", "MH", "CP", "99.5", "099"],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    cleaned = sp._clean_original(pd.DataFrame([self.original_row() | {field: value}]))
                    self.assertEqual(cleaned[field].iloc[0], value)
        for field in ("number_of_borrowers", "number_of_units"):
            for value in ("1", 1, 1.0, "1.00"):
                cleaned = sp._clean_original(pd.DataFrame([self.original_row() | {field: value}]))
                self.assertEqual(cleaned[field].iloc[0], "1")

    def test_sparse_aj_composition_first_and_last_horizon(self):
        aj = sp.aalen_johansen_cif([2, 3], [0, 0], [1, 0], times=np.array([2, 3]))
        for horizon in (2, 3):
            np.testing.assert_allclose(sp.conditional_aj_cif(aj, [0], horizon), [.5])

    def test_sparse_aj_missing_horizon_is_not_a_row_position(self):
        aj = sp.aalen_johansen_cif([2, 3], [0, 0], [1, 0], times=np.array([2, 3]))
        with self.assertRaisesRegex(ValueError, "month|monthly"):
            sp.conditional_aj_cif(aj, [0], 1)

    def test_sparse_aj_missing_entry_is_not_interpolated(self):
        aj = sp.aalen_johansen_cif([2, 3], [0, 0], [1, 0], times=np.array([1, 3]))
        with self.assertRaisesRegex(ValueError, "month|monthly"):
            sp.conditional_aj_cif(aj, [2], 3)

    def test_full_aj_grid_retains_monthly_conditional_values(self):
        aj = sp.aalen_johansen_cif([2, 3], [0, 0], [1, 0])
        np.testing.assert_array_equal(sp.conditional_aj_cif(aj, [0], 1), [0])
        np.testing.assert_allclose(sp.conditional_aj_cif(aj, [0, 1], 2), [.5, .5])
        np.testing.assert_allclose(sp.conditional_aj_cif(aj, [0, 2], 3), [.5, 0])


if __name__ == "__main__":
    unittest.main()
