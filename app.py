"""
SodhiCable MES v4.0 — Flask Application

Best-in-class Manufacturing Execution System for wire & cable production.
Web-based dashboard with real-time simulation, MESA-11 functions,
12 optimization solvers, DES, MRP, SPC, OEE, and TPM integration.

Run: flask run
"""
import os
from flask import Flask

from config import DATABASE, SECRET_KEY, DEBUG
from db import get_db, close_db


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["DEBUG"] = DEBUG
    app.config["DATABASE"] = DATABASE

    # Make get_db available to blueprints
    app.teardown_appcontext(close_db)

    # Register blueprints — dashboard + all MESA function APIs + analytics
    from blueprints.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    # Register all API blueprints (each handles its own routes)
    blueprint_modules = [
        'api_scheduling', 'api_quality', 'api_workorders', 'api_equipment',
        'api_traceability', 'api_performance', 'api_labor', 'api_documents',
        'api_inventory', 'api_process', 'api_des', 'api_mrp',
        'api_executive', 'api_bottleneck', 'api_extras', 'api_oee', 'api_demo',
        'api_suppliers', 'api_sales', 'api_scada', 'api_about', 'api_ai',
        'api_system', 'api_erp',
    ]
    for mod_name in blueprint_modules:
        try:
            mod = __import__(f'blueprints.{mod_name}', fromlist=['bp'])
            app.register_blueprint(mod.bp)
        except (ImportError, AttributeError) as e:
            print(f"  Note: Blueprint {mod_name} not loaded: {e}")

    app.get_db = get_db

    return app


# Create the app instance for `flask run`
app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))

    # Auto-start OPC-UA simulator for live data generation
    try:
        from engines.opcua_sim import start as opcua_start
        opcua_start(DATABASE, interval=5)
        print("  OPC-UA Simulator: RUNNING (5s interval)")
    except Exception as e:
        print(f"  OPC-UA Simulator: Not started ({e})")

    # Auto-start ERP simulator for Level 4 business cycle
    try:
        from engines.erp_sim import start as erp_start
        erp_start(DATABASE, interval=10)
        print("  ERP Simulator:    RUNNING (10s interval)")
    except Exception as e:
        print(f"  ERP Simulator:    Not started ({e})")

    print(f"\n  SodhiCable MES v4.0 — http://localhost:{port}")
    print(f"  Demo: http://localhost:{port}/demo")
    print(f"  ERP:  http://localhost:{port}/erp")
    print(f"  Live data: OPC-UA sim (L0-1) + ERP sim (L4) active\n")
    app.run(debug=True, port=port, use_reloader=False)
