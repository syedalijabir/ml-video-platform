import cv2
import torch
from transformers import CLIPProcessor, CLIPModel, CLIPTokenizer
from PIL import Image
import numpy as np
from typing import List, Dict, Any, Tuple
import tempfile
import os
from collections import defaultdict


class VideoAnalyzer:    
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")
        
        # Load model
        model_name = "openai/clip-vit-base-patch32"
        self.model = CLIPModel.from_pretrained(model_name)
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.tokenizer = CLIPTokenizer.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    
    def extract_frames(self, video_path: str, sample_rate: int = 30) -> Tuple[List[np.ndarray], Dict]:
        """Extract frames from video at specified sample rate"""
        frames = []
        timestamps = []
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        
        frame_count = 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        
        print(f"Processing video: {total_frames} frames, {fps:.2f} FPS, {duration:.2f}s")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % sample_rate == 0:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)
                timestamps.append(frame_count / fps if fps > 0 else frame_count)
            
            frame_count += 1
        
        cap.release()
        
        video_info = {
            "total_frames": total_frames,
            "fps": fps,
            "duration": duration,
            "sampled_frames": len(frames),
            "timestamps": timestamps
        }
        
        print(f"Extracted {len(frames)} frames from {total_frames} total frames")
        return frames, video_info
    
    def generate_frame_embeddings(self, frames: List[np.ndarray]) -> np.ndarray:
        """Generate CLIP embeddings for frames"""
        embeddings = []
        batch_size = 8
        
        for i in range(0, len(frames), batch_size):
            batch_frames = frames[i:i + batch_size]
            pil_images = [Image.fromarray(frame) for frame in batch_frames]
            
            inputs = self.processor(images=pil_images, return_tensors="pt", padding=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            embeddings.append(image_features.cpu().numpy())
        
        return np.vstack(embeddings)
    
    
    def semantic_search(
        self,
        frames: List[np.ndarray],
        timestamps: List[float],
        query: str,
        threshold: float = 0.25
    ) -> List[Dict[str, Any]]:
        """
        Find frames matching a text query
        Example: "a person holding a phone", "people in a meeting"
        """
        print(f"Searching for: '{query}'")
        
        # Generate text embedding for query
        text_inputs = self.tokenizer([query], padding=True, return_tensors="pt")
        text_inputs = {k: v.to(self.device) for k, v in text_inputs.items()}
        
        with torch.no_grad():
            text_features = self.model.get_text_features(**text_inputs)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        
        # Generate image embeddings
        image_embeddings = self.generate_frame_embeddings(frames)
        image_embeddings_tensor = torch.from_numpy(image_embeddings).to(self.device)
        
        # Calculate similarity
        similarity = (image_embeddings_tensor @ text_features.T).squeeze().cpu().numpy()
        
        # Find matching frames above threshold
        matches = []
        for i, score in enumerate(similarity):
            if score > threshold:
                matches.append({
                    "frame_index": i,
                    "timestamp": timestamps[i],
                    "similarity_score": float(score),
                    "time_formatted": f"{int(timestamps[i] // 60)}:{int(timestamps[i] % 60):02d}"
                })
        
        # Sort by similarity
        matches.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        print(f"Found {len(matches)} matching frames")
        return matches
    
