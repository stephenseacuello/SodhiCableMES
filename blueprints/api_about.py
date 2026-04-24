"""Informational: System architecture & ISA-95 reference.

SodhiCable MES — About / Company Profile Blueprint
Serves the about page and live database statistics.
"""
from flask import Blueprint, render_template, jsonify, request

bp = Blueprint("about", __name__)


@bp.route("/about")
def about_page():
    return render_template("about.html")


@bp.route("/api/docs")
def api_docs():
    """Serve Swagger UI for API documentation."""
    return render_template("api_docs.html")


@bp.route("/api/about/stats")
def about_stats():
    """Return live database row counts for the about page."""
    from db import get_db
    db = get_db()

    tables_to_count = [
        "products", "work_centers", "materials", "customers",
        "work_orders", "personnel", "equipment", "spc_readings",
        "process_data_live",
    ]

    stats = {}
    for tbl in tables_to_count:
        try:
            row = db.execute(f"SELECT COUNT(*) AS c FROM {tbl}").fetchone()
            stats[tbl] = row["c"] if row else 0
        except Exception:
            stats[tbl] = 0

    # Total table count from sqlite_master
    try:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table'"
        ).fetchone()
        stats["total_tables"] = row["c"] if row else 0
    except Exception:
        stats["total_tables"] = 0

    return jsonify(stats)
