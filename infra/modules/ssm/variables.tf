variable "project_name" {
  type = string
}

variable "env_values" {
  type      = map(string)
  sensitive = true
}

