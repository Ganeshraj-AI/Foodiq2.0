# statistics_service.py
import pandas as pd
import numpy as np
import os

WEEKDAY_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

class StatisticsService:
    REQUIRED_COLUMNS = {"date", "dish_name", "quantity_prepared", "quantity_consumed"}

    def __init__(self, csv_path):
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV not found at: {csv_path}")
        self.df = pd.read_csv(csv_path)
        # Try common ISO first, then fall back to day-first parse
        try:
            self.df["date"] = pd.to_datetime(self.df["date"], format="%Y-%m-%d", errors="raise")
        except Exception:
            self.df["date"] = pd.to_datetime(self.df["date"], dayfirst=True, errors="coerce")
        self._validate_columns()
        self._preprocess()

    def _validate_columns(self):
        missing = self.REQUIRED_COLUMNS - set(self.df.columns)
        if missing:
            raise ValueError(f"Missing columns in data: {missing}")

    def _preprocess(self):
        self.df["quantity_prepared"] = pd.to_numeric(self.df["quantity_prepared"], errors="coerce").fillna(0).astype(float)
        self.df["quantity_consumed"] = pd.to_numeric(self.df["quantity_consumed"], errors="coerce").fillna(0).astype(float)
        self.df["surplus"] = self.df["quantity_prepared"] - self.df["quantity_consumed"]
        self.df["dish_name"] = self.df["dish_name"].astype(str).str.strip().str.lower()
        self.df["day_of_week"] = self.df["date"].dt.day_name()
        self.df["day_of_week"] = pd.Categorical(self.df["day_of_week"], categories=WEEKDAY_ORDER, ordered=True)
        self.df["year"] = self.df["date"].dt.year
        self.df["month"] = self.df["date"].dt.to_period("M").astype(str)
        # aggregate duplicates
        self.df = self.df.groupby(["date","dish_name"], as_index=False).agg({
            "quantity_prepared":"sum",
            "quantity_consumed":"sum",
            "surplus":"sum",
            "day_of_week":"first",
            "year":"first",
            "month":"first"
        })

    # 1. overall
    def overall_summary(self):
        total_prepared = self.df["quantity_prepared"].sum()
        total_consumed = self.df["quantity_consumed"].sum()
        total_surplus = self.df["surplus"].sum()
        avg_surplus = float(self.df["surplus"].mean()) if not self.df.empty else 0.0
        avg_consumption_rate = (total_consumed / total_prepared) * 100 if total_prepared else 0.0
        days = int(self.df["date"].nunique())
        return {
            "total_prepared": int(total_prepared),
            "total_consumed": int(total_consumed),
            "total_surplus": int(total_surplus),
            "avg_surplus_per_day": round(avg_surplus, 2),
            "avg_consumption_rate_percent": round(avg_consumption_rate, 2),
            "days_reported": days
        }

    # 2. daily stats
    def daily_stats(self):
        daily = self.df.groupby("date").agg({
            "quantity_prepared":"sum",
            "quantity_consumed":"sum",
            "surplus":"sum"
        }).reset_index().sort_values("date")
        daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
        return daily.to_dict(orient="records")

    # 3. dish-wise
    def dish_wise_stats(self, top_n=None):
        dish = self.df.groupby("dish_name").agg({
            "quantity_prepared":"sum",
            "quantity_consumed":"sum",
            "surplus":"sum"
        }).reset_index()
        dish["waste_rate_percent"] = np.where(dish["quantity_prepared"]>0,
                                             (dish["surplus"] / dish["quantity_prepared"]) * 100,
                                             0.0)
        dish = dish.sort_values("waste_rate_percent", ascending=False)
        if top_n:
            dish = dish.head(top_n)
        return dish.to_dict(orient="records")

    def most_wasted_dish(self):
        stats = self.dish_wise_stats(top_n=1)
        return stats[0] if stats else None

    def weekday_trends(self):
        counts = (self.df.groupby("day_of_week")["date"].nunique().reindex(WEEKDAY_ORDER).fillna(0).astype(int))
        agg = (self.df.groupby("day_of_week")
               .agg(total_prepared=("quantity_prepared","sum"),
                    total_consumed=("quantity_consumed","sum"),
                    total_surplus=("surplus","sum"))
               .reindex(WEEKDAY_ORDER)
               .fillna(0))
        agg["days_count"] = counts
        agg["avg_surplus_per_day"] = np.where(agg["days_count"]>0, agg["total_surplus"]/agg["days_count"], 0.0)
        agg = agg.reset_index()
        agg["day_of_week"] = agg["day_of_week"].astype(str)
        return agg.to_dict(orient="records")

    def surplus_exceeds_threshold(self, date, threshold_qty):
        d = pd.to_datetime(date).normalize()
        subset = self.df[self.df["date"] == d]
        res = subset[subset["surplus"] >= threshold_qty].sort_values("surplus", ascending=False)
        return res.to_dict(orient="records")

    # ML export hook
    def get_dataset_for_ai(self):
        return self.df[[
            "date","dish_name","quantity_prepared","quantity_consumed","surplus","day_of_week"
        ]]
