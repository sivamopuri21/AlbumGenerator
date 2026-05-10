import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        timeout_keep_alive=300,
        limit_max_requests=None,
    )
