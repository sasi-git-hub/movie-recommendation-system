import app as m


def titles_for_age(age: int, n: int = 8):
    from app import db, User, Rating, get_recommendations, app as flask_app

    with flask_app.app_context():
        Rating.query.delete()
        User.query.delete()
        db.session.commit()

        u = User(username=f"user{age}", email=f"user{age}@x.com", password_hash="x", age=age)
        db.session.add(u)
        db.session.commit()

        return [mv.title for mv, _score in get_recommendations(u.id, num_recommendations=n)]


if __name__ == "__main__":
    m.init_db()
    print("KID (8):   ", titles_for_age(8))
    print("YOUTH (15):", titles_for_age(15))
    print("ADULT (25):", titles_for_age(25))

