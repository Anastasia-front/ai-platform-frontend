output "parameter_prefix" {
  description = "Prefix used for all frontend SSM parameters."

  value = "/${var.project_name}-frontend"
}

