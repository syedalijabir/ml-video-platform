import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
import os

from app.config import get_settings
from app.database import get_db, engine, Base
from app.schemas import HealthCheck
from app.api import videos, jobs, search

settings = get_settings()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    description="ML Video Platform API",
    version="1.0.0",
    docs_url="/docs"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

app.include_router(videos.router, prefix=f"{settings.api_v1_prefix}/videos", tags=["videos"])
app.include_router(jobs.router, prefix=f"{settings.api_v1_prefix}/jobs", tags=["jobs"])
app.include_router(search.router, prefix=f"{settings.api_v1_prefix}/search", tags=["search"])


@app.get("/")
async def serve_frontend():
    """Serve the frontend UI"""
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    return {
        "message": "ML Video Platform API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthCheck)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for load balancers and monitoring"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "database": "connected",
        "s3": "connected",
        "sqs": "connected"
    }
    
    # Check database
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check S3
    try:
        s3 = boto3.client('s3', region_name=settings.aws_region)
        s3.head_bucket(Bucket=settings.s3_bucket_name)
    except ClientError as e:
        health_status["s3"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check SQS
    try:
        sqs = boto3.client('sqs', region_name=settings.aws_region)
        sqs.get_queue_attributes(
            QueueUrl=settings.sqs_queue_url,
            AttributeNames=['ApproximateNumberOfMessages']
        )
    except ClientError as e:
        health_status["sqs"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    return health_status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)