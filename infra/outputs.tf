output "instance_id" {
  value = module.ec2.instance_id
}

output "frontend_public_ip" {
  value = module.ec2.public_ip
}

output "frontend_elastic_ip" {
  value = module.ec2.elastic_ip
}

output "frontend_elastic_ip_allocation_id" {
  value = module.ec2.elastic_ip_allocation_id
}

output "frontend_public_dns" {
  value = module.ec2.public_dns
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "ssm_parameter_prefix" {
  value = module.ssm.parameter_prefix
}
