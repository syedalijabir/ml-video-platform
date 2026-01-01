output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.lb.dns_name
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for videos"
  value       = aws_s3_bucket.videos.bucket
}

output "sqs_queue_url" {
  description = "URL of the SQS processing queue"
  value       = aws_sqs_queue.processing_queue.url
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}
