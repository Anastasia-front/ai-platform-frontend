variable "project_name" {
  type = string
}

variable "ami" {}

variable "instance_type" {
  default = "t3.micro"
}

variable "key_name" {
  type = string
}

variable "subnet_id" {}

variable "security_group" {}

variable "instance_profile" {}

variable "user_data" {}

