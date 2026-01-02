provider "aws" {
  region = var.region
  assume_role {
    role_arn = "arn:aws:iam::${var.account_id}:role/${var.assume_role}"
  }
}

provider "pinecone" {
    api_key = var.pinecone_api_key
}
