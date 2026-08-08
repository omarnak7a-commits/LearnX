@app.api_route("/api/migrate", methods=["GET", "POST"])
@app.api_route("/migrate", methods=["GET", "POST"])
def migrate_database() -> dict:
    try:
        import app.models
        from app.core.db import Base, engine
        Base.metadata.create_all(bind=engine)
        return {
            "status": "ok",
            "message": "Database tables created successfully on Supabase Postgres",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.on_event("startup")
def auto_create_tables():
    try:
        import app.models
        from app.core.db import Base, engine
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
