from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import numpy as np
import torch
from transformers import CLIPTokenizer, CLIPModel

from app.database import get_db
from app.models import VideoFrame, Video
from app.schemas import SearchRequest, SearchResult, SearchResponse
from app.pinecone_client import query_similar_frames, get_index_stats

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


def _build_pinecone_filter(video_ids: Optional[List[str]]) -> Optional[Dict[str, Any]]:
    if not video_ids:
        return None
    return {"video_id": {"$in": video_ids}}


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
    print(f"  Max videos: {request.max_videos}")

    query_embedding = encode_text_query(request.query)

    # Ask Pinecone for enough candidates to fill:
    #   max_videos * max_results_per_video
    desired = request.max_videos * request.max_results_per_video
    top_k = min(max(desired * 5, 50), 500)  # cap to keep latency sane

    filter_dict = _build_pinecone_filter(request.video_ids)

    try:
        pinecone_matches = query_similar_frames(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_dict=filter_dict,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pinecone query failed: {str(e)}",
        )

    if not pinecone_matches:
        return SearchResponse(
            query=request.query,
            total_videos=0,
            total_matches=0,
            results=[],
            average_similarity=0.0,
        )

    filtered = [m for m in pinecone_matches if float(m.get("score", 0.0)) >= request.threshold]

    print(f"Pinecone returned {len(pinecone_matches)} matches; {len(filtered)} >= threshold")

    video_results: Dict[str, Dict[str, Any]] = {}
    for m in filtered:
        md = m.get("metadata") or {}
        video_id = md.get("video_id")
        video_filename = md.get("video_filename")

        if not video_id:
            continue
        if video_id not in video_results:
            video_results[video_id] = {
                "video_id": video_id,
                "video_filename": video_filename or "unknown",
                "matches": [],
            }

        # early stop criteria
        if len(video_results) >= request.max_videos and video_id not in video_results:
            continue

        if len(video_results[video_id]["matches"]) >= request.max_results_per_video:
            continue

        ts = float(md.get("timestamp", 0.0))
        frame_index = int(md.get("frame_index", 0))

        video_results[video_id]["matches"].append(
            {
                "frame_id": m.get("frame_id"),
                "frame_index": frame_index,
                "timestamp": ts,
                "time_formatted": f"{int(ts // 60)}:{int(ts % 60):02d}",
                "similarity_score": float(m.get("score", 0.0)),
            }
        )

        # If reached max_videos
        if len(video_results) >= request.max_videos:
            all_full = all(
                len(v["matches"]) >= request.max_results_per_video for v in video_results.values()
            )
            if all_full:
                break

    results = list(video_results.values())[: request.max_videos]

    total_matches = sum(len(v["matches"]) for v in results)
    avg_score = (
        float(np.mean([m["similarity_score"] for v in results for m in v["matches"]]))
        if total_matches > 0
        else 0.0
    )

    print(f"   Returning {len(results)} videos with {total_matches} total matches")
    print(f"   Average similarity: {avg_score:.3f}\n")
    print(f"   Returning {len(results)} videos with {total_matches} total matches")
    print(f"   Average similarity: {avg_score:.3f}\n")

    return SearchResponse(
        query=request.query,
        total_videos=len(results),
        total_matches=total_matches,
        results=results,
        average_similarity=avg_score
    )


@router.get("/videos/{video_id}/frames")
async def get_video_frames(
    video_id: str,
    db: Session = Depends(get_db)
):
    frames = (
        db.query(VideoFrame)
        .filter(VideoFrame.video_id == video_id)
        .order_by(VideoFrame.timestamp)
        .all()
    )

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

    # Pinecone stats
    pinecone = {}
    try:
        pinecone = get_index_stats()
    except Exception as e:
        pinecone = {"error": str(e)}

    videos_with_frames = (
        db.query(
            Video.id,
            Video.filename,
            func.count(VideoFrame.id).label("frame_count"),
        )
        .join(VideoFrame, Video.id == VideoFrame.video_id, isouter=True)
        .group_by(Video.id, Video.filename)
        .all()
    )

    return {
        "total_videos": total_videos,
        "total_frames": total_frames,
        "avg_frames_per_video_db": (total_frames / total_videos) if total_videos > 0 else 0,
        "pinecone": pinecone,
        "videos": [
            {
                "video_id": v.id,
                "filename": v.filename,
                "frame_count_db": v.frame_count or 0,
            }
            for v in videos_with_frames
        ],
    }
