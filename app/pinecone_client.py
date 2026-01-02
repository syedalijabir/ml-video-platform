from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Any
import numpy as np
from app.config import get_settings

settings = get_settings()

_pinecone_client = None
_index = None


def get_pinecone_client():
    global _pinecone_client
    if _pinecone_client is None:
        _pinecone_client = Pinecone(api_key=settings.pinecone_api_key)
    return _pinecone_client


def get_pinecone_index():
    global _index
    if _index is None:
        pc = get_pinecone_client()        
        _index = pc.Index(settings.pinecone_index_name)
    
    return _index


def upsert_embeddings(
    video_id: str,
    frame_embeddings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Store frame embeddings in Pinecone
    
    Args:
        video_id: ID of the video
        frame_embeddings: List of dicts with:
            - frame_id: unique identifier
            - embedding: numpy array or list
            - metadata: dict with frame_index, timestamp, video_id, etc.
    
    Returns:
        Dict with upsert statistics
    """
    index = get_pinecone_index()
    
    vectors = []
    for frame_data in frame_embeddings:
        embedding = frame_data['embedding']
        
        # Convert numpy array to list
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()
        
        vectors.append({
            'id': frame_data['frame_id'],
            'values': embedding,
            'metadata': frame_data['metadata']
        })
    
    # Upsert in batches of 100 (Pinecone limit)
    batch_size = 100
    total_upserted = 0
    
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        result = index.upsert(vectors=batch)
        total_upserted += result.upserted_count
    
    print(f"Upserted {total_upserted} vectors to Pinecone for video {video_id}")
    
    return {
        'video_id': video_id,
        'upserted_count': total_upserted
    }


def query_similar_frames(
    query_embedding: np.ndarray,
    top_k: int = 50,
    filter_dict: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Query Pinecone for similar frames
    
    Args:
        query_embedding: Query vector (512-dim)
        top_k: Number of results to return
        filter_dict: Optional metadata filters (e.g., {'video_id': 'abc-123'})
    
    Returns:
        List of matches with id, score, and metadata
    """
    index = get_pinecone_index()
    
    # Convert numpy to list
    if isinstance(query_embedding, np.ndarray):
        query_embedding = query_embedding.tolist()
    
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict
    )
    
    matches = []
    for match in results.matches:
        matches.append({
            'frame_id': match.id,
            'score': float(match.score),
            'metadata': match.metadata
        })
    
    return matches


def delete_video_embeddings(video_id: str) -> Dict[str, Any]:
    index = get_pinecone_index()
    
    # Delete by metadata filter
    index.delete(filter={'video_id': video_id})
    
    print(f"Deleted embeddings for video {video_id}")
    
    return {
        'video_id': video_id,
        'deleted': True
    }


def get_index_stats() -> Dict[str, Any]:
    index = get_pinecone_index()
    stats = index.describe_index_stats()
    
    return {
        'total_vectors': stats.total_vector_count,
        'dimension': stats.dimension,
        'index_fullness': stats.index_fullness,
        'namespaces': stats.namespaces
    }
