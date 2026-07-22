module "network" {
  source = "./modules/network"

  project_name       = var.project_name
  ssh_allowed_cidrs  = var.ssh_allowed_cidrs
  http_allowed_cidrs = var.http_allowed_cidrs
}

module "iam" {
  source = "./modules/iam"

  project_name = var.project_name
  aws_region   = var.aws_region
}

module "ec2" {
  source = "./modules/ec2"

  project_name     = var.project_name
  key_name         = var.key_name
  ami              = var.ec2_ami
  instance_type    = var.frontend_instance_type
  subnet_id        = module.network.subnet_id
  security_group   = module.network.ec2_security_group
  instance_profile = module.iam.instance_profile
  user_data        = "${path.module}/userdata.sh"
}

module "ecr" {
  source = "./modules/ecr"

  project_name = var.project_name
}

module "ssm" {
  source = "./modules/ssm"

  project_name                     = var.project_name
  nginx_origin_certificate         = var.nginx_origin_certificate
  nginx_origin_certificate_version = var.nginx_origin_certificate_version
  nginx_origin_private_key         = var.nginx_origin_private_key
  nginx_origin_private_key_version = var.nginx_origin_private_key_version

  env_values = merge(
    var.env_values,
    {
      BASE_API_URL     = var.backend_base_api_url
      GOOGLE_CLIENT_ID = var.google_client_id
    }
  )
}
