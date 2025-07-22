
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
import json
import asyncio
from database.db import session_scope
from database.models.thesisai import Post

ENV_PATH = os.getenv("ENV_PATH")
load_dotenv(ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY ENVIRONMENT VARIABLE IS EITHER EMPTY OR DOESN'T EXIST")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def summarize_points_from_post(post_id):
    """
    Summarizes main investment points from the post associated with the gigen post_id using GPT-4o.
    """
    with session_scope() as session:
        post_obj = session.query(Post).filter(Post.id == post_id).first()
        
        post_content = post_obj.content
        ticker_symbol = post_obj.ticker.symbol
        ticker_name = post_obj.ticker.name

    system_prompt = f"""
    Extract the main thesis points from the following financial post regarding the ticker {ticker_symbol} with the name {ticker_name} in bullet form. Only extract thesis points that relate specifically to this stock; ignore any information or points about other stocks.

    For each bullet point, please follow these instructions:

    1. Factual Only: Extract only the factual thesis points; ignore any personal opinions or references to the "user."
    2. Crisp & Short: Make each bullet point concise and straightforward.
    3. Omit Ticker/Name: Do not mention the stock name or ticker (assume that every point refers to that ticker).
    4. Sentiment Score: Assign a sentiment score from 1 to 100 for each bullet point using the following guideline:
    - A score of 50 is neutral.
    - Above 50 indicates a bullish/positive sentiment.
    - Below 50 indicates a bearish/negative sentiment.
    Ensure that the sentiment score accurately reflects the economic impact of the point (e.g., challenges or drawbacks should get a score below 50)‚

    {post_content}
    """

    user_prompt = f"""
    Ticker: {ticker_symbol}
    Name: {ticker_name}
    post content:
    {post_content}
    """

    response = await client.responses.create(
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
                                    "point": {
                                        "type": "string",
                                        "description": "The extracted thesis point text."
                                    },
                                    "sentiment_score": {
                                        "type": "integer",
                                        "description": "The sentiment score, where 50 is neutral, above 50 is bullish, and below 50 is bearish."
                                    }
                                },
                                "required": ["point", "sentiment_score"],
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

    result_dict = json.loads(response.output_text).get("thesis_points")
    for point in result_dict:
        point["post_id"] = post_id
    return result_dict

def run_summarize_points_from_post(post_id):
    import asyncio
    return asyncio.run(summarize_points_from_post(post_id))

async def summarize_all_posts(post_ids):
    tasks = [asyncio.to_thread(run_summarize_points_from_post, pid) for pid in post_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Flatten the list of lists
    return [point for res in results if isinstance(res, list) for point in res]
