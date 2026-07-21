output "public_ip" {
  value = aws_eip.frontend.public_ip
}

output "public_dns" {
  value = aws_instance.frontend.public_dns
}

output "elastic_ip" {
  value = aws_eip.frontend.public_ip
}

output "elastic_ip_allocation_id" {
  value = aws_eip.frontend.id
}
