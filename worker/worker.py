#!/usr/bin/env python3
import json
import time
import boto3
import os
import tempfile
import signal
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from worker.video_analyzer import VideoAnalyzer
from app.models import ProcessingJob, JobStatus, VideoFrame, Video
from app.config import get_settings

settings = get_settings()

# Graceful shutdown handler
shutdown_flag = False
def signal_handler(signum, frame):
    global shutdown_flag
    print(f"\nReceived signal {signum}. Initiating graceful shutdown...")
    shutdown_flag = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Configuration
MAX_MESSAGES = int(os.getenv('MAX_MESSAGES_PER_BATCH', '1'))
WAIT_TIME_SECONDS = int(os.getenv('SQS_WAIT_TIME', '20'))
VISIBILITY_TIMEOUT = int(os.getenv('VISIBILITY_TIMEOUT', '900'))  # 15 minutes
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '10'))

s3_client = boto3.client('s3', region_name=settings.aws_region)
sqs_client = boto3.client('sqs', region_name=settings.aws_region)

# Database
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

print("Initializing CLIP model...")
analyzer = VideoAnalyzer()
print("CLIP model loaded successfully")


def update_job_status(db, job_id: str, status: JobStatus, **kwargs):
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job:
            job.status = status
            for key, value in kwargs.items():
                setattr(job, key, value)
            db.commit()
            db.refresh(job)
            return job
        else:
            print(f"Warning: Job {job_id} not found in database")
            return None
    except Exception as e:
        print(f"Error updating job status: {e}")
        db.rollback()
        return None


def store_frame_embeddings(db, video_id: str, frames_data: list, embeddings_array):
    """
    Store frame embeddings in database for semantic search
    
    Args:
        db: Database session
        video_id: ID of the video
        frames_data: List of dicts with frame_index and timestamp
        embeddings_array: numpy array of embeddings (n_frames, 512)
    """
    print(f"Storing {len(frames_data)} frame embeddings")
    
    # Delete existing frames for this video (in case of reprocessing)
    db.query(VideoFrame).filter(VideoFrame.video_id == video_id).delete()
    
    # Create VideoFrame objects
    video_frames = []
    for i, frame_info in enumerate(frames_data):
        embedding_list = embeddings_array[i].tolist()  # Convert numpy to list
        
        video_frame = VideoFrame(
            video_id=video_id,
            frame_index=frame_info['frame_index'],
            timestamp=frame_info['timestamp'],
            embedding=embedding_list
        )
        video_frames.append(video_frame)
    
    # Bulk insert
    db.bulk_save_objects(video_frames)
    db.commit()
    
    print(f"Stored {len(video_frames)} frame embeddings")
    return len(video_frames)


def process_message(message, db):
    start_time = time.time()
    receipt_handle = message['ReceiptHandle']
    
    try:
        body = json.loads(message['Body'])
        job_id = body['job_id']
        video_id = body['video_id']
        s3_key = body['s3_key']
        s3_bucket = body['s3_bucket']
        
        print(f"Processing job: {job_id}")
        print(f"Video ID: {video_id}")
        print(f"S3 Location: s3://{s3_bucket}/{s3_key}")
        
        update_job_status(
            db, job_id,
            status=JobStatus.PROCESSING,
            started_at=datetime.utcnow()
        )
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            tmp_path = tmp_file.name
            print(f"Downloading from S3")
            
            try:
                s3_client.download_file(s3_bucket, s3_key, tmp_path)
                file_size = os.path.getsize(tmp_path)
                print(f"Downloaded {file_size / (1024*1024):.2f} MB to {tmp_path}")
            except Exception as e:
                print(f"S3 download failed: {e}")
                raise
        
        print(f"Analyzing video with model")        
        frames, video_info = analyzer.extract_frames(tmp_path, sample_rate=30)
        embeddings = analyzer.generate_frame_embeddings(frames)
        frames_data = [
            {
                'frame_index': i,
                'timestamp': video_info['timestamps'][i]
            }
            for i in range(len(frames))
        ]
        
        embeddings_count = store_frame_embeddings(db, video_id, frames_data, embeddings)
        
        video = db.query(Video).filter(Video.id == video_id).first()
        if video and video.duration_seconds is None:
            video.duration_seconds = video_info['duration']
            db.commit()

        os.unlink(tmp_path)
        print(f"Cleaned up temporary file")
        
        processing_time = time.time() - start_time
        
        update_job_status(
            db, job_id,
            status=JobStatus.COMPLETED,
            completed_at=datetime.utcnow(),
            results={},#results,
            processing_time_seconds=processing_time,
            frames_processed=len(frames),
            embeddings_stored=embeddings_count
        )

        print(f"Job {job_id} completed successfully")
        print(f"Processing time: {processing_time:.2f}s")
        print(f"Frames processed: {len(frames)}")
        print(f"Embeddings stored: {embeddings_count}")
        
        sqs_client.delete_message(
            QueueUrl=settings.sqs_queue_url,
            ReceiptHandle=receipt_handle
        )
        print(f"Message deleted from queue\n")
        
        return True
        
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        
        try:
            body = json.loads(message['Body'])
            job_id = body.get('job_id')
            if job_id:
                update_job_status(
                    db, job_id,
                    status=JobStatus.FAILED,
                    completed_at=datetime.utcnow(),
                    error_message=str(e)
                )
        except Exception as update_error:
            print(f"Failed to update job status: {update_error}")
        
        return False


def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        
        sqs_client.get_queue_attributes(
            QueueUrl=settings.sqs_queue_url,
            AttributeNames=['ApproximateNumberOfMessages']
        )
        
        s3_client.head_bucket(Bucket=settings.s3_bucket_name)
        
        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False


def main():
    print(f"Worker started")
    print(f"Queue URL: {settings.sqs_queue_url}")
    print(f"Database: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'configured'}")
    print(f"S3 Bucket: {settings.s3_bucket_name}")
    print(f"Max Messages per Batch: {MAX_MESSAGES}")
    print(f"Wait Time: {WAIT_TIME_SECONDS}s")
    print(f"Visibility Timeout: {VISIBILITY_TIMEOUT}s")
    
    if not health_check():
        print("Initial health check failed. Exiting...")
        sys.exit(1)
    
    print("Health check passed. Starting to poll for messages\n")
    
    consecutive_errors = 0
    max_consecutive_errors = 10
    
    while not shutdown_flag:
        db = None
        try:
            db = SessionLocal()
            
            response = sqs_client.receive_message(
                QueueUrl=settings.sqs_queue_url,
                MaxNumberOfMessages=MAX_MESSAGES,
                WaitTimeSeconds=WAIT_TIME_SECONDS,
                VisibilityTimeout=VISIBILITY_TIMEOUT,
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            
            if messages:
                print(f"Received {len(messages)} message(s) from queue")
                consecutive_errors = 0
                
                for message in messages:
                    if shutdown_flag:
                        print("Shutdown flag set, stopping message processing")
                        break
                    
                    success = process_message(message, db)
                    if not success:
                        consecutive_errors += 1
                    
            else:
                print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] No messages. Waiting...")
                time.sleep(POLL_INTERVAL)
                
        except KeyboardInterrupt:
            print("\nInterrupt received. Shutting down...")
            break
            
        except Exception as e:
            consecutive_errors += 1
            print(f"\nError: {e}")
            print(f"Consecutive errors: {consecutive_errors}/{max_consecutive_errors}\n")
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"Max consecutive errors reached. Exiting...")
                sys.exit(1)
            
            time.sleep(POLL_INTERVAL)
            
        finally:
            if db:
                db.close()
    
    print("Graceful shutdown complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
