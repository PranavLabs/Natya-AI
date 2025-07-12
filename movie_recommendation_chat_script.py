import os
import requests
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from fastapi import FastAPI, HTTPException
import tmdbsimple as tmdb # Ensure tmdbsimple is imported

# --- API Key Configuration ---
# IMPORTANT:
# For production environments, it is highly recommended to set your API keys
# as environment variables. For example, in your terminal before running:
# export TMDB_API_KEY="your_tmdb_api_key_here"
# export SARVAM_API_KEY="your_sarvam_api_key_here"

# If you are testing locally and prefer not to set environment variables,
# you can uncomment the lines below and replace "YOUR_TMDB_API_KEY" and
# "YOUR_SARVAM_API_KEY" with your actual keys.
# DO NOT commit hardcoded keys to version control in a real project!

# Attempt to get keys from environment variables first
# Fallback to hardcoded values for local testing if environment variables are not set
# Uncomment and replace with your actual keys if needed for quick testing:
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
SARVAM_KEY = os.getenv("SARVAM_API_KEY")

# Set TMDb API key
tmdb.API_KEY = TMDB_API_KEY

# Sarvam AI embedding service configuration
SARVAM_URL = "https://api.sarvam.ai/v1/embeddings"
HEADERS = {"API-Subscription-Key": SARVAM_KEY}

# Initialize FastAPI application
app = FastAPI(
    title="Movie Recommendation System",
    description="API for recommending movies based on user preferences using TMDb and Sarvam AI embeddings.",
    version="1.0.0"
)

# --- Helper Functions ---

def get_genre_ids():
    """
    Fetches movie genre IDs and their names from TMDb.
    Caches the result to avoid repeated API calls.
    Raises HTTPException if TMDb API call fails.
    """
    try:
        g = tmdb.Genres()
        # Fetch movie list and create a dictionary mapping lowercase genre names to their IDs
        genres = {x['name'].lower(): x['id'] for x in g.movie_list()['genres']}
        print(f"Successfully fetched {len(genres)} genres from TMDb.")
        return genres
    except tmdb.exceptions.TMDbException as e:
        print(f"Error fetching genres from TMDb: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not fetch movie genres. Please check your TMDb API key and network connection."
        )
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching genres from TMDb: {e}")
        raise HTTPException(
            status_code=500,
            detail="Network error while fetching movie genres. Please check your internet connection."
        )

# Global variable to store genre map, initialized once
GENRE_MAP = get_genre_ids()

def parse_genres(user_text: str) -> list[int]:
    """
    Parses user input text to identify relevant TMDb genre IDs.
    If no specific genres are found, it defaults to 'drama'.
    """
    # Convert user text to lowercase for case-insensitive matching
    user_text_lower = user_text.lower()
    # Find genre IDs where the genre name (key) is present in the user's text
    hits = [GENRE_MAP[w] for w in GENRE_MAP if w in user_text_lower]
    # Return found genres or default to 'drama' if no matches
    return hits or [GENRE_MAP['drama']]

def discover_movies(genre_ids: list[int], pages: int = 2) -> list[dict]:
    """
    Discovers movies from TMDb based on a list of genre IDs.
    Fetches movies from multiple pages (default 2) and caps the results to 100.
    Includes error handling for TMDb API calls.
    """
    movies = []
    discover = tmdb.Discover()
    for p in range(1, pages + 1):
        try:
            # Make the API call to discover movies with specified genres
            resp = discover.movie(with_genres=','.join(map(str, genre_ids)), page=p)
            movies.extend(resp['results'])
            print(f"Fetched {len(resp['results'])} movies from TMDb page {p}.")
        except tmdb.exceptions.TMDbException as e:
            print(f"Error discovering movies from TMDb (page {p}): {e}")
            # Log the error but continue to try fetching from other pages
            continue
        except requests.exceptions.RequestException as e:
            print(f"Network error discovering movies from TMDb (page {p}): {e}")
            continue
    # Cap the total number of movies to 100 to manage latency and processing load
    return movies[:100]

