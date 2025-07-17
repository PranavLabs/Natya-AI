import os
import requests
import json
import tmdbsimple as tmdb
import re
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Union, Optional

# --- API Key Configuration ---
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
SARVAM_KEY = os.getenv("SARVAM_API_KEY")

if not TMDB_API_KEY:
    raise ValueError(
        "TMDB_API_KEY environment variable is not set. "
        "Please set it in Render project settings."
    )
if not SARVAM_KEY:
    raise ValueError(
        "SARVAM_API_KEY environment variable is not set. "
        "Please set it in Render project settings."
    )

tmdb.API_KEY = TMDB_API_KEY

SARVAM_CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"
HEADERS = {
    "API-Subscription-Key": SARVAM_KEY,
    "Content-Type": "application/json"
}

app = FastAPI(
    title="Movie/TV Show Recommendation Chatbot API",
    description="Provides interactive recommendations using TMDb and Sarvam AI, remembering conversation context.",
    version="1.0.0"
)

# --- CORS Configuration ---
origins = [
    "http://localhost",
    "http://localhost:3000", # React development server
    "http://localhost:8000", # FastAPI development server
    "https://*.onrender.com", # Allows all Render subdomains (e.g., your-app-name.onrender.com)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Serve React Frontend Static Files ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_BUILD_DIR = os.path.join(BASE_DIR, '..', 'build')
FRONTEND_STATIC_ASSETS_DIR = os.path.join(FRONTEND_BUILD_DIR, 'static')

if not os.path.exists(FRONTEND_BUILD_DIR):
    print(f"WARNING: Frontend build directory not found at {FRONTEND_BUILD_DIR}. "
          "The React frontend might not be served correctly. "
          "Ensure 'npm run build' is part of your Render build command.")
if not os.path.exists(FRONTEND_STATIC_ASSETS_DIR):
    print(f"WARNING: Frontend static assets directory not found at {FRONTEND_STATIC_ASSETS_DIR}. "
          "Static files (JS, CSS) might not be served correctly.")

app.mount("/static", StaticFiles(directory=FRONTEND_STATIC_ASSETS_DIR), name="static")

# --- Pydantic Models for Chat Mode ---

class Message(BaseModel):
    role: str
    content: str

# Removed RecommendationItem as AI will return plain text
# class RecommendationItem(BaseModel):
#     title: str = Field(..., description="The title or name of the recommended movie/TV show.")
#     description: str = Field(..., description="A brief, engaging description based on its overview.")
#     type: str = Field(..., description="Whether it's a 'movie' or 'tv show'.")

class ChatResponse(BaseModel):
    # ai_message will now contain the full recommendation text
    ai_message: str = Field(..., description="The AI's natural language response, including recommendations.")
    # Removed recommendations list as AI will return plain text
    # recommendations: Optional[List[RecommendationItem]] = Field(None, description="A list of structured recommendations if applicable.")
    history: List[Message] = Field(..., description="The updated conversation history including the latest turn.")

# --- TMDb Helper Functions (unchanged, as they are accurate for data retrieval) ---

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

# Global variables to store genre maps, initialized once
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
        else: # media_type == 'tv'
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
            print(f"Detected language/industry keyword: '{keyword}', mapping to '{lang_code}'")
            return lang_code
    return None

def discover_movies(genre_ids: list[int], year: int | None = None, language: str | None = None, pages: int = 2) -> list[dict]:
    movies = []
    discover = tmdb.Discover()
    print(f"Discovering movies for genres: {genre_ids} (Year: {year if year else 'Any'}, Language: {language if language else 'Any'})...")

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
            print(f"  Fetched {len(resp['results'])} movies from TMDb page {p}.")
        except tmdb.exceptions.TMDbException as e:
            print(f"  Warning: Error discovering movies from TMDb (page {p}): {e}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"  Warning: Network error discovering movies from TMDb (page {p}): {e}")
            continue
    print(f"Total discovered movies: {len(movies[:100])}")
    return movies[:100]

def discover_tv_shows(genre_ids: list[int], year: int | None = None, language: str | None = None, pages: int = 2) -> list[dict]:
    tv_shows = []
    discover = tmdb.Discover()
    print(f"Discovering TV shows for genres: {genre_ids} (Year: {year if year else 'Any'}, Language: {language if language else 'Any'})...")

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
            print(f"  Fetched {len(resp['results'])} TV shows from TMDb page {p}.")
        except tmdb.exceptions.TMDbException as e:
            print(f"  Warning: Error discovering TV shows from TMDb (page {p}): {e}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"  Warning: Network error discovering TV shows from TMDb (page {p}): {e}")
            continue
    print(f"Total discovered TV shows: {len(tv_shows[:100])}")
    return tv_shows[:100]


# --- Sarvam AI Interaction ---

def get_chat_recommendation(user_preference: str, media_list_from_tmdb: list[dict], media_type: str, conversation_history: List[Message]) -> str:
    print(f"Sending request to Sarvam AI chat model with TMDb {media_type} data and history...")

    media_for_ai_prompt = media_list_from_tmdb[:20] # Limit the list for the LLM context

    media_list_str = ""
    if not media_for_ai_prompt:
        media_list_str = f"No {media_type}s were found from TMDb to recommend from."
    else:
        for i, item in enumerate(media_for_ai_prompt):
            title_or_name = item.get('title', item.get('name', 'N/A'))
            overview = item.get('overview', 'No overview available')
            # Truncate overview to prevent excessively long prompts
            truncated_overview = (overview[:150] + '...') if len(overview) > 150 else overview
            popularity = item.get('popularity', 'N/A')
            vote_average = item.get('vote_average', 'N/A')
            media_list_str += (
                f"Title/Name: {title_or_name}\n"
                f"Overview: {truncated_overview}\n"
                f"Popularity: {popularity}\n"
                f"Rating (Vote Average): {vote_average}\n"
                f"---\n"
            )

    # --- MODIFIED: System message now instructs for natural language/Markdown output ---
    system_message_content = (
        f"You are a helpful and friendly {media_type} recommendation assistant. "
        f"You will be given a user's {media_type} preference and a list of {media_type}s. "
        f"Recommend 3-5 {media_type}s *from the provided list* that best match the user's preference, "
        f"considering their popularity and rating. "
        f"For each recommendation, provide its title/name and a brief, engaging description. "
        f"Format your recommendations clearly using Markdown (e.g., bold titles, bullet points). "
        f"If no good matches, politely state that and suggest trying a different preference or genre. "
        f"Do not invent {media_type}s or details not present in the provided list."
    )

    # Construct messages with history
    messages_for_llm = [
        {"role": "system", "content": system_message_content}
    ]
    # Add previous messages to maintain context
    for msg in conversation_history:
        messages_for_llm.append({"role": msg.role, "content": msg.content})

    # Add the current user query to the messages
    messages_for_llm.append({
        "role": "user",
        "content": (
            f"My current {media_type} preference is: {user_preference}\n\n"
            f"Here is a list of {media_type}s to choose from (sorted by popularity):\n\n{media_list_str}\n"
            f"Please recommend 3-5 {media_type}s from this list that best fit my preference. "
            f"Only recommend {media_type}s from the list provided. "
            f"For each recommendation, state the title/name and a brief description. "
            f"Format your response using Markdown."
        )
    })

    payload = {
        "model": "sarvam-m",
        "messages": messages_for_llm,
        "max_tokens": 500,
        "temperature": 0.5
    }

    print("\n--- Debug Info: Request Payload (to Sarvam AI) ---")
    print(json.dumps(payload, indent=2))
    print(f"Total characters in payload (approx): {len(json.dumps(payload))}")
    print("---------------------------------------------------\n")

    try:
        response = requests.post(SARVAM_CHAT_URL, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()

        response_data = response.json()

        if response_data and response_data.get('choices'):
            ai_response_content = response_data['choices'][0]['message']['content']
            print("Successfully received natural language recommendation from Sarvam AI.")
            print(f"Raw AI Content: {ai_response_content}")
            return ai_response_content # Return the raw string content
        else:
            raise ValueError(f"Unexpected response structure from Sarvam AI: {response_data}")

    except requests.exceptions.RequestException as e:
        print(f"\n--- Debug Info: Raw API Response (if available) ---")
        print(f"HTTP Status Code: {e.response.status_code if hasattr(e, 'response') and e.response is not None else 'N/A'}")
        print(f"HTTP Reason: {e.response.reason if hasattr(e, 'response') and e.response is not None else 'N/A'}")
        if hasattr(e, 'response') and e.response is not None:
            print(e.response.text)
        else:
            print("No raw response text available.")
        print("---------------------------------------------------\n")
        raise RuntimeError(
            f"Error calling Sarvam AI chat completion service: {e}. "
            "This is likely a 4xx or 5xx HTTP error. "
            "Please check your SARVAM_API_KEY, verify the SARVAM_CHAT_URL, "
            "and ensure the 'model' name is correct in the payload."
        ) from e
    except KeyError as e:
        raise RuntimeError(
            f"Unexpected response structure from Sarvam AI: {response_data}. "
            f"Missing key: {e}. 'choices', 'message', or 'content' might be missing."
        ) from e
    except ValueError as e:
        raise RuntimeError(f"Data error from Sarvam AI: {e}") from e

# --- FastAPI Endpoint for Chat ---
class ChatRequest(BaseModel):
    user_message: str
    media_type: str # 'movie' or 'tv'
    history: List[Message] = []

@app.post("/api/chat", response_model=ChatResponse) # Use ChatResponse model for structured output
async def chat_recommendation(request: ChatRequest):
    try:
        user_message = request.user_message
        media_type = request.media_type
        conversation_history = request.history

        if media_type not in ['movie', 'tv']:
            raise HTTPException(status_code=400, detail="Invalid media_type. Must be 'movie' or 'tv'.")

        current_history_for_llm = conversation_history + [Message(role="user", content=user_message)]

        release_year = extract_year(user_message)
        original_language = extract_language(user_message)
        genres = parse_genres(user_message, media_type)

        if media_type == 'movie':
            media_list_from_tmdb = discover_movies(genres, year=release_year, language=original_language)
        else: # media_type == 'tv'
            media_list_from_tmdb = discover_tv_shows(genres, year=release_year, language=original_language)

        if not media_list_from_tmdb:
            ai_msg_content = f"I couldn't find any {media_type}s for your request based on the current criteria. Please try a different description or broaden your search."
            updated_history = current_history_for_llm + [Message(role="assistant", content=ai_msg_content)]
            return ChatResponse(ai_message=ai_msg_content, recommendations=[], history=updated_history)

        # Get recommendation from Sarvam AI, now expecting a plain text/Markdown string
        ai_response_text = get_chat_recommendation(user_message, media_list_from_tmdb, media_type, current_history_for_llm)

        # The ai_message will now be the full text response from Sarvam AI
        ai_message = ai_response_text
        
        # Since Sarvam AI is returning plain text, there are no structured recommendations from it.
        # The frontend will render the ai_message directly.
        recommendations = [] 

        ai_response_for_history = Message(
            role="assistant", 
            content=ai_message, 
        )
        updated_history = current_history_for_llm + [ai_response_for_history]

        return ChatResponse(
            ai_message=ai_message,
            recommendations=recommendations, # This will always be an empty list now
            history=updated_history
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"An unexpected error occurred in /api/chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# --- Catch-all route to serve index.html for React client-side routing ---
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_frontend(full_path: str):
    index_html_path = os.path.join(FRONTEND_BUILD_DIR, 'index.html')
    if not os.path.exists(index_html_path):
        raise HTTPException(status_code=500, detail="Frontend index.html not found. Build might have failed or path is incorrect.")
    return FileResponse(index_html_path)


