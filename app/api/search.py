from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import numpy as np
import torch
from transformers import CLIPTokenizer, CLIPModel

from app.database import get_db
from app.models import VideoFrame, Video
from app.schemas import SearchRequest, SearchResult, SearchResponse

router = APIRouter()

# Load CLIP model for text encoding
print("Loading CLIP model for search")
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-base-patch32")
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)
model.eval()
print(f"CLIP model loaded on {device}")


def encode_text_query(query: str) -> np.ndarray:
    inputs = tokenizer([query], padding=True, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    with torch.no_grad():
        text_features = model.get_text_features(**inputs)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
    
    return text_features.cpu().numpy()[0]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


@router.post("/", response_model=SearchResponse)
async def search_videos(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    Search for videos matching a text query    
    """
    print(f"\n Search query: '{request.query}'")
    print(f"  Threshold: {request.threshold}")
    print(f"  Max results per video: {request.max_results_per_video}")
    
    query_embedding = encode_text_query(request.query)
    
    # Get all frames from database
    if request.video_ids:
        # Search only in specific videos
        frames = db.query(VideoFrame, Video).join(
            Video, VideoFrame.video_id == Video.id
        ).filter(
            VideoFrame.video_id.in_(request.video_ids)
        ).all()
    else:
        # Search all videos
        frames = db.query(VideoFrame, Video).join(
            Video, VideoFrame.video_id == Video.id
        ).all()
    
    print(f"   Searching through {len(frames)} frames...")
    
    # Calculate similarities
    matches = []
    for frame, video in frames:
        frame_embedding = np.array(frame.embedding)
        similarity = cosine_similarity(query_embedding, frame_embedding)
        
        if similarity >= request.threshold:
            matches.append({
                'video_id': video.id,
                'video_filename': video.filename,
                'frame_id': frame.id,
                'frame_index': frame.frame_index,
                'timestamp': frame.timestamp,
                'time_formatted': f"{int(frame.timestamp // 60)}:{int(frame.timestamp % 60):02d}",
                'similarity_score': float(similarity)
            })
    
    matches.sort(key=lambda x: x['similarity_score'], reverse=True)    
    print(f"   Found {len(matches)} matching frames")
    
    # Group by video and limit results per video
    video_results = {}
    for match in matches:
        video_id = match['video_id']
        
        if video_id not in video_results:
            video_results[video_id] = {
                'video_id': video_id,
                'video_filename': match['video_filename'],
                'matches': []
            }
        
        if len(video_results[video_id]['matches']) < request.max_results_per_video:
            video_results[video_id]['matches'].append({
                'frame_id': match['frame_id'],
                'frame_index': match['frame_index'],
                'timestamp': match['timestamp'],
                'time_formatted': match['time_formatted'],
                'similarity_score': match['similarity_score']
            })
    
    results = list(video_results.values())[:request.max_videos]
    
    total_matches = sum(len(video['matches']) for video in results)
    avg_score = np.mean([m['similarity_score'] for video in results for m in video['matches']]) if total_matches > 0 else 0.0
    
    print(f"   Returning {len(results)} videos with {total_matches} total matches")
    print(f"   Average similarity: {avg_score:.3f}\n")
    
    return SearchResponse(
        query=request.query,
        total_videos=len(results),
        total_matches=total_matches,
        results=results,
        average_similarity=float(avg_score)
    )


@router.get("/videos/{video_id}/frames")
async def get_video_frames(
    video_id: str,
    db: Session = Depends(get_db)
):
    frames = db.query(VideoFrame).filter(
        VideoFrame.video_id == video_id
    ).order_by(VideoFrame.timestamp).all()
    
    if not frames:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No frames found for video {video_id}"
        )
    
    return {
        "video_id": video_id,
        "frame_count": len(frames),
        "frames": [
            {
                "frame_id": frame.id,
                "frame_index": frame.frame_index,
                "timestamp": frame.timestamp,
                "time_formatted": f"{int(frame.timestamp // 60)}:{int(frame.timestamp % 60):02d}"
            }
            for frame in frames
        ]
    }


@router.get("/stats")
async def get_search_stats(db: Session = Depends(get_db)):
    """Get statistics about indexed videos"""
    total_videos = db.query(func.count(Video.id)).scalar()
    total_frames = db.query(func.count(VideoFrame.id)).scalar()
    
    videos_with_frames = db.query(
        Video.id,
        Video.filename,
        func.count(VideoFrame.id).label('frame_count')
    ).join(
        VideoFrame, Video.id == VideoFrame.video_id, isouter=True
    ).group_by(Video.id, Video.filename).all()
    
    return {
        "total_videos": total_videos,
        "total_frames": total_frames,
        "avg_frames_per_video": total_frames / total_videos if total_videos > 0 else 0,
        "videos": [
            {
                "video_id": v.id,
                "filename": v.filename,
                "frame_count": v.frame_count or 0
            }
            for v in videos_with_frames
        ]
    }
