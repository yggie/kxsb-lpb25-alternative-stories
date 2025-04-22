import sqlalchemy

engine = sqlalchemy.create_engine(
    sqlalchemy.engine.URL(
        drivername="postgresql",
        username="postgres",
        password="example",
        port=5432,
        host="localhost",
        database="postgres",
        query={},
    )
)
connection = engine.connect()
