# Movie Recommendation System - Enhanced Features

## New Features Added

### 1. Age-Based Recommendations
- **User Age Field**: Added `age` field to User model for age-based filtering
- **Age Collection**: Registration form now collects user age (optional)
- **Age-Appropriate Filtering**: 
  - Children (< 13): G and PG rated movies, family-friendly genres
  - Teens (13-17): G, PG, and PG-13 rated movies
  - Adults (18+): All movies with preference for popular ones
- **Age Update**: Users can update their age in Preferences page

### 2. Similarity-Based Recommendations (For Watched Movies)
When a user has watched/rated movies, the system now recommends similar movies based on:

- **Genre Similarity (40% weight)**: Finds movies with matching genres
- **Director Similarity (20% weight)**: Recommends movies by the same director
- **Cast Similarity (20% weight)**: Suggests movies with common actors
- **Year Similarity (20% weight)**: Prefers movies from similar time periods
  - Same era (within 5 years): Full score
  - Recent era (within 10 years): Half score
  - Similar era (within 20 years): Quarter score

### 3. Enhanced Movie Data
- **Cast Information**: Added `cast` field to Movie model (comma-separated list)
- **Age Rating**: Added `age_rating` field (G, PG, PG-13, R, etc.)
- **Updated Seed Data**: All 23 sample movies now include cast and age rating information

### 4. Hybrid Recommendation Algorithm
The recommendation system now uses a multi-layered approach:

1. **Age-Based Filtering** (Priority for new users with age)
   - Filters movies based on age-appropriateness
   - Score: 0.6

2. **Similarity-Based** (For users who watched movies)
   - Analyzes watched movies and finds similar ones
   - Score: Based on similarity match (0.0 - 1.0)

3. **Collaborative Filtering** (When enough user data exists)
   - Finds users with similar tastes
   - Score: 0.4 (normalized)

4. **Content-Based** (Genre preferences)
   - Uses user's preferred genres
   - Score: 0.5 base, +0.2 boost

### 5. Enhanced User Experience
- **Login Message**: Shows personalized message based on age and watched movies
- **Dashboard Header**: Displays recommendation basis (age, watched movies, preferences)
- **Movie Details**: Now shows cast and age rating information
- **Preferences Page**: Allows updating age along with genre preferences

## How It Works

### For New Users (No Watched Movies):
1. If age is provided → Age-based recommendations
2. If genre preferences set → Content-based recommendations
3. Otherwise → Popular movies

### For Users Who Watched Movies:
1. **Similarity Analysis**: System analyzes all watched movies
2. **Multi-Factor Matching**: Finds movies similar in:
   - Genre (40%)
   - Director (20%)
   - Cast (20%)
   - Year/Era (20%)
3. **Combined Scoring**: Combines similarity scores with:
   - Age-appropriateness
   - Collaborative filtering (if available)
   - Genre preferences

### Example Scenario:
**User Profile:**
- Age: 25
- Watched: "The Dark Knight" (rated 5/5)
- Preferences: Action, Crime, Drama

**Recommendations Generated:**
1. **Similarity Match**: "Inception" (same director: Christopher Nolan, similar genre)
2. **Similarity Match**: "The Prestige" (same director, similar year)
3. **Age-Based**: Other PG-13 action movies
4. **Genre Match**: Other Crime/Drama movies
5. **Collaborative**: Movies liked by users who also liked "The Dark Knight"

## Database Changes

### User Model
- Added `age` field (Integer, nullable)

### Movie Model
- Added `cast` field (String, 500 chars)
- Added `age_rating` field (String, 10 chars)

**Note**: On first run after update, the database will be recreated with new schema. Existing data will be lost (development only). In production, use Flask-Migrate for proper migrations.

## Usage

1. **Register** with age (optional but recommended)
2. **Watch/Rate Movies**: Rate movies you've watched
3. **Set Preferences**: Select favorite genres (can also update age here)
4. **Get Recommendations**: Dashboard shows personalized recommendations based on:
   - Your age
   - Movies you've watched
   - Similar movies (genre, cast, director, year)
   - Your genre preferences
   - Similar users' preferences

## Technical Details

### Recommendation Algorithm Flow:
```
1. Check user age → Age-based filtering
2. Check watched movies → Similarity analysis
3. Check user ratings → Collaborative filtering
4. Check preferences → Content-based filtering
5. Combine scores → Sort and return top N
```

### Similarity Calculation:
```python
similarity_score = (
    genre_match * 0.4 +
    director_match * 0.2 +
    cast_match * 0.2 +
    year_match * 0.2
)
```

### Final Score Combination:
```python
final_score = (
    age_based_score * 0.6 +
    similarity_score * 1.0 +
    collaborative_score * 0.4 +
    content_based_score * 0.5
)
```

## Benefits

1. **Better for New Users**: Age-based recommendations provide immediate value
2. **Personalized**: Watched movies drive highly relevant suggestions
3. **Multi-Dimensional**: Considers genre, cast, director, and era
4. **Scalable**: Works with or without extensive user data
5. **Age-Appropriate**: Ensures content suitability for all age groups
