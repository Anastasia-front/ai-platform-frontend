#!/bin/bash
yum update -y

yum install -y docker
service docker start
usermod -a -G docker ec2-user

yum install -y nginx
systemctl enable nginx
systemctl start nginx
