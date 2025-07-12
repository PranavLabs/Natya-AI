import os
import requests
import json
import tmdbsimple as tmdb
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware # Import CORSMiddleware
from pydantic import BaseModel

# --- API Key Configuration ---
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
SARVAM_KEY = os.getenv("SARVAM_API_KEY")

if not TMDB_API_KEY:
    raise ValueError("TMDB_API_KEY environment variable is not set.")
if not SARVAM_KEY:
    raise ValueError("SARVAM_API_KEY environment variable is not set.")

tmdb.API_KEY = TMDB_API_KEY

SARVAM_CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"
HEADERS = {
    "API-Subscription-Key": SARVAM_KEY,
    "Content-Type": "application/json"
}

app = FastAPI(
    title="Movie/TV Show Recommendation API",
    description="Provides recommendations based on user preferences using TMDb and Sarvam AI."
)

# --- CORS Configuration ---
# IMPORTANT: Replace "YOUR_FRAMER_SITE_DOMAIN.framer.app" with your actual Framer site domain.
# For development/testing, you can use ["*"] to allow all origins, but this is NOT recommended for production.
origins = [
    "http://localhost", # For local testing if you run Framer locally
    "http://localhost:3000", # Common for local React dev servers
    "https://natyamv.onrender.com", # Replace with your actual Framer domain
    # Add any other domains your Framer site might be hosted on (e.g., custom domains)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # List of allowed origins
    allow_credentials=True, # Allow cookies to be included in cross-origin requests
    allow_methods=["*"],    # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],    # Allow all headers in the request
)

# Pydantic model for request body validation
class PreferenceRequest(BaseModel):
    user_preference: str
    media_type: str

# --- TMDb Helper Functions (unchanged) ---

def get_movie_genre_ids():
    try:
        g = tmdb.Genres()
        genres = {x['name'].lower(): x['id'] for x in g.movie_list()['genres']}
        print(f"Successfully fetched {len(genres)} movie genres from TMDb.")
        return genres
    except tmdb.exceptions.TMDbException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching movie genres from TMDb: {e}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Network error fetching movie genres from TMDb: {e}")

def get_tv_genre_ids():
    try:
        g = tmdb.Genres()
        genres = {x['name'].lower(): x['id'] for x in g.tv_list()['genres']}
        print(f"Successfully fetched {len(genres)} TV genres from TMDb.")
        return genres
    except tmdb.exceptions.TMDbException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching TV genres from TMDb: {e}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Network error fetching TV genres from TMDb: {e}")

MOVIE_GENRE_MAP = get_movie_genre_ids()
TV_GENRE_MAP = get_tv_genre_ids()

def parse_genres(user_text: str, media_type: str) -> list[int]:
    user_text_lower = user_text.lower()
    hits = []
    genre_map_to_use = MOVIE_GENRE_MAP if media_type == 'movie' else TV_GENRE_MAP

    if 'anime' in user_text_lower or 'animation' in user_text_lower:
        if 'animation' in genre_map_to_use:
            hits.append(genre_map_to_use['animation'])
        else:
            print(f"Warning: 'Animation' genre not found in TMDb {media_type} genre map. Using default.")

    for w in genre_map_to_use:
        if w in user_text_lower and genre_map_to_use[w] not in hits:
            hits.append(genre_map_to_use[w])
    
    if not hits:
        if media_type == 'movie':
            return [genre_map_to_use.get('drama', list(genre_map_to_use.values())[0])]
        else:
            return [genre_map_to_use.get('documentary', list(genre_map_to_use.values())[0])]
    return hits

def extract_year(user_text: str) -> int | None:
    match = re.search(r'\b(19\d{2}|20\d{2})\b', user_text)
    if match:
        try:
            year = int(match.group(0))
            if 1900 <= year <= 2100:
                return year
        except ValueError:
            pass
    return None

def extract_language(user_text: str) -> str | None:
    user_text_lower = user_text.lower()
    language_map = {
        'hindi': 'hi', 'bollywood': 'hi', 'indian': 'hi',
        'japanese': 'ja', 'korean': 'ko', 'mandarin': 'zh', 'chinese': 'zh',
        'english': 'en', 'hollywood': 'en', 'american': 'en',
        'spanish': 'es', 'french': 'fr', 'german': 'de', 'italian': 'it',
        'arabic': 'ar', 'russian': 'ru', 'portuguese': 'pt'
    }
    for keyword, lang_code in language_map.items():
        if keyword in user_text_lower:
            return lang_code
    return None

