# config_local.py
class ConfigLocal:
    # Cambia estos valores según tu DB en DBeaver
    SQLALCHEMY_DATABASE_URI = "postgresql://postgres:rhQVnJkBVeFlcECwWQsRYCUGbfOCcDQA@localhost:5432/railway"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True
