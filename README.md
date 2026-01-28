# Movie Recommendation System

A comprehensive Movie Recommendation System that provides personalized movie suggestions based on user preferences, ratings, and collaborative filtering algorithms.

## Features

- **User Registration and Profiles**: Secure user registration and authentication system
- **Movie Ratings and Preferences**: Users can rate movies (1-5 scale) and set genre preferences
- **Recommendation Algorithm**: Hybrid recommendation system using:
  - Collaborative Filtering (user-based similarity)
  - Content-based Filtering (genre preferences)
- **User Feedback and Ratings**: Users can submit ratings and reviews for movies
- **Movie Catalog**: Browse and search through a collection of movies
- **Personalized Dashboard**: View recommendations and rated movies

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML, CSS, JavaScript
- **Recommendation Engine**: NumPy, Pandas, Scikit-learn (cosine similarity)

## Installation

1. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

2. **Run the application**:
```bash
python app.py
```

3. **Access the application**:
   - Open your browser and navigate to `http://localhost:5000`
   - The database will be automatically created and seeded with sample movies

## Usage

1. **Register a new account** or **login** with existing credentials
2. **Browse movies** from the catalog
3. **Rate movies** you've watched (1-5 stars)
4. **Set your preferences** by selecting favorite genres
5. **View personalized recommendations** on your dashboard
6. **Submit reviews** along with your ratings

## Project Structure

```
.
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/            # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── register.html
│   ├── login.html
│   ├── dashboard.html
│   ├── movies.html
│   ├── movie_detail.html
│   └── preferences.html
├── static/
│   └── css/
│       └── style.css     # Stylesheet
└── movie_recommendations.db  # SQLite database (created automatically)
```

## Database Models

- **User**: Stores user account information
- **Movie**: Stores movie details (title, genre, year, director, description)
- **Rating**: Stores user ratings and reviews for movies
- **Preference**: Stores user genre preferences

## Recommendation Algorithm

The system uses a hybrid approach:

1. **Collaborative Filtering**: Finds users with similar rating patterns and recommends movies they liked
2. **Content-based Filtering**: Recommends movies based on user's preferred genres
3. **Hybrid Scoring**: Combines both approaches for better recommendations

## Use Cases Implemented

✅ User Registration and Profiles  
✅ Movie Ratings and Preferences  
✅ Recommendation Algorithm  
✅ User Feedback and Ratings  

## Notes

- The database is automatically initialized with 20 sample movies on first run
- User passwords are securely hashed using Werkzeug
- The recommendation algorithm improves as more users rate movies
- All user data is stored locally in SQLite database

## Future Enhancements

- Movie poster images
- Advanced filtering options
- Social features (follow users, see friends' ratings)
- Machine learning model integration
- Movie trailers and additional metadata
