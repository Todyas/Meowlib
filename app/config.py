class Config:
    SECRET_KEY = "Cheese"
    UPLOAD_DIR = "meowlib/app/uploads"


cfg = Config
print(f"Booting ok, {cfg.SECRET_KEY}, {cfg.UPLOAD_DIR}")