def embed(text_list: list[str]) -> np.ndarray:
    """
    Generates embeddings for a list of texts using the Sarvam AI embedding service.
    Handles network errors and unexpected API responses.
    """
    payload = {"input": text_list, "model": "sarvam-embed:v1"}
    try:
        # Send POST request to Sarvam AI embedding service
        r = requests.post(SARVAM_URL, json=payload, headers=HEADERS, timeout=15)
        r.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        response_data = r.json()
        # Extract embeddings from the response
        vecs = [item['embedding'] for item in response_data.get('data', [])]
        if not vecs:
            raise ValueError("No embeddings found in Sarvam AI response.")
        print(f"Successfully generated {len(vecs)} embeddings from Sarvam AI.")
        return np.array(vecs, dtype=np.float32)
    except requests.exceptions.RequestException as e:
        print(f"Error calling Sarvam AI embedding service: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Could not generate text embeddings from Sarvam AI. Error: {e}"
        )
    except KeyError:
        print(f"Unexpected response structure from Sarvam AI: {r.json()}")
        raise HTTPException(
            status_code=500,
            detail="Unexpected response format from embedding service. 'data' or 'embedding' key missing."
        )
    except ValueError as e:
        print(f"Data error from Sarvam AI: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Data error from embedding service: {e}"
        )

def rank_by_similarity(user_paragraph: str, movies: list[dict], top_k: int = 10) -> list[dict]:
    """
    Ranks movies by their semantic similarity to the user's preference paragraph.
    Uses cosine similarity between the user's text embedding and movie overviews' embeddings.
    Returns the top_k most similar movies.
    """
    if not movies:
        return []

    # Generate embedding for the user's preference paragraph
    user_vec = embed([user_paragraph])

    # Filter movies that have an overview and collect their overviews
    movies_with_overview = [m for m in movies if m.get('overview')]
    synopses = [m['overview'] for m in movies_with_overview]

    if not synopses:
        print("No movie overviews available for similarity ranking.")
        return [] # No synopses to compare

    # Generate embeddings for movie overviews
    movie_vecs = embed(synopses)

    # Calculate cosine similarity between user vector and movie overview vectors
    # [0] is used because cosine_similarity returns a 2D array, and we need the first row
    sims = cosine_similarity(user_vec, movie_vecs)[0]

    # Pair movies (that had overviews) with their similarity scores
    movies_and_sims = list(zip(movies_with_overview, sims))

    # Sort movies by similarity score in descending order
    ranked = sorted(movies_and_sims, key=lambda x: x[1], reverse=True)

    # Prepare the final list of top_k recommended movies
    recommended_movies = []
    for m, s in ranked[:top_k]:
        recommended_movies.append({
            "title": m.get('title', 'N/A'),
            "score": round(s, 3), # Round score for cleaner output
            "overview": m.get('overview', 'No overview available')
        })
    print(f"Ranked {len(recommended_movies)} movies by similarity.")
    return recommended_movies

# --- FastAPI Endpoint ---

@app.post("/recommend")
def recommend_movies(pref: dict):
    """
    **Movie Recommendation Endpoint**

    This endpoint takes a user's movie preference description and returns
    a list of recommended movies.

    **Request Body:**
    - `text`: A string describing the user's movie preferences (e.g., "I want a thrilling action movie with a strong female lead").

    **Example Request:**
    ```json
    {
        "text": "A heartwarming comedy about friendship and overcoming challenges."
    }
    ```

    **Response:**
    A list of dictionaries, each containing:
    - `title`: The movie title.
    - `score`: A similarity score (higher is better).
    - `overview`: A brief synopsis of the movie.

    **Possible HTTP Errors:**
    - `400 Bad Request`: If the 'text' field is missing or invalid in the request body.
    - `404 Not Found`: If no movies are found for the inferred genres or if ranking fails.
    - `500 Internal Server Error`: For issues with TMDb or Sarvam AI API calls, or unexpected errors.
    """
    # Validate input: ensure 'text' key exists and its value is a string
    if 'text' not in pref or not isinstance(pref['text'], str) or not pref['text'].strip():
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid 'text' field in request body. Please provide a string."
        )

    user_preference_text = pref['text'].strip()
    print(f"Received user preference: '{user_preference_text}'")

    try:
        # 1. Parse genres from user preference
        genres = parse_genres(user_preference_text)
        print(f"Inferred genre IDs: {genres}")

        # 2. Discover movies based on genres
        movies = discover_movies(genres)
        if not movies:
            raise HTTPException(
                status_code=404,
                detail="No movies found for the specified genres. Try a different description."
            )
        print(f"Discovered {len(movies)} movies.")

        # 3. Rank movies by similarity to user preference
        ranked_movies = rank_by_similarity(user_preference_text, movies)

        if not ranked_movies:
            raise HTTPException(
                status_code=404,
                detail="Could not rank movies based on your preference. Try a more detailed description."
            )

        print(f"Returning {len(ranked_movies)} recommended movies.")
        return ranked_movies

    except HTTPException as e:
        # Re-raise HTTPExceptions that were already created by helper functions
        raise e
    except Exception as e:
        # Catch any other unexpected errors and return a generic 500 error
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An internal server error occurred: {e}"
        )
