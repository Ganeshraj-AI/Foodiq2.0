# api.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
import os
from statistics_service import StatisticsService

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)

# resolve csv path relative to this file
BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(BASE_DIR, "canteen_data.csv")

svc = None
try:
    svc = StatisticsService(csv_path=CSV_PATH)
    logging.info("StatisticsService loaded. rows=%d", len(svc.df))
except Exception as e:
    logging.exception("Failed to initialize StatisticsService: %s", e)

@app.route("/")
def index():
    return jsonify({"message":"Canteen stats API. Try /api/overall, /api/daily, /api/dishes, /api/weekday"})

@app.route("/api/overall")
def overall():
    if svc is None:
        return jsonify({"error":"backend not initialized - check server logs"}), 500
    try:
        return jsonify(svc.overall_summary())
    except Exception as e:
        logging.exception("overall endpoint error: %s", e)
        return jsonify({"error":"internal error"}), 500

@app.route("/api/daily")
def daily():
    if svc is None:
        return jsonify({"error":"backend not initialized - check server logs"}), 500
    try:
        return jsonify(svc.daily_stats())
    except Exception as e:
        logging.exception("daily endpoint error: %s", e)
        return jsonify({"error":"internal error"}), 500

@app.route("/api/dishes")
def dishes():
    if svc is None:
        return jsonify({"error":"backend not initialized - check server logs"}), 500
    try:
        top = request.args.get("top", None)
        if top:
            return jsonify(svc.dish_wise_stats(top_n=int(top)))
        return jsonify(svc.dish_wise_stats())
    except Exception as e:
        logging.exception("dishes endpoint error: %s", e)
        return jsonify({"error":"internal error"}), 500

@app.route("/api/weekday")
def weekday():
    if svc is None:
        return jsonify({"error":"backend not initialized - check server logs"}), 500
    try:
        return jsonify(svc.weekday_trends())
    except Exception as e:
        logging.exception("weekday endpoint error: %s", e)
        return jsonify({"error":"internal error"}), 500

@app.route("/api/threshold")
def threshold():
    if svc is None:
        return jsonify({"error":"backend not initialized - check server logs"}), 500
    date = request.args.get("date")
    try:
        threshold = float(request.args.get("threshold", 0))
    except Exception:
        threshold = 0.0
    if not date:
        return jsonify({"error":"provide date param YYYY-MM-DD"}), 400
    try:
        return jsonify(svc.surplus_exceeds_threshold(date, threshold))
    except Exception as e:
        logging.exception("threshold endpoint error: %s", e)
        return jsonify({"error":"internal error"}), 500

if __name__ == "__main__":
    logging.info("Starting Flask app. CSV_PATH=%s", CSV_PATH)
    app.run(debug=True, port=5000)
