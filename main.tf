provider "aws" {
  region = "eu-central-1"
}

# 1. Create the Repo (If you haven't already)
resource "aws_ecr_repository" "meme_repo" {
  name = "meme-index"
}

# 2. The Role (Let Lambda Run)
resource "aws_iam_role" "lambda_role" {
  name = "meme_index_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}
resource "aws_iam_role_policy" "lambda_dynamo_access" {
  name = "lambda_dynamo_policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Effect   = "Allow"
        Resource = aws_dynamodb_table.meme_history.arn
      }
    ]
  })
}
# Attach basic logging permissions
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# 3. The Function (Points to your Docker Image)
resource "aws_lambda_function" "meme_index" {
  function_name = "meme-index-api"
  package_type  = "Image"
  image_uri     = "555272931561.dkr.ecr.eu-central-1.amazonaws.com/meme-index:latest"
  role          = aws_iam_role.lambda_role.arn
  architectures = ["x86_64"]

  environment {
    variables = {
      COIN_ID = "pepe"
      TABLE_NAME = aws_dynamodb_table.meme_history.name
    }
  }
}

# 4. The Public URL (The "Product")
resource "aws_lambda_function_url" "public_api" {
  function_name      = aws_lambda_function.meme_index.function_name
  authorization_type = "NONE"
}

# Output the URL so you can sell it
output "api_url" {
  value = aws_lambda_function_url.public_api.function_url
}

resource "aws_dynamodb_table" "meme_history" {
  name           = "meme-coin-history"
  billing_mode   = "PAY_PER_REQUEST" # Free tier friendly
  hash_key       = "coin"       # Partition Key (e.g., "pepe")
  range_key      = "timestamp"  # Sort Key (e.g., "2025-11-22T...")

  attribute {
    name = "coin"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }
}