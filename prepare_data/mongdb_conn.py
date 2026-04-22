import pymongo


def test_connection():
    client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
        print("MongoDB connected")
    except Exception as exc:
        print(f"MongoDB connect failed: {exc}")
    finally:
        client.close()


if __name__ == "__main__":
    test_connection()
