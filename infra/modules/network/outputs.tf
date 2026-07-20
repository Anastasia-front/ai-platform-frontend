output "vpc_id" {
  value = data.aws_vpc.default.id
}

output "subnet_id" {
  value = data.aws_subnets.default.ids[0]
}

output "ec2_security_group" {
  value = aws_security_group.ec2.id
}

