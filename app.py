from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import numpy as np
import pandas as pd
from datetime import datetime
import os
import requests
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///movie_recommendations.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    age = db.Column(db.Integer, nullable=True)  # User age for age-based recommendations
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    ratings = db.relationship('Rating', backref='user', lazy=True, cascade='all, delete-orphan')
    preferences = db.relationship('Preference', backref='user', lazy=True, cascade='all, delete-orphan')

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    genre = db.Column(db.String(100))
    year = db.Column(db.Integer)
    director = db.Column(db.String(100))
    cast = db.Column(db.String(500))  # Main cast members (comma-separated)
    description = db.Column(db.Text)
    poster_url = db.Column(db.String(500))
    age_rating = db.Column(db.String(10))  # PG, PG-13, R, etc.
    
    # Relationships
    ratings = db.relationship('Rating', backref='movie', lazy=True)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    rating = db.Column(db.Float, nullable=False)  # 1-5 scale
    review = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Ensure one rating per user per movie
    __table_args__ = (db.UniqueConstraint('user_id', 'movie_id', name='unique_user_movie_rating'),)

class Preference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    genre = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, default=1.0)  # Preference weight

# External movie API (OMDb) setup
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        age = request.form.get('age')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        try:
            age_int = int(age) if age else None
        except (ValueError, TypeError):
            age_int = None
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            age=age_int
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            # Show age-based recommendations message if age is set
            if user.age:
                flash(f'Welcome back! Here are personalized recommendations based on your age ({user.age}) and preferences.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's rated movies
    user_ratings = Rating.query.filter_by(user_id=current_user.id).all()
    rated_movie_ids = [r.movie_id for r in user_ratings]
    
    # Get recommendations
    recommendations = get_recommendations(current_user.id)
    
    # Get all movies (excluding already rated ones)
    all_movies = Movie.query.filter(~Movie.id.in_(rated_movie_ids)).limit(20).all()
    
    return render_template('dashboard.html', 
                         user_ratings=user_ratings,
                         recommendations=recommendations,
                         all_movies=all_movies)

@app.route('/movies')
@login_required
def movies():
    search = request.args.get('search', '')
    genre_filter = request.args.get('genre', '')
    
    query = Movie.query
    if search:
        query = query.filter(Movie.title.contains(search))
    if genre_filter:
        query = query.filter(Movie.genre.contains(genre_filter))
    
    movies = query.limit(50).all()
    genres = db.session.query(Movie.genre).distinct().all()
    genres = [g[0] for g in genres if g[0]]
    
    return render_template('movies.html', movies=movies, genres=genres, 
                         search=search, genre_filter=genre_filter)

@app.route('/movie/<int:movie_id>')
@login_required
def movie_detail(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    user_rating = Rating.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
    all_ratings = Rating.query.filter_by(movie_id=movie_id).all()
    avg_rating = np.mean([r.rating for r in all_ratings]) if all_ratings else 0
    
    return render_template('movie_detail.html', movie=movie, 
                         user_rating=user_rating, avg_rating=avg_rating,
                         total_ratings=len(all_ratings))

@app.route('/rate_movie', methods=['POST'])
@login_required
def rate_movie():
    movie_id = int(request.form.get('movie_id'))
    rating = float(request.form.get('rating'))
    review = request.form.get('review', '')
    
    existing_rating = Rating.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
    
    if existing_rating:
        existing_rating.rating = rating
        existing_rating.review = review
        flash('Rating updated successfully', 'success')
    else:
        new_rating = Rating(
            user_id=current_user.id,
            movie_id=movie_id,
            rating=rating,
            review=review
        )
        db.session.add(new_rating)
        flash('Rating submitted successfully', 'success')
    
    db.session.commit()
    return redirect(url_for('movie_detail', movie_id=movie_id))

@app.route('/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    if request.method == 'POST':
        # Update age if provided
        age = request.form.get('age')
        if age:
            try:
                current_user.age = int(age)
            except (ValueError, TypeError):
                pass
        
        # Clear existing preferences
        Preference.query.filter_by(user_id=current_user.id).delete()
        
        # Add new preferences
        selected_genres = request.form.getlist('genres')
        for genre in selected_genres:
            preference = Preference(user_id=current_user.id, genre=genre)
            db.session.add(preference)
        
        db.session.commit()
        flash('Preferences updated successfully', 'success')
        return redirect(url_for('dashboard'))
    
    # Get all available genres
    genres = db.session.query(Movie.genre).distinct().all()
    genres = [g[0] for g in genres if g[0]]
    
    # Get user's current preferences
    user_preferences = Preference.query.filter_by(user_id=current_user.id).all()
    preferred_genres = [p.genre for p in user_preferences]
    
    return render_template('preferences.html', genres=genres, preferred_genres=preferred_genres)

@app.route('/api/recommendations')
@login_required
def api_recommendations():
    recommendations = get_recommendations(current_user.id)
    return jsonify([{
        'id': m.id,
        'title': m.title,
        'genre': m.genre,
        'year': m.year,
        'score': score
    } for m, score in recommendations])

# Recommendation Algorithm
def get_recommendations(user_id, num_recommendations=10):
    """
    Enhanced Hybrid recommendation system:
    1. Age-based filtering (age-appropriate content)
    2. Similarity-based (for watched movies: genre, cast, director, year)
    3. Collaborative filtering (user-based)
    4. Content-based filtering (genre preferences)
    """
    user = User.query.get(user_id)
    user_ratings = Rating.query.filter_by(user_id=user_id).all()
    user_rated_movie_ids = [r.movie_id for r in user_ratings]
    movie_scores = {}
    
    # 1. Age-based recommendations (if age is provided) - HIGH PRIORITY
    if user and user.age:
        age_based_movies = get_age_based_recommendations(user.age, user_rated_movie_ids, num_recommendations * 2)
        for movie in age_based_movies:
            if movie.id not in user_rated_movie_ids:
                # Higher priority for age-based (especially for children)
                priority = 0.8 if user.age < 13 else 0.6
                movie_scores[movie.id] = priority  # Age-based score
    
    # 2. Similarity-based recommendations (if user has watched movies)
    if user_ratings:
        user_age_for_filter = user.age if user else None
        similarity_movies = get_similarity_based_recommendations(user_id, user_rated_movie_ids, num_recommendations * 2, user_age_for_filter)
        for movie, score in similarity_movies:
            # FILTER BY AGE - Only add if age-appropriate
            if movie.id not in user_rated_movie_ids:
                if user and user.age:
                    if not is_age_appropriate(movie, user.age):
                        continue  # Skip age-inappropriate movies
                if movie.id not in movie_scores:
                    movie_scores[movie.id] = score
                else:
                    movie_scores[movie.id] += score * 0.5  # Boost similarity matches
    
    # 3. Collaborative filtering (if enough ratings exist)
    all_ratings = Rating.query.all()
    if len(all_ratings) > 10 and user_ratings:
        user_age_for_filter = user.age if user else None
        collaborative_movies = get_collaborative_recommendations(user_id, user_rated_movie_ids, num_recommendations, user_age_for_filter)
        for movie, score in collaborative_movies:
            # FILTER BY AGE - Only add if age-appropriate
            if movie.id not in user_rated_movie_ids:
                if user and user.age:
                    if not is_age_appropriate(movie, user.age):
                        continue  # Skip age-inappropriate movies
                if movie.id not in movie_scores:
                    movie_scores[movie.id] = score * 0.4
                else:
                    movie_scores[movie.id] += score * 0.3
    
    # 4. Content-based (genre preferences)
    user_age_for_filter = user.age if user else None
    content_based = get_content_based_recommendations(
        user_id,
        num_recommendations * 2,
        user_age=user_age_for_filter,
        exclude_movie_ids=user_rated_movie_ids
    )
    for movie in content_based:
        # FILTER BY AGE - Only add if age-appropriate
        if movie.id not in user_rated_movie_ids:
            if user and user.age:
                if not is_age_appropriate(movie, user.age):
                    continue  # Skip age-inappropriate movies
            if movie.id not in movie_scores:
                movie_scores[movie.id] = 0.5
            else:
                movie_scores[movie.id] += 0.2
    
    # Sort by score and get top recommendations
    sorted_movies = sorted(movie_scores.items(), key=lambda x: x[1], reverse=True)
    
    recommendations = []
    for movie_id, score in sorted_movies[:num_recommendations * 2]:  # Get more to filter
        movie = Movie.query.get(movie_id)
        if movie:
            # FINAL AGE FILTER - Double check before adding to recommendations
            if user and user.age:
                if not is_age_appropriate(movie, user.age):
                    continue  # Skip age-inappropriate movies
            recommendations.append((movie, min(score, 1.0)))  # Cap score at 1.0
            if len(recommendations) >= num_recommendations:
                break  # Stop when we have enough
    
    # If we don't have enough recommendations, fill with age-appropriate or popular movies
    if len(recommendations) < num_recommendations:
        if user and user.age:
            fallback_movies = get_age_based_recommendations(user.age, user_rated_movie_ids + [m[0].id for m in recommendations], num_recommendations - len(recommendations))
        else:
            fallback_movies = Movie.query.filter(~Movie.id.in_(user_rated_movie_ids + [m[0].id for m in recommendations])).limit(num_recommendations - len(recommendations)).all()
        
        for movie in fallback_movies:
            recommendations.append((movie, 0.3))
    
    return recommendations

def is_age_appropriate(movie, age):
    """Check if a movie is appropriate for the given age"""
    if not age:
        return True  # If no age provided, allow all
    
    if not movie.age_rating:
        # If no rating, be conservative for children
        if age < 13:
            return False
        return True
    
    if age <= 7:
        # Very young: Only G rated
        return movie.age_rating == 'G'
    elif age <= 12:
        # Children: G and PG
        return movie.age_rating in ['G', 'PG']
    elif age < 18:
        # Teens: G, PG, PG-13 (NO R)
        return movie.age_rating in ['G', 'PG', 'PG-13']
    else:
        # Adults: All ratings
        return True

def get_age_based_recommendations(age, exclude_movie_ids, num_recommendations=10):
    """Get age-appropriate movie recommendations with age-specific genre preferences"""
    exclude_list = exclude_movie_ids if exclude_movie_ids else []
    movies = []
    
    # Kids (0-12): Focus on Animation, Family, Adventure, Comedy
    if age <= 12:
        # Priority 1: Animation and Family movies (most popular with kids)
        priority_movies = Movie.query.filter(
            ~Movie.id.in_(exclude_list)
        ).filter(
            (Movie.age_rating.in_(['G', 'PG'])) | (Movie.age_rating == None)
        ).filter(
            (Movie.genre.contains('Animation') | 
             Movie.genre.contains('Family'))
        ).order_by(Movie.year.desc()).limit(num_recommendations * 2).all()
        movies.extend(priority_movies)
        
        # Priority 2: Adventure and Comedy (also popular with kids)
        if len(movies) < num_recommendations:
            additional = Movie.query.filter(
                ~Movie.id.in_(exclude_list + [m.id for m in movies])
            ).filter(
                (Movie.age_rating.in_(['G', 'PG'])) | (Movie.age_rating == None)
            ).filter(
                (Movie.genre.contains('Adventure') | 
                 Movie.genre.contains('Comedy'))
            ).order_by(Movie.year.desc()).limit(num_recommendations * 2).all()
            movies.extend(additional)
        
        # Priority 3: Any other G/PG rated movies
        if len(movies) < num_recommendations:
            fallback = Movie.query.filter(
                ~Movie.id.in_(exclude_list + [m.id for m in movies])
            ).filter(
                (Movie.age_rating.in_(['G', 'PG'])) | (Movie.age_rating == None)
            ).order_by(Movie.year.desc()).limit(num_recommendations - len(movies)).all()
            movies.extend(fallback)
    
    # Youth/Teens (13-17): Focus on Action, Sci-Fi, Adventure, Comedy, Thriller (popular with young adults)
    elif age < 18:
        # Priority 1: Action, Sci-Fi, Adventure (most popular with youth)
        priority_movies = Movie.query.filter(
            ~Movie.id.in_(exclude_list)
        ).filter(
            (Movie.age_rating.in_(['PG-13', 'PG'])) | (Movie.age_rating == None)
        ).filter(
            (Movie.genre.contains('Action') | 
             Movie.genre.contains('Sci-Fi') | 
             Movie.genre.contains('Adventure'))
        ).order_by(Movie.year.desc()).limit(num_recommendations * 2).all()
        movies.extend(priority_movies)
        
        # Priority 2: Comedy, Thriller, Drama (also popular with youth)
        if len(movies) < num_recommendations:
            additional = Movie.query.filter(
                ~Movie.id.in_(exclude_list + [m.id for m in movies])
            ).filter(
                (Movie.age_rating.in_(['PG-13', 'PG', 'G'])) | (Movie.age_rating == None)
            ).filter(
                (Movie.genre.contains('Comedy') | 
                 Movie.genre.contains('Thriller') | 
                 Movie.genre.contains('Drama'))
            ).order_by(Movie.year.desc()).limit(num_recommendations * 2).all()
            movies.extend(additional)
        
        # Priority 3: Any other PG-13/PG/G rated movies (NO R rated)
        if len(movies) < num_recommendations:
            fallback = Movie.query.filter(
                ~Movie.id.in_(exclude_list + [m.id for m in movies])
            ).filter(
                (Movie.age_rating.in_(['PG-13', 'PG', 'G'])) | (Movie.age_rating == None)
            ).order_by(Movie.year.desc()).limit(num_recommendations - len(movies)).all()
            movies.extend(fallback)
    
    # Adults (18+): All movies, but prioritize popular genres
    else:
        # Priority 1: Action, Drama, Thriller, Crime (popular with adults)
        priority_movies = Movie.query.filter(
            ~Movie.id.in_(exclude_list)
        ).filter(
            (Movie.genre.contains('Action') | 
             Movie.genre.contains('Drama') | 
             Movie.genre.contains('Thriller') | 
             Movie.genre.contains('Crime'))
        ).order_by(Movie.year.desc()).limit(num_recommendations * 2).all()
        movies.extend(priority_movies)
        
        # Priority 2: All other movies
        if len(movies) < num_recommendations:
            fallback = Movie.query.filter(
                ~Movie.id.in_(exclude_list + [m.id for m in movies])
            ).order_by(Movie.year.desc()).limit(num_recommendations - len(movies)).all()
            movies.extend(fallback)
    
    # Remove duplicates and return
    seen = set()
    unique_movies = []
    for movie in movies:
        if movie.id not in seen:
            seen.add(movie.id)
            unique_movies.append(movie)
            if len(unique_movies) >= num_recommendations:
                break
    
    return unique_movies[:num_recommendations]

def get_age_group(age):
    """Return an age-group label used for recommendations."""
    if age is None:
        return None
    if age <= 12:
        return "kid"
    if age < 18:
        return "youth"
    return "adult"

def get_similarity_based_recommendations(user_id, exclude_movie_ids, num_recommendations=10, user_age=None):
    """Recommend movies similar to ones the user has watched (based on genre, cast, director, year)"""
    user_ratings = Rating.query.filter_by(user_id=user_id).all()
    if not user_ratings:
        return []
    
    # Get all watched movies
    watched_movies = [Movie.query.get(r.movie_id) for r in user_ratings if Movie.query.get(r.movie_id)]
    
    movie_scores = {}
    
    for watched_movie in watched_movies:
        if not watched_movie:
            continue
            
        # Find similar movies based on multiple factors
        # Apply age filtering at query level for better performance
        query = Movie.query.filter(
            ~Movie.id.in_(exclude_movie_ids + [watched_movie.id])
        )
        
        # Add age rating filter if age is provided
        if user_age:
            if user_age <= 7:
                query = query.filter((Movie.age_rating == 'G') | (Movie.age_rating == None))
            elif user_age <= 12:
                query = query.filter((Movie.age_rating.in_(['G', 'PG'])) | (Movie.age_rating == None))
            elif user_age < 18:
                query = query.filter((Movie.age_rating.in_(['G', 'PG', 'PG-13'])) | (Movie.age_rating == None))
            # For adults (18+), no filter needed
        
        similar_movies = query.all()
        
        for movie in similar_movies:
            # Double-check age appropriateness (safety check)
            if user_age and not is_age_appropriate(movie, user_age):
                continue  # Skip age-inappropriate movies
            
            similarity_score = 0.0
            
            # Genre similarity (40% weight)
            if watched_movie.genre and movie.genre:
                watched_genres = set([g.strip() for g in watched_movie.genre.split(',')])
                movie_genres = set([g.strip() for g in movie.genre.split(',')])
                common_genres = watched_genres.intersection(movie_genres)
                if common_genres:
                    similarity_score += 0.4 * (len(common_genres) / max(len(watched_genres), len(movie_genres)))
            
            # Director similarity (20% weight)
            if watched_movie.director and movie.director:
                if watched_movie.director.lower() == movie.director.lower():
                    similarity_score += 0.2
            
            # Cast similarity (20% weight)
            if watched_movie.cast and movie.cast:
                watched_cast = set([c.strip().lower() for c in watched_movie.cast.split(',')])
                movie_cast = set([c.strip().lower() for c in movie.cast.split(',')])
                common_cast = watched_cast.intersection(movie_cast)
                if common_cast:
                    similarity_score += 0.2 * (len(common_cast) / max(len(watched_cast), len(movie_cast), 1))
            
            # Year similarity (20% weight) - prefer movies from similar era
            if watched_movie.year and movie.year:
                year_diff = abs(watched_movie.year - movie.year)
                if year_diff <= 5:
                    similarity_score += 0.2
                elif year_diff <= 10:
                    similarity_score += 0.1
                elif year_diff <= 20:
                    similarity_score += 0.05
            
            if similarity_score > 0:
                if movie.id not in movie_scores:
                    movie_scores[movie.id] = similarity_score
                else:
                    movie_scores[movie.id] = max(movie_scores[movie.id], similarity_score)
    
    # Sort and return top recommendations
    sorted_movies = sorted(movie_scores.items(), key=lambda x: x[1], reverse=True)
    recommendations = []
    for movie_id, score in sorted_movies[:num_recommendations]:
        movie = Movie.query.get(movie_id)
        if movie:
            recommendations.append((movie, score))
    
    return recommendations

def get_collaborative_recommendations(user_id, exclude_movie_ids, num_recommendations=10, user_age=None):
    """Collaborative filtering: find similar users and recommend their liked movies"""
    all_ratings = Rating.query.all()
    if not all_ratings:
        return []
    
    # Build user-item matrix
    ratings_data = []
    for rating in all_ratings:
        ratings_data.append({
            'user_id': rating.user_id,
            'movie_id': rating.movie_id,
            'rating': rating.rating
        })
    
    df_ratings = pd.DataFrame(ratings_data)
    
    try:
        user_movie_matrix = df_ratings.pivot_table(index='user_id', columns='movie_id', values='rating')
        user_movie_matrix = user_movie_matrix.fillna(0)
        
        # Calculate cosine similarity between users
        user_similarities = cosine_similarity(user_movie_matrix)
        
        # Get current user's index
        user_ids = user_movie_matrix.index.tolist()
        if user_id not in user_ids:
            return []
        
        user_idx = user_ids.index(user_id)
        
        # Get top similar users
        similar_users = np.argsort(user_similarities[user_idx])[::-1][1:6]  # Top 5 similar users
        
        # Get movies rated by similar users
        recommended_movies = {}
        for similar_user_idx in similar_users:
            similar_user_id = user_ids[similar_user_idx]
            similarity_score = user_similarities[user_idx][similar_user_idx]
            
            if similarity_score > 0:
                similar_user_ratings = Rating.query.filter_by(user_id=similar_user_id).all()
                for rating in similar_user_ratings:
                    if rating.movie_id not in exclude_movie_ids:
                        # Check age appropriateness before adding
                        movie = Movie.query.get(rating.movie_id)
                        if movie and user_age:
                            if not is_age_appropriate(movie, user_age):
                                continue  # Skip age-inappropriate movies
                        if rating.movie_id not in recommended_movies:
                            recommended_movies[rating.movie_id] = []
                        recommended_movies[rating.movie_id].append(rating.rating * similarity_score)
        
        # Calculate weighted scores
        movie_scores = {}
        for movie_id, scores in recommended_movies.items():
            movie_scores[movie_id] = np.mean(scores) / 5.0  # Normalize to 0-1
        
        # Sort and return
        sorted_movies = sorted(movie_scores.items(), key=lambda x: x[1], reverse=True)
        recommendations = []
        for movie_id, score in sorted_movies[:num_recommendations]:
            movie = Movie.query.get(movie_id)
            if movie:
                # Final age check
                if user_age and not is_age_appropriate(movie, user_age):
                    continue
                recommendations.append((movie, score))
        
        return recommendations
    except Exception as e:
        # If collaborative filtering fails, return empty
        return []

def get_content_based_recommendations(user_id, num_recommendations=10, user_age=None, exclude_movie_ids=None):
    """Content-based filtering using genre preferences (with age-aware fallback)."""
    user_preferences = Preference.query.filter_by(user_id=user_id).all()
    preferred_genres = [p.genre for p in user_preferences]
    
    # Base query
    base_query = Movie.query
    
    # Add age rating filter if age is provided
    if user_age:
        if user_age <= 7:
            base_query = base_query.filter((Movie.age_rating == 'G') | (Movie.age_rating == None))
        elif user_age <= 12:
            base_query = base_query.filter((Movie.age_rating.in_(['G', 'PG'])) | (Movie.age_rating == None))
        elif user_age < 18:
            base_query = base_query.filter((Movie.age_rating.in_(['G', 'PG', 'PG-13'])) | (Movie.age_rating == None))
        # For adults (18+), no filter needed
    
    if not preferred_genres:
        # If no preferences, DON'T return "first N" (it often looks identical across ages).
        # Instead, use explicit age-group recommendations.
        if user_age:
            return get_age_based_recommendations(user_age, exclude_movie_ids or [], num_recommendations)
        return base_query.order_by(Movie.year.desc()).limit(num_recommendations).all()
    
    # Get movies matching preferred genres
    recommended_movies = []
    for genre in preferred_genres:
        movies = base_query.filter(Movie.genre.contains(genre)).limit(5).all()
        recommended_movies.extend(movies)
    
    # Remove duplicates
    seen = set()
    unique_movies = []
    for movie in recommended_movies:
        if movie.id not in seen:
            seen.add(movie.id)
            unique_movies.append(movie)
    
    return unique_movies[:num_recommendations]

# Initialize database and seed data
def init_db():
    with app.app_context():
        # Drop and recreate tables to handle schema changes (for development only)
        # In production, use proper migrations (Flask-Migrate)
        try:
            db.drop_all()
            db.create_all()
            print("Database tables created/updated successfully")
        except Exception as e:
            print(f"Note: {e}")
            db.create_all()
        
        # Check if movies already exist
        if Movie.query.count() == 0:
            seed_movies()
        else:
            # Update existing movies to include cast and age_rating if missing
            movies = Movie.query.filter((Movie.cast == None) | (Movie.age_rating == None)).all()
            if movies:
                print("Updating existing movies with cast and age rating information...")
                # Re-seed to update movies
                Movie.query.delete()
                db.session.commit()
                seed_movies()

def seed_movies():
    """Seed database with sample movies"""
    movies_data = [
        {"title": "The Shawshank Redemption", "genre": "Drama", "year": 1994, "director": "Frank Darabont", "cast": "Tim Robbins, Morgan Freeman, Bob Gunton", "age_rating": "R", "poster_url": "https://m.media-amazon.com/images/M/MV5BNDE3ODcxYzMtY2YzZC00NmNlLWJiNDMtZDViZWM2MzIxZDYwXkEyXkFqcGdeQXVyNjAwNDUxODI@._V1_.jpg", "description": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency."},
        {"title": "The Godfather", "genre": "Crime, Drama", "year": 1972, "director": "Francis Ford Coppola", "cast": "Marlon Brando, Al Pacino, James Caan", "age_rating": "R", "poster_url": "https://m.media-amazon.com/images/M/MV5BM2MyNjYxNmUtYTAwNi00MTYxLWJmNWYtYzZlODY3ZTk3OTFlXkEyXkFqcGdeQXVyNzkwMjQ5NzM@._V1_.jpg", "description": "The aging patriarch of an organized crime dynasty transfers control to his reluctant son."},
        {"title": "The Dark Knight", "genre": "Action, Crime, Drama", "year": 2008, "director": "Christopher Nolan", "cast": "Christian Bale, Heath Ledger, Aaron Eckhart", "age_rating": "PG-13", "poster_url": "https://m.media-amazon.com/images/M/MV5BMTMxNTMwODM0NF5BMl5BanBnXkFtZTcwODAyMTk2Mw@@._V1_.jpg", "description": "Batman faces the Joker, a criminal mastermind who seeks to undermine Batman's influence."},
        {"title": "Pulp Fiction", "genre": "Crime, Drama", "year": 1994, "director": "Quentin Tarantino", "cast": "John Travolta, Uma Thurman, Samuel L. Jackson", "age_rating": "R", "poster_url": "https://m.media-amazon.com/images/M/MV5BNGNhMDIzZTUtNTBlZi00MTRlLWFjM2ItYzViMjE3Yz5bNjNkXkEyXkFqcGdeQXVyNzkwMjQ5NzM@._V1_.jpg", "description": "The lives of two mob hitmen, a boxer, and others intertwine in four tales of violence and redemption."},
        {"title": "Forrest Gump", "genre": "Drama, Romance", "year": 1994, "director": "Robert Zemeckis", "cast": "Tom Hanks, Robin Wright, Gary Sinise", "age_rating": "PG-13", "poster_url": "https://m.media-amazon.com/images/M/MV5BNWIwODRlZTUtY2U3ZS00Yzg1LWJhNzYtMmZiYmEyYzE3ODZkXkEyXkFqcGdeQXVyMTQxNzMzNDI@._V1_.jpg", "description": "The presidencies of Kennedy and Johnson, the Vietnam War, and other historical events unfold through the perspective of an Alabama man."},
        {"title": "Inception", "genre": "Action, Sci-Fi, Thriller", "year": 2010, "director": "Christopher Nolan", "cast": "Leonardo DiCaprio, Marion Cotillard, Tom Hardy", "age_rating": "PG-13", "poster_url": "https://m.media-amazon.com/images/M/MV5BMjAxMzY3NjcxNF5BMl5BanBnXkFtZTcwNTI5OTM0Mw@@._V1_.jpg", "description": "A thief who steals corporate secrets through dream-sharing technology is given the inverse task of planting an idea."},
        {"title": "The Matrix", "genre": "Action, Sci-Fi", "year": 1999, "director": "Lana Wachowski, Lilly Wachowski", "cast": "Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss", "age_rating": "R", "poster_url": "https://m.media-amazon.com/images/M/MV5BNzQzOTk3OTAtNDQ0Zi00ZTVkLWI0MTEtMDllZjNkYzNjNTc4L2ltYWdlXkEyXkFqcGdeQXVyNjU0OTQ0OTY@._V1_.jpg", "description": "A computer hacker learns about the true nature of reality and his role in the war against its controllers."},
        {"title": "Goodfellas", "genre": "Crime, Drama", "year": 1990, "director": "Martin Scorsese", "cast": "Robert De Niro, Ray Liotta, Joe Pesci", "age_rating": "R", "poster_url": "https://m.media-amazon.com/images/M/MV5BY2NkZjEzMDgtN2RjYy00YzM1LWI4ZmQtMjIwYjFjNmI3ZGEwXkEyXkFqcGdeQXVyNzkwMjQ5NzM@._V1_.jpg", "description": "The story of Henry Hill and his life in the mob, covering his relationship with his wife Karen and his mob partners."},
        {"title": "The Lord of the Rings: The Return of the King", "genre": "Adventure, Drama, Fantasy", "year": 2003, "director": "Peter Jackson", "cast": "Elijah Wood, Viggo Mortensen, Ian McKellen", "age_rating": "PG-13", "poster_url": "https://m.media-amazon.com/images/M/MV5BNzA5ZDNlZWMtM2NhNS00NDJjLTk4NDItNDRjMGFhMDM3YzYxXkEyXkFqcGdeQXVyMTMxODk2OTU@._V1_.jpg", "description": "Gandalf and Aragorn lead the World of Men against Sauron's army to draw his gaze from Frodo and Sam as they approach Mount Doom."},
        {"title": "Fight Club", "genre": "Drama", "year": 1999, "director": "David Fincher", "cast": "Brad Pitt, Edward Norton, Helena Bonham Carter", "age_rating": "R", "poster_url": "https://m.media-amazon.com/images/M/MV5BMmEzNTkxYjQtZTc0MC00YTVjLTg5ZTEtZWMwOWVlYzY0NWIwXkEyXkFqcGdeQXVyNzkwMjQ5NzM@._V1_.jpg", "description": "An insomniac office worker and a devil-may-care soapmaker form an underground fight club that evolves into something much bigger."},
        {"title": "Star Wars: Episode IV - A New Hope", "genre": "Action, Adventure, Fantasy", "year": 1977, "director": "George Lucas", "cast": "Mark Hamill, Harrison Ford, Carrie Fisher", "age_rating": "PG", "poster_url": "https://m.media-amazon.com/images/M/MV5BNzVlY2MwMjktM2E4OS00Y2Y3LWE3ZjctYzhkZGM3YzA1ZWM2XkEyXkFqcGdeQXVyNzkwMjQ5NzM@._V1_.jpg", "description": "Luke Skywalker joins forces with a Jedi Knight, a cocky pilot, a Wookiee and two droids to save the galaxy."},
        {"title": "The Avengers", "genre": "Action, Adventure, Sci-Fi", "year": 2012, "director": "Joss Whedon", "cast": "Robert Downey Jr., Chris Evans, Scarlett Johansson", "age_rating": "PG-13", "poster_url": "https://m.media-amazon.com/images/M/MV5BNDYxNjQyMjAtNTdiOS00NGYwLWFmNTAtNThmYjU5ZGI2YTI1XkEyXkFqcGdeQXVyMTMxODk2OTU@._V1_.jpg", "description": "Earth's mightiest heroes must come together and learn to fight as a team."},
        {"title": "Interstellar", "genre": "Adventure, Drama, Sci-Fi", "year": 2014, "director": "Christopher Nolan", "cast": "Matthew McConaughey, Anne Hathaway, Jessica Chastain", "age_rating": "PG-13", "poster_url": "https://m.media-amazon.com/images/M/MV5BZjdkOTU3MDktN2IxOS00OGEyLWFmMjktY2FiMmZkNWIyODZiXkEyXkFqcGdeQXVyMTMxODk2OTU@._V1_.jpg", "description": "A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival."},
        {"title": "The Silence of the Lambs", "genre": "Crime, Drama, Thriller", "year": 1991, "director": "Jonathan Demme", "cast": "Jodie Foster, Anthony Hopkins, Scott Glenn", "age_rating": "R", "poster_url": "https://m.media-amazon.com/images/M/MV5BNjNhZTk0ZmEtNjJhMi00YzFlLWE1MmEtYzM1M2ZmMGMwMTU4XkEyXkFqcGdeQXVyNjU0OTQ0OTY@._V1_.jpg", "description": "A young F.B.I. cadet must receive the help of an incarcerated and manipulative cannibal killer to help catch another serial killer."},
        {"title": "Titanic", "genre": "Drama, Romance", "year": 1997, "director": "James Cameron", "cast": "Leonardo DiCaprio, Kate Winslet, Billy Zane", "age_rating": "PG-13", "poster_url": "https://m.media-amazon.com/images/M/MV5BMDdmZGU3NDQtY2E5My00ZTliLWIzOTUtMTY4ZGI1YjdiNjk3XkEyXkFqcGdeQXVyNTA4NDY5MzE@._V1_.jpg", "description": "A seventeen-year-old aristocrat falls in love with a kind but poor artist aboard the luxurious, ill-fated R.M.S. Titanic."},
        {"title": "Avatar", "genre": "Action, Adventure, Fantasy", "year": 2009, "director": "James Cameron", "cast": "Sam Worthington, Zoe Saldana, Sigourney Weaver", "age_rating": "PG-13", "poster_url": "https://m.media-amazon.com/images/M/MV5BZDA0OGQxNTItMDZkMC00N2UxLTg3MzItYTJmNjU3MjU3NjQxXkEyXkFqcGdeQXVyMjUzOTY1NTc@._V1_.jpg", "description": "A paraplegic marine dispatched to the moon Pandora on a unique mission becomes torn between following his orders and protecting the world he feels is his home."},
        {"title": "Gladiator", "genre": "Action, Adventure, Drama", "year": 2000, "director": "Ridley Scott", "cast": "Russell Crowe, Joaquin Phoenix, Connie Nielsen", "age_rating": "R", "poster_url": "https://m.media-amazon.com/images/M/MV5BMDliMmNhNDEtODUyOS00MjNlLTgxODEtN2U3NjI3MGVkYzE0XkEyXkFqcGdeQXVyNjU0OTQ0OTY@._V1_.jpg", "description": "A former Roman General sets out to exact vengeance against the corrupt emperor who murdered his family and sent him into slavery."},
        {"title": "The Departed", "genre": "Crime, Drama, Thriller", "year": 2006, "director": "Martin Scorsese", "cast": "Leonardo DiCaprio, Matt Damon, Jack Nicholson", "age_rating": "R", "poster_url": "https://m.media-amazon.com/images/M/MV5BMTI1MTY2OTIxNV5BMl5BanBnXkFtZTYwNjM4NjY3._V1_.jpg", "description": "An undercover cop and a mole in the police attempt to identify each other while infiltrating an Irish gang in South Boston."},
        {"title": "The Prestige", "genre": "Drama, Mystery, Thriller", "year": 2006, "director": "Christopher Nolan", "cast": "Hugh Jackman, Christian Bale, Michael Caine", "age_rating": "PG-13", "poster_url": "https://m.media-amazon.com/images/M/MV5BMjA4NDI0MTkzNV5BMl5BanBnXkFtZTYwNTM0MzY2._V1_.jpg", "description": "Two stage magicians engage in competitive one-upmanship in an attempt to create the ultimate illusion."},
        {"title": "Casino Royale", "genre": "Action, Adventure, Thriller", "year": 2006, "director": "Martin Campbell", "cast": "Daniel Craig, Eva Green, Mads Mikkelsen", "age_rating": "PG-13", "poster_url": "https://m.media-amazon.com/images/M/MV5BMDI5ZWJhOWItYTlhOC00YWNhLTlkNzctNDU5YTI1M2BkNTQzXkEyXkFqcGdeQXVyNTIzOTk5ODM@._V1_.jpg", "description": "After earning 00 status and a licence to kill, Secret Agent James Bond sets out on his first mission as 007."},
        {"title": "Toy Story", "genre": "Animation, Adventure, Family", "year": 1995, "director": "John Lasseter", "cast": "Tom Hanks, Tim Allen, Don Rickles", "age_rating": "G", "poster_url": "https://m.media-amazon.com/images/M/MV5BMDU2ZWJlMjktMTRhMy00ZTA5LWEzNDgtYmNmZTEwZTViZWJkXkEyXkFqcGdeQXVyNDQ2OTk4MzI@._V1_.jpg", "description": "A cowboy doll is profoundly threatened and jealous when a new spaceman figure supplants him as top toy in a boy's room."},
        {"title": "Finding Nemo", "genre": "Animation, Adventure, Family", "year": 2003, "director": "Andrew Stanton", "cast": "Albert Brooks, Ellen DeGeneres, Alexander Gould", "age_rating": "G", "poster_url": "https://m.media-amazon.com/images/M/MV5BZjMxYzBiNjUtZDliNC00MDAyLTg3N2QtOWNjNmNhZGQ1NDg2XkEyXkFqcGdeQXVyNjE2NDQ5NzY@._V1_.jpg", "description": "After his son is captured in the Great Barrier Reef and taken to Sydney, a timid clownfish sets out on a journey to bring him home."},
        {"title": "The Lion King", "genre": "Animation, Adventure, Drama", "year": 1994, "director": "Roger Allers, Rob Minkoff", "cast": "Matthew Broderick, Jeremy Irons, James Earl Jones", "age_rating": "G", "poster_url": "https://m.media-amazon.com/images/M/MV5BYTYxNGMyZTYtMjE3MS00MzNjLWFjNmYtMDk3N2FmM2JiM2M1XkEyXkFqcGdeQXVyNjY5NDU4NzI@._V1_.jpg", "description": "Lion prince Simba and his father are targeted by his bitter uncle, who wants to ascend the throne himself."},
        {"title": "Frozen", "genre": "Animation, Adventure, Family", "year": 2013, "director": "Chris Buck, Jennifer Lee", "cast": "Kristen Bell, Idina Menzel, Jonathan Groff", "age_rating": "PG", "poster_url": "https://m.media-amazon.com/images/M/MV5BMTQ1MjQwMTE5OF5BMl5BanBnXkFtZTgwNjk3MTcyMDE@._V1_.jpg", "description": "When the newly crowned Queen Elsa accidentally uses her power to turn things into ice to curse her home in infinite winter, her sister Anna teams up with a mountain man to break the spell."},
        {"title": "Moana", "genre": "Animation, Adventure, Family", "year": 2016, "director": "Ron Clements, John Musker", "cast": "Auli'i Cravalho, Dwayne Johnson, Rachel House", "age_rating": "PG", "poster_url": "https://m.media-amazon.com/images/M/MV5BMjI4MzU5NTExNF5BMl5BanBnXkFtZTgwNzY1MTEwMDI@._V1_.jpg", "description": "In Ancient Polynesia, when a terrible curse incurred by the Demigod Maui reaches Moana's island, she answers the Ocean's call to seek out the Demigod to set things right."},
        {"title": "Shrek", "genre": "Animation, Adventure, Comedy", "year": 2001, "director": "Andrew Adamson, Vicky Jenson", "cast": "Mike Myers, Eddie Murphy, Cameron Diaz", "age_rating": "PG", "poster_url": "https://m.media-amazon.com/images/M/MV5BOGZhM2FhNTItODAzNi00YjA0LWEyN2UtNjJlYWQzYzU1MDg5L2ltYWdlL2ltYWdlXkEyXkFqcGdeQXVyMTQxNzMzNDI@._V1_.jpg", "description": "A mean lord exiles fairytale creatures to the swamp of a grumpy ogre, who must go on a quest and rescue a princess for the lord in order to get his land back."},
        {"title": "Coco", "genre": "Animation, Adventure, Family", "year": 2017, "director": "Lee Unkrich, Adrian Molina", "cast": "Anthony Gonzalez, Gael García Bernal, Benjamin Bratt", "age_rating": "PG", "poster_url": "https://m.media-amazon.com/images/M/MV5BYjQ5NjM0Y2YtNjxlNC00Y2QxLWJhMjktNzQ4OTYxYjY0YjYyXkEyXkFqcGdeQXVyNjg2NjQwMDQ@._V1_.jpg", "description": "Aspiring musician Miguel, confronted with his family's ancestral ban on music, enters the Land of the Dead to find his great-great-grandfather, a legendary singer."},

        # More KID-friendly picks (to make kid recommendations distinct)
        {"title": "Inside Out", "genre": "Animation, Adventure, Comedy", "year": 2015, "director": "Pete Docter", "cast": "Amy Poehler, Phyllis Smith, Richard Kind", "age_rating": "PG", "poster_url": "", "description": "A young girl's emotions come to life as she navigates a big move and growing up."},
        {"title": "Up", "genre": "Animation, Adventure, Comedy", "year": 2009, "director": "Pete Docter", "cast": "Edward Asner, Jordan Nagai, John Ratzenberger", "age_rating": "PG", "poster_url": "", "description": "An old man ties balloons to his house and flies to South America with an unexpected young stowaway."},
        {"title": "Monsters, Inc.", "genre": "Animation, Adventure, Comedy", "year": 2001, "director": "Pete Docter", "cast": "Billy Crystal, John Goodman, Mary Gibbs", "age_rating": "G", "poster_url": "", "description": "Two monsters discover a little girl in their world and try to return her home."},
        {"title": "Kung Fu Panda", "genre": "Animation, Action, Adventure", "year": 2008, "director": "Mark Osborne, John Stevenson", "cast": "Jack Black, Ian McShane, Angelina Jolie", "age_rating": "PG", "poster_url": "", "description": "A clumsy panda becomes an unlikely kung fu hero."},

        # More YOUTH/TEEN picks (PG-13 leaning, to make youth recommendations distinct)
        {"title": "Spider-Man: Into the Spider-Verse", "genre": "Animation, Action, Adventure", "year": 2018, "director": "Bob Persichetti, Peter Ramsey, Rodney Rothman", "cast": "Shameik Moore, Jake Johnson, Hailee Steinfeld", "age_rating": "PG", "poster_url": "", "description": "A teenager becomes Spider-Man and meets other Spider-heroes from different universes."},
        {"title": "The Hunger Games", "genre": "Action, Adventure, Sci-Fi", "year": 2012, "director": "Gary Ross", "cast": "Jennifer Lawrence, Josh Hutcherson, Liam Hemsworth", "age_rating": "PG-13", "poster_url": "", "description": "A teenager volunteers for a deadly televised competition to save her sister."},
        {"title": "Harry Potter and the Sorcerer's Stone", "genre": "Adventure, Family, Fantasy", "year": 2001, "director": "Chris Columbus", "cast": "Daniel Radcliffe, Rupert Grint, Emma Watson", "age_rating": "PG", "poster_url": "", "description": "A boy discovers he is a wizard and begins his journey at a magical school."},
        {"title": "The Amazing Spider-Man", "genre": "Action, Adventure, Sci-Fi", "year": 2012, "director": "Marc Webb", "cast": "Andrew Garfield, Emma Stone, Rhys Ifans", "age_rating": "PG-13", "poster_url": "", "description": "Peter Parker gains powers and faces a new threat in New York City."},
    ]
    
    for movie_data in movies_data:
        movie = Movie(**movie_data)
        db.session.add(movie)
    
    db.session.commit()
    print(f"Seeded {len(movies_data)} movies into the database")

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
