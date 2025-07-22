import asyncio
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import SentenceTransformer
import os
import json
import numpy as np
import logging
from database.models.thesisai import Ticker, Point
from database.db import session_scope
from sqlalchemy.exc import SQLAlchemyError
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import func
# Load environment variables and initialize OpenAI client
ENV_PATH = os.getenv("ENV_PATH")
load_dotenv(ENV_PATH)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY ENVIRONMENT VARIABLE IS EITHER EMPTY OR DOESN'T EXIST")
client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------
# Utility Functions
# -------------------------

#finlang_model = SentenceTransformer("FinLang/finance-embeddings-investopedia")
finlang_model = SentenceTransformer("all-MiniLM-L6-v2")

def compute_finlang_embedding(text:str) -> np.array:
    """
    Compute the embedding for the provided text using the FinLang embedding model.
    Returns the embedding as a numpy array.
    """
    
    return np.array(finlang_model.encode(text))

def cosine_sim(vec1: np.array, vec2: np.array) -> float:
    """
    Compute the cosine similarity between two vectors.
    """
    return cosine_similarity([vec1], [vec2])[0][0]


# -------------------------
# Database Retrieval
# -------------------------

def get_existing_points_as_dicts(ticker_id: int) -> List:
    """
    Retrieve existing thesis points for the given ticker, including their stored embeddings.
    Returns a list of dictionaries.
    """
    with session_scope() as session:
        points = session.query(Point).filter(Point.ticker_id == ticker_id).all()
        points_list =[
                {
                    "point": point.text,
                    "sentiment_score": point.sentiment_score,
                    "embedding": point.embedding  # Stored embedding (list of floats)
                }
                for point in points
            ]
        return points_list

# -------------------------
# Duplicate Filtering Function
# -------------------------

async def remove_duplicate_points(new_points: List, ticker_id: int, threshold: float = 0.40) -> Dict:
    """
    Remove duplicate thesis points by comparing new points against those already stored in the database.
    
    Process:
      1. Retrieve existing thesis points (with embeddings) for the given ticker.
      2. For each new thesis point (which should also include a "post_id" field), compute its embedding.
      3. Compute cosine similarity between the new point's embedding and each existing point's embedding.
      4. If the maximum similarity exceeds the threshold, consider it a duplicate; otherwise, save the new point (with its embedding)
         to the database and include it in the output.
    
    Returns a dictionary with the filtered (unique) thesis points.
    """
    # Retrieve existing points (including embeddings) & Prepare lists for existing embeddings and texts
    existing_points = get_existing_points_as_dicts(ticker_id)
    existing_embeddings = [np.array(pt["embedding"]) for pt in existing_points if pt.get("embedding")]
    existing_point_texts = [pt.get("point") for pt in existing_points if pt.get("point")]

    unique_points = []
    # Maintain two lists for candidate points:
    # 1. candidate_points_for_gpt: sent to GPT (without embedding)
    # 2. candidate_points_full: contains embedding locally
    candidate_points_for_gpt = []
    candidate_points_full = []
    
    # Create a list of tasks to compute embeddings concurrently.
    # We'll only compute embeddings for points that have a valid post_id.
    tasks = []
    valid_new_points = []
    for pt in new_points:
        if "post_id" not in pt:
            logging.warning(f"Point dictionary for point '{pt}' does not include post_id. Skipping...")
            continue
        valid_new_points.append(pt)
        # Offload compute_finlang_embedding to a thread.
        tasks.append(asyncio.to_thread(compute_finlang_embedding, pt["point"]))
    
    # Gather all embeddings concurrently 
    new_embeddings = await asyncio.gather(*tasks)

    # Iterate through the points and their computed embeddings.
    for pt, new_embedding in zip(valid_new_points, new_embeddings):
        text = pt["point"]
        sentiment = pt["sentiment_score"]
        post_id = pt["post_id"]
        emb_list = new_embedding.tolist()
        
        # Compare with existing embeddings to check for duplicates
        is_duplicate = False
        if existing_embeddings:
            sims = [cosine_sim(new_embedding, emb) for emb in existing_embeddings]
            max_sim = max(sims) if sims else 0.0
            if max_sim >= threshold:
                is_duplicate = True
        
        if not is_duplicate:
            unique_points.append({
                "point": text,
                "sentiment_score": sentiment,
                "embedding": emb_list,
                "post_id": post_id
            })
        else:
            print("COULDNT FILTER DUPLICATE, PASSING TO GPT")
            # Add candidate without embedding for GPT
            candidate_points_for_gpt.append({
                "point": text,
                "sentiment_score": sentiment,
                "post_id": post_id
            })
            # Also store the full candidate with embedding locally
            candidate_points_full.append({
                "point": text,
                "sentiment_score": sentiment,
                "post_id": post_id,
                "embedding": emb_list
            })
    
    # Use GPT to further filter candidate points
    if candidate_points_for_gpt:
        system_prompt = (
            "You are a financial analysis assistant. Your task is to compare two lists of thesis points "
            "and determine which points from the candidate list express a unique idea that is not already "
            "present in the existing list. A thesis point is considered a duplicate if it conveys the same core idea, "
            "even if the phrasing is slightly different. Return only the candidate points that are unique, in JSON format "
            "with the following schema: {\"thesis_points\": [{\"point\": \"string\", \"sentiment_score\": number, \"post_id\": number}]}."
        )

        user_prompt = (
            f"Candidate New Thesis Points:\n{json.dumps(candidate_points_for_gpt, indent=2)}\n\n"
            f"Existing Thesis Points:\n{json.dumps(existing_point_texts, indent=2)}"
        )

        response = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "thesis_summarization",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "thesis_points": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "point": {"type": "string"},
                                        "sentiment_score": {"type": "integer"},
                                        "post_id": {"type": "integer"}
                                    },
                                    "required": ["point", "sentiment_score", "post_id"],
                                    "additionalProperties": False
                                }
                            }
                        },
                        "required": ["thesis_points"],
                        "additionalProperties": False
                    }
                }
            }
        )

        gpt_filtered = json.loads(response.output_text)
        filtered_candidates = gpt_filtered.get("thesis_points", [])

        # For each candidate returned by GPT, look up the full candidate (the one with embedding)
        for candidate in filtered_candidates:
            # Here we're matching on both 'post_id' and 'point' to be safe
            full_candidate = next(
                (item for item in candidate_points_full
                 if item["post_id"] == candidate["post_id"] and item["point"] == candidate["point"]),
                None
            )
            if full_candidate:
                unique_points.append(full_candidate)
    
    return unique_points

