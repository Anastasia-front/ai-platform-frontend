resource "aws_ecr_repository" "frontend" {
  name = "${var.project_name}-frontend"
}

