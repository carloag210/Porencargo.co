import os 

class Config:
    SECRET_KEY =os.getenv("SECRET__KEY")  # cambia esto a algo largo y seguro
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    # KEY_db = os.getenv("KEY")
    # SQLALCHEMY_DATABASE_URI = f"postgresql://postgres:{KEY_db}@localhost:5432/data_base_porencargo"

    SQLALCHEMY_TRACK_MODIFICATIONS = False  
