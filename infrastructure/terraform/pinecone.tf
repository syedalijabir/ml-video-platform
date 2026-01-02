# Free tier
resource "pinecone_index" "video_frames" {
  name      = "${local.pinecone_index}"
  dimension = 512
  vector_type = "dense"
  metric = "cosine"
  spec = {
    serverless = {
      cloud  = "aws"
      region = "us-east-1"
    }
  }
}