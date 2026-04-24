"""SodhiCable MES v4.0 — Configuration"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    """Base configuration."""
    DATABASE = os.path.join(BASE_DIR, "database", "sodhicable_mes.db")
    SECRET_KEY = os.environ.get("SECRET_KEY", "sodhicable-mes-dev-key-2026")
    DEBUG = False
    TESTING = False

    MES_CONFIG = {
        "oee_world_class": 0.85,
        "oee_acceptable": 0.60,
        "kpi_thresholds": {
            "OEE (%)":          (60, 85),
            "Throughput (u/h)": (0.1, 0.3),
            "WIP (units)":      (5, 15),
            "On-Time (%)":      (80, 95),
            "FPY (%)":          (95, 97),
            "Utilization (%)":  (70, 90),
        },
        "spc_subgroup_size": 5,
        "cpk_target": 1.33,
        "sim_arrival_rate": 0.30,
        "dispatch_w_urgency": 0.4,
        "dispatch_w_priority": 0.4,
        "dispatch_w_changeover": 0.2,
        "fallback_quality": 0.97,
        "fallback_performance": 0.80,
    }

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DATABASE = os.path.join(BASE_DIR, "database", "sodhicable_mes_test.db")

class ProductionConfig(Config):
    """Production configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY")
    # SECRET_KEY must be set in production via environment variable

configs = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

# Backwards compatibility — modules that do `from config import DATABASE, MES_CONFIG`
_active = configs[os.environ.get("FLASK_ENV", "development")]
DATABASE = _active.DATABASE
SECRET_KEY = _active.SECRET_KEY
DEBUG = _active.DEBUG
MES_CONFIG = _active.MES_CONFIG
