# GridWise LLM

## Run with Docker

### 1. Pull the image

docker pull mostafizsajal/gridwise-llm:latest

### 2. Start the API

docker run --rm -p 8000:8000 mostafizsajal/gridwise-llm:latest

### 3. Check health

Open:

http://127.0.0.1:8000/health

Expected:

{"status":"ok"}

### 4. API endpoint

POST /optimize-energy


### 5. Vercel link
https://gridwise-llm-delta.vercel.app/