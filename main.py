import requests
from google.transit import gtfs_realtime_pb2
from sentence_transformers import SentenceTransformer
from google import genai
import numpy as np
from fastapi import FastAPI
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("MTA_API_KEY")
url = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts"
response = requests.get(url, headers={"x-api-key": api_key})

feed = gtfs_realtime_pb2.FeedMessage()
feed.ParseFromString(response.content)

alert_strings = []

for entity in feed.entity:
    for translation in entity.alert.header_text.translation:
        if translation.language == "en":
            alert_strings.append(translation.text)

model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(alert_strings)
def find_closest(query_embedding):
    diff = embeddings - query_embedding
    squared = diff ** 2
    row_sums = squared.sum(axis=1)
    closest_index = np.argmin(row_sums)
    return alert_strings[closest_index]

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def ask(question):
    question_embedding = model.encode([question])
    context = find_closest(question_embedding)

    prompt = f"""
    Answer the question using the context below. If the question has anything relevance to the context, 
    answer it. If the question can't be answered using the context, say "I don't know".

    context = {context}
    question = {question}
    """
    response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=prompt
    )
    return response.text

app = FastAPI()
@app.get("/ask")
def ask_endpoint(question:str):
    return ask(question)

if __name__ == "__main__":
    print(ask("Is there any alerts for L train?"))