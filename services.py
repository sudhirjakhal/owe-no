from database import SessionLocal, engine
import models

def createDatabase():
    models.Base.metadata.create_all(bind=engine)

def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()