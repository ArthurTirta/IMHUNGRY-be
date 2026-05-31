from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import items, auth, chat, library, recipe

app = FastAPI(title="IMHUNGRY API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(items.router, prefix="/api")
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(library.router)
app.include_router(recipe.router)


@app.get("/")
def root():
    return {"message": "Welcome to IMHUNGRY API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
