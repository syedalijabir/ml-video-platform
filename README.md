# Video Search Platform

> AI-powered semantic search across video content using CLIP embeddings and vector cosine similarity

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![AWS](https://img.shields.io/badge/AWS-ECS%20%7C%20RDS%20%7C%20S3-orange.svg)](https://aws.amazon.com/)
[![Pinecone](https://img.shields.io/badge/Pinecone-Vector%20DB-green.svg)](https://www.pinecone.io/)

## Overview

An ML infrastructure that enables natural language search across video content. Upload videos, and search for moments using queries like "people celebrating," "ocean waves," or "dog running in park." The system extracts frames, generates embeddings using OpenAI's CLIP model, and performs semantic similarity matching.

<div align="center">
  <img src="./docs/diagrams/frontend.png" alt="User Interface" width="75%">
</div>
f

### Key Features

- **Semantic Search**: Natural language queries to find specific moments in videos
- **Real-time Processing**: Asynchronous video processing with auto-scaling workers
- **Scalable Architecture**: Container-based deployment with auto-scaling on AWS for high availability
- **Video Playback**: Jump directly to matching timestamps

---

## Architecture
### System Design

<div align="center">
  <img src="./docs/diagrams/top-level.png" alt="Video search high-level architecture" width="90%">
</div>

### Component Details

| Component | Technology | Function |
|-----------|-----------|---------|
| **Load Balancer** | AWS ALB | Traffic distribution, SSL termination |
| **API Service** | ECS Fargate + FastAPI | REST endpoints for upload/search/playback |
| **Worker Service** | ECS Fargate + Python | Background video processing |
| **Container Registry** | Amazon ECR | Docker image storage |
| **Message Queue** | Amazon SQS | Async job processing |
| **Object Storage** | Amazon S3 | Video and frame storage |
| **Relational DB** | Amazon RDS (PostgreSQL) | Metadata and job tracking |
| **Vector DB** | Pinecone | Embedding storage and search |
| **ML Model** | CLIP (Hugging Face) | Image-text embedding generation |

---

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **ML Model**: OpenAI CLIP (via Hugging Face Transformers)
- **Video Processing**: OpenCV, FFmpeg
- **ORM**: SQLAlchemy
- **Task Queue**: Boto3 (SQS client)

### Frontend
- **UI**: Vanilla JavaScript + HTML5
- **Styling**: Custom CSS with modern design
- **Video Player**: HTML5 Video API

### Infrastructure
- **Cloud Provider**: AWS
- **Container Orchestration**: ECS Fargate
- **Database**: PostgreSQL (RDS)
- **Vector Database**: Pinecone
- **Storage**: S3
- **Networking**: VPC, ALB, Security Groups

---

## Prerequisites

- AWS Account with appropriate permissions
- Pinecone account and API key
- Docker installed locally
- Python 3.11+
- Terraform or AWS CDK (for infrastructure)

---

## 🚀 Deployment Guide

### Step 1: Clone Repository

```bash
git clone https://github.com/syedalijabir/ml-video-platform.git
cd ml-video-platform
```

### Step 2: Configure Environment Variables

Make sure the following environment variables are available

```env
APP_NAME=ML Video Platform API

# AWS Configuration
AWS_REGION=<aws_region_name>
AWS_ACCOUNT_ID=123456789012

# RDS Database
DATABASE_URL=<postgresql://user:pass@rds-endpoint:5432/videosearch>

# S3 Configuration
S3_BUCKET_NAME=<bucket_name>
S3_REGION=<aws_region_name>

# SQS Configuration
SQS_QUEUE_URL=<queue_url>

# Pinecone Configuration
PINECONE_API_KEY=<your-api-key-here>
PINECONE_INDEX_NAME=<your-index-name>
```

### Step 3: Build Docker Images

```bash
# Build API service
docker build -t video-search-api:latest -f infrastructure/docker/Dockerfile.api .

# Build Worker service
docker build -t video-search-worker:latest -f infrastructure/docker/Dockerfile.worker .

# Tag and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

docker tag video-search-api:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/video-search-api:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/video-search-api:latest

docker tag video-search-worker:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/video-search-worker:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/video-search-worker:latest
```

### Step 4: Deploy Infrastructure with Terraform

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Review planned changes
terraform plan

# Deploy infrastructure
terraform apply
```

```bash
# Check API health
curl https://video-search.<your_hosted_zone>/health
```

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure:
- Code follows PEP 8 style guide (`flake8`)
- Documentation is updated

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**If you find this project useful, please consider giving it a star on GitHub!**