def discover_movies(genre_ids: list[int], year: int | None = None, language: str | None = None, pages: int = 2) -> list[dict]:
    movies = []
    discover = tmdb.Discover()
    discover_params = {
        'with_genres': ','.join(map(str, genre_ids)),
        'page': 1,
        'sort_by': 'popularity.desc'
    }
    if year:
        discover_params['primary_release_year'] = year
    if language:
        discover_params['with_original_language'] = language

    for p in range(1, pages + 1):
        discover_params['page'] = p
        try:
            resp = discover.movie(**discover_params)
            movies.extend(resp['results'])
        except tmdb.exceptions.TMDbException as e:
            print(f"  Warning: Error discovering movies from TMDb (page {p}): {e}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"  Warning: Network error discovering movies from TMDb (page {p}): {e}")
            continue
    return movies[:100]

def discover_tv_shows(genre_ids: list[int], year: int | None = None, language: str | None = None, pages: int = 2) -> list[dict]:
    tv_shows = []
    discover = tmdb.Discover()
    discover_params = {
        'with_genres': ','.join(map(str, genre_ids)),
        'page': 1,
        'sort_by': 'popularity.desc'
    }
    if year:
        discover_params['first_air_date_year'] = year
    if language:
        discover_params['with_original_language'] = language

    for p in range(1, pages + 1):
        discover_params['page'] = p
        try:
            resp = discover.tv(**discover_params)
            tv_shows.extend(resp['results'])
        except tmdb.exceptions.TMDbException as e:
            print(f"  Warning: Error discovering TV shows from TMDb (page {p}): {e}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"  Warning: Network error discovering TV shows from TMDb (page {p}): {e}")
            continue
    return tv_shows[:100]

def get_chat_recommendation(user_preference: str, media_list_from_tmdb: list[dict], media_type: str) -> str:
    media_for_ai_prompt = media_list_from_tmdb[:20]

    movie_list_str = ""
    if not media_for_ai_prompt:
        movie_list_str = f"No {media_type}s were found from TMDb to recommend from."
    else:
        for i, item in enumerate(media_for_ai_prompt):
            title_or_name = item.get('title', item.get('name', 'N/A'))
            overview = item.get('overview', 'No overview available')
            popularity = item.get('popularity', 'N/A')
            vote_average = item.get('vote_average', 'N/A')
            movie_list_str += (
                f"Title/Name: {title_or_name}\n"
                f"Overview: {overview}\n"
                f"Popularity: {popularity}\n"
                f"Rating (Vote Average): {vote_average}\n"
                f"---\n"
            )

    messages = [
        {
            "role": "system",
            "content": (
                f"You are a helpful and friendly {media_type} recommendation assistant. "
                f"You will be given a user's {media_type} preference and a list of {media_type}s with their overviews, popularity, and ratings. "
                f"The provided list is already sorted by popularity, with the most popular items at the top. "
                f"Your task is to recommend 3-5 {media_type}s *from the provided list* that best match the user's preference, "
                f"considering their popularity and rating as additional factors. "
                f"For each recommendation, provide the {media_type} title/name and a brief, engaging description based on its overview. "
                f"If no {media_type}s from the provided list are a good match, politely state that and suggest trying a different preference or genre."
                f"Do not invent {media_type}s or details not present in the provided list."
            )
        },
        {
            "role": "user",
            "content": (
                f"My {media_type} preference is: {user_preference}\n\n"
                f"Here is a list of {media_type}s to choose from (sorted by popularity):\n\n{movie_list_str}\n"
                f"Please recommend 3-5 {media_type}s from this list that best fit my preference. "
                f"Only recommend {media_type}s from the list provided. "
                f"For each recommendation, state the title/name and a brief description."
            )
        }
    ]

    payload = {
        "model": "sarvam-m",
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.7
    }

    try:
        response = requests.post(SARVAM_CHAT_URL, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        response_data = response.json()
        if response_data and response_data.get('choices'):
            ai_response = response_data['choices'][0]['message']['content']
            return ai_response
        else:
            raise ValueError(f"Unexpected response structure from Sarvam AI: {response_data}")
    except requests.exceptions.RequestException as e:
        error_detail = f"HTTP Status: {e.response.status_code}, Reason: {e.response.reason}, Response: {e.response.text}" if hasattr(e, 'response') and e.response is not None else str(e)
        raise HTTPException(status_code=500, detail=f"Sarvam AI API Error: {error_detail}")
    except KeyError as e:
        raise HTTPException(status_code=500, detail=f"Sarvam AI response parsing error: Missing key {e}")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Sarvam AI data error: {e}")

# --- FastAPI Endpoint ---
@app.post("/recommend")
async def recommend_media(request: PreferenceRequest):
    try:
        user_preference = request.user_preference
        media_type = request.media_type

        if media_type not in ['movie', 'tv']:
            raise HTTPException(status_code=400, detail="Invalid media_type. Must be 'movie' or 'tv'.")

        release_year = extract_year(user_preference)
        original_language = extract_language(user_preference)
        genres = parse_genres(user_preference, media_type)

        if media_type == 'movie':
            media_list_from_tmdb = discover_movies(genres, year=release_year, language=original_language)
        else: # media_type == 'tv'
            media_list_from_tmdb = discover_tv_shows(genres, year=release_year, language=original_language)

        if not media_list_from_tmdb:
            return {"recommendation": f"No {media_type}s found from TMDb for your criteria. Try a different description or broaden your search."}

        recommendation_text = get_chat_recommendation(user_preference, media_list_from_tmdb, media_type)
        return {"recommendation": recommendation_text}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

