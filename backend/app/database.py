import sqlalchemy
from app.config import Config

engine = sqlalchemy.create_engine(
    sqlalchemy.engine.URL(
        drivername="postgresql",
        username=Config.db_username,
        password=Config.db_password,
        port=Config.db_port,
        host=Config.db_host,
        database=Config.db_database,
        query={},
    )
)
connection = engine.connect()