if __name__ == "__main__":
    ticker = "spry"
    new_points_list = [{'point': 'Epinephrine nasal spray available by prescription since September.', 'sentiment_score': 60, 'post_id': 6}, {'point': 'Shelf life of 30 months compared to 18 months for Epipen.', 'sentiment_score': 70, 'post_id': 6}, {'point': 'Renaissance Lakewood, LLC, partnered for production, expanding to meet demand.', 'sentiment_score': 65, 'post_id': 6}, {'point': 'Device may not be covered by insurance; not covered by Medicare.', 'sentiment_score': 45, 'post_id': 6}, {'point': 'Pushback from the medical community for speed of delivery concerns.', 'sentiment_score': 40, 'post_id': 6}, {'point': 'Better suited for home use, less likely for hospital use.', 'sentiment_score': 50, 'post_id': 6}, {'point': 'Launched first FDA-approved needle-free epinephrine nasal spray for severe allergic reactions.', 'sentiment_score': 75, 'post_id': 9}, {'point': 'Early sales have exceeded expectations.', 'sentiment_score': 80, 'post_id': 9}, {'point': 'Targets several segments within severe allergic reactions and could become an OTC medication.', 'sentiment_score': 78, 'post_id': 9}, {'point': 'Plans to expand indications into CSU and pediatric use.', 'sentiment_score': 74, 'post_id': 9}, {'point': 'Risks related to insurance coverage policies and competition with traditional auto-injectors.', 'sentiment_score': 40, 'post_id': 9}, {'point': 'First non-injectable epinephrine nasal spray launched in U.S. and Europe.', 'sentiment_score': 75, 'post_id': 10}, {'point': '140% year-to-date stock increase driven by product launch.', 'sentiment_score': 80, 'post_id': 10}, {'point': 'Solid balance sheet with $205 million in cash.', 'sentiment_score': 70, 'post_id': 10}, {'point': 'Received $145 million upfront payment from licensing deal with ALK-Abelló.', 'sentiment_score': 72, 'post_id': 10}, {'point': 'Uncertain demand curve shortly after commercialization start.', 'sentiment_score': 45, 'post_id': 10}, {'point': 'Notable insider selling recorded in November.', 'sentiment_score': 40, 'post_id': 10}]
    with session_scope() as session:
        ticker_obj = session.query(Ticker).filter(func.lower(Ticker.symbol) == ticker.lower()).first()

    results = asyncio.run(remove_duplicate_points(new_points=new_points_list, ticker_obj=ticker_obj))
    for result in results:
        result.pop("embedding", None)
    print(results)
