from database import init_db, create_user

if __name__ == "__main__":
    print("Initializing database...")
    init_db()

    print("Creating dev user...")
    create_user("dev@example.com", "Dev")

    print("Database migration complete.")
