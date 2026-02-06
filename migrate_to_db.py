from database import init_db, ensure_name_column, create_user

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    ensure_name_column()

    print("Creating dev user...")
    create_user("dev@example.com", "Dev")

    print("Database migration complete.")
