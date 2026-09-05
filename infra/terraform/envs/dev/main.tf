terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

variable "env" { default = "dev" }
variable "region" { default = "us-east-1" }

provider "aws" { region = var.region }

# Phase 0: local docker-compose is source of truth.
# Phase 6 promotes this to RDS + Fargate + S3 + Secrets.
# resource "aws_db_instance" "pil" { ... }
