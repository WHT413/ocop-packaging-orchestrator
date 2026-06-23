from ocop_pack.infrastructure.persistence.session import init_db, make_engine

init_db(make_engine())
print("database initialized")
