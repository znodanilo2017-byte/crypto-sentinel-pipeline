# 1. THE SETUP BLOCK
# This tells Terraform: "We are using AWS."
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.16"
    }
  }
  required_version = ">= 1.2.0"
}

# 2. THE LOGIN BLOCK
# This tells Terraform: "Use my credentials and go to Frankfurt."
provider "aws" {
  region  = "eu-central-1"
}

# 3. THE RESOURCE BLOCK (The thing we are building)
# This creates a Storage Bucket (S3) to hold our financial data.
resource "aws_s3_bucket" "finance_data" {
  # CHANGE THIS NAME BELOW TO SOMETHING UNIQUE
  bucket = "crypto-lake-taras-2025-november" 

  tags = {
    Name        = "My Crypto Data Lake"
    Environment = "Dev"
  }
}
# ---------------------------------------------------------
# 1. THE FIREWALL (Security Group)
# This allows traffic on Port 22 (SSH) so you can log in.
# ---------------------------------------------------------
resource "aws_security_group" "crypto_firewall" {
  name        = "crypto-allow-ssh"
  description = "Allow SSH inbound traffic"

  ingress {
    description = "SSH from anywhere"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # WARNING: This allows access from ANY IP. For dev only.
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ---------------------------------------------------------
# 2. THE OS FINDER (Data Source)
# This automatically finds the latest Ubuntu 20.04 ID in Frankfurt.
# ---------------------------------------------------------
data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical (The makers of Ubuntu)
}
# ---------------------------------------------------------
# IAM ROLE: The "Identity" for the Server
# ---------------------------------------------------------
resource "aws_iam_role" "crypto_role" {
  name = "crypto_bot_role_v1"

  # The "Trust Policy" -> Who is allowed to wear this badge? (EC2)
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# ---------------------------------------------------------
# IAM POLICY: The "Permissions" (Access to S3)
# ---------------------------------------------------------
resource "aws_iam_role_policy" "crypto_s3_access" {
  name = "allow_s3_write"
  role = aws_iam_role.crypto_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        # Allow listing buckets and putting files
        Action = [
          "s3:PutObject",
          "s3:ListBucket"
        ]
        # Grant access ONLY to your specific bucket
        Resource = [
          aws_s3_bucket.finance_data.arn,
          "${aws_s3_bucket.finance_data.arn}/*"
        ]
      }
    ]
  })
}
# ---------------------------------------------------------
# NEW: Allow the server to download Docker images (ECR Read Only)
# ---------------------------------------------------------
resource "aws_iam_role_policy_attachment" "ecr_read_only" {
  role       = aws_iam_role.crypto_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}
# ---------------------------------------------------------
# INSTANCE PROFILE: The "Connector" to EC2
# ---------------------------------------------------------
resource "aws_iam_instance_profile" "crypto_profile" {
  name = "crypto_bot_profile_v1"
  role = aws_iam_role.crypto_role.name
}

# ---------------------------------------------------------
# 3. THE SERVER (EC2 Instance)
# ---------------------------------------------------------
resource "aws_instance" "crypto_server" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"
  key_name      = "my-aws-key"
  
  vpc_security_group_ids = [aws_security_group.crypto_firewall.id]
  iam_instance_profile = aws_iam_instance_profile.crypto_profile.name

  tags = {
    Name = "Terraform-Automated-Server"
  }

  # ---------------------------------------------------------
  # THE MAGIC SCRIPT (User Data)
  # This runs as "root" instantly when the server turns on.
  # ---------------------------------------------------------
  user_data = <<-EOF
              #!/bin/bash
              # 1. Update the OS
              apt-get update -y
              
              # 2. Install Docker and AWS CLI
              apt-get install -y docker.io awscli
              
              # 3. Start Docker
              systemctl start docker
              systemctl enable docker
              
              # 4. Add the 'ubuntu' user to the Docker group
              usermod -aG docker ubuntu
              EOF
}