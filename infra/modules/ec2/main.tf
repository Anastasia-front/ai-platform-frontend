resource "aws_instance" "frontend" {
  ami = var.ami

  instance_type = var.instance_type

  key_name = var.key_name

  subnet_id = var.subnet_id

  vpc_security_group_ids = [
    var.security_group
  ]

  iam_instance_profile = var.instance_profile

  user_data = file(var.user_data)

  tags = {
    Name = "${var.project_name}-frontend"
  }
}

