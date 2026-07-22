data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "ec2" {
  name   = "${var.project_name}-frontend-ec2-sg"
  vpc_id = data.aws_vpc.default.id

  ingress {
    from_port = 22
    to_port   = 22
    protocol  = "tcp"

    cidr_blocks = var.ssh_allowed_cidrs
  }

  ingress {
    description = "Allow public HTTP traffic to host Nginx"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"

    cidr_blocks = var.http_allowed_cidrs
  }

  ingress {
    description = "Allow public HTTPS traffic"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"

    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
