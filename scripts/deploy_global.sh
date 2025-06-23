#!/bin/bash

##############################################################################
# Global Multi-Region Deployment Script for Influence Item v1.0
# 
# This script deploys the influence item system across multiple regions
# with proper load balancing, failover, and monitoring capabilities.
##############################################################################

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_FILE="${PROJECT_ROOT}/logs/global_deployment_$(date +%Y%m%d_%H%M%S).log"

# Default configuration
DEFAULT_REGIONS=("us-east-1" "us-west-2" "eu-west-1" "ap-northeast-2")
DEFAULT_ENVIRONMENT="production"
DEFAULT_VERSION="v1.0"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

##############################################################################
# Utility Functions
##############################################################################

log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log_info() {
    log "${BLUE}[INFO]${NC} $1"
}

log_success() {
    log "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    log "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    log "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check required tools
    local required_tools=("docker" "kubectl" "aws" "terraform" "helm")
    for tool in "${required_tools[@]}"; do
        if ! command -v "${tool}" &> /dev/null; then
            log_error "Required tool '${tool}' is not installed"
            exit 1
        fi
    done
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured"
        exit 1
    fi
    
    log_success "All prerequisites met"
}

create_directories() {
    log_info "Creating necessary directories..."
    
    local dirs=(
        "${PROJECT_ROOT}/logs"
        "${PROJECT_ROOT}/terraform"
        "${PROJECT_ROOT}/helm"
        "${PROJECT_ROOT}/ssl"
        "${PROJECT_ROOT}/geoip"
        "${PROJECT_ROOT}/backups"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "${dir}"
    done
    
    log_success "Directories created"
}

##############################################################################
# Infrastructure Deployment Functions
##############################################################################

deploy_infrastructure() {
    local region=$1
    log_info "Deploying infrastructure in region: ${region}"
    
    # Set AWS region
    export AWS_DEFAULT_REGION="${region}"
    
    # Create Terraform configuration
    cat > "${PROJECT_ROOT}/terraform/main_${region}.tf" << EOF
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "influence-item-terraform-state"
    key    = "global/${region}/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = "${region}"
}

# VPC and Networking
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  
  name = "influence-item-vpc-${region}"
  cidr = "10.0.0.0/16"
  
  azs             = ["\${data.aws_availability_zones.available.names[0]}", "\${data.aws_availability_zones.available.names[1]}"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]
  
  enable_nat_gateway = true
  enable_vpn_gateway = false
  enable_dns_hostnames = true
  enable_dns_support = true
  
  tags = {
    Environment = "${DEFAULT_ENVIRONMENT}"
    Project     = "influence-item"
    Region      = "${region}"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# EKS Cluster
module "eks" {
  source = "terraform-aws-modules/eks/aws"
  
  cluster_name    = "influence-item-${region}"
  cluster_version = "1.28"
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets
  
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = true
  
  node_groups = {
    general = {
      desired_capacity = 3
      max_capacity     = 10
      min_capacity     = 2
      
      instance_types = ["t3.medium"]
      
      k8s_labels = {
        workload-type = "general"
      }
    }
    
    gpu = {
      desired_capacity = 2
      max_capacity     = 6
      min_capacity     = 1
      
      instance_types = ["g4dn.xlarge"]
      
      k8s_labels = {
        workload-type = "gpu-intensive"
        accelerator = "nvidia-tesla-t4"
      }
      
      taints = [
        {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      ]
    }
  }
  
  tags = {
    Environment = "${DEFAULT_ENVIRONMENT}"
    Project     = "influence-item"
    Region      = "${region}"
  }
}

# RDS Aurora Cluster
module "aurora" {
  source = "terraform-aws-modules/rds-aurora/aws"
  
  name           = "influence-item-db-${region}"
  engine         = "aurora-postgresql"
  engine_version = "14.9"
  
  vpc_id  = module.vpc.vpc_id
  subnets = module.vpc.private_subnets
  
  instances = {
    writer = {
      instance_class = "db.r6g.large"
    }
    reader = {
      instance_class = "db.r6g.large"
    }
  }
  
  storage_encrypted = true
  
  manage_master_user_password = true
  
  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"
  preferred_maintenance_window = "sun:04:00-sun:05:00"
  
  tags = {
    Environment = "${DEFAULT_ENVIRONMENT}"
    Project     = "influence-item"
    Region      = "${region}"
  }
}

# ElastiCache Redis Cluster
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id         = "influence-item-redis-${region}"
  description                  = "Redis cluster for influence item"
  
  node_type                    = "cache.r6g.large"
  port                         = 6379
  parameter_group_name         = "default.redis7.cluster.on"
  
  num_cache_clusters           = 3
  
  subnet_group_name            = aws_elasticache_subnet_group.redis.name
  security_group_ids           = [aws_security_group.redis.id]
  
  at_rest_encryption_enabled   = true
  transit_encryption_enabled   = true
  
  tags = {
    Environment = "${DEFAULT_ENVIRONMENT}"
    Project     = "influence-item"
    Region      = "${region}"
  }
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "influence-item-redis-subnet-${region}"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name_prefix = "influence-item-redis-"
  vpc_id      = module.vpc.vpc_id
  
  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [module.vpc.vpc_cidr_block]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "influence-item-redis-${region}"
  }
}

# S3 Buckets
resource "aws_s3_bucket" "assets" {
  bucket = "influence-item-assets-${region}"
  
  tags = {
    Environment = "${DEFAULT_ENVIRONMENT}"
    Project     = "influence-item"
    Region      = "${region}"
  }
}

resource "aws_s3_bucket" "backups" {
  bucket = "influence-item-backups-${region}"
  
  tags = {
    Environment = "${DEFAULT_ENVIRONMENT}"
    Project     = "influence-item"
    Region      = "${region}"
  }
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "assets" {
  origin {
    domain_name = aws_s3_bucket.assets.bucket_regional_domain_name
    origin_id   = "S3-\${aws_s3_bucket.assets.id}"
    
    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.assets.cloudfront_access_identity_path
    }
  }
  
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  
  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-\${aws_s3_bucket.assets.id}"
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }
  
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  
  viewer_certificate {
    cloudfront_default_certificate = true
  }
  
  tags = {
    Environment = "${DEFAULT_ENVIRONMENT}"
    Project     = "influence-item"
    Region      = "${region}"
  }
}

resource "aws_cloudfront_origin_access_identity" "assets" {
  comment = "OAI for influence-item assets in ${region}"
}

# Outputs
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "eks_cluster_name" {
  value = module.eks.cluster_id
}

output "aurora_endpoint" {
  value = module.aurora.cluster_endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_replication_group.redis.configuration_endpoint_address
}

output "cloudfront_domain" {
  value = aws_cloudfront_distribution.assets.domain_name
}
EOF
    
    # Initialize and apply Terraform
    cd "${PROJECT_ROOT}/terraform"
    terraform init
    terraform plan -var="region=${region}"
    terraform apply -auto-approve -var="region=${region}"
    
    log_success "Infrastructure deployed in ${region}"
}

##############################################################################
# Application Deployment Functions
##############################################################################

build_and_push_images() {
    local version=$1
    log_info "Building and pushing Docker images (version: ${version})"
    
    # Build CPU image
    docker build -f "${PROJECT_ROOT}/Dockerfile.cpu" -t "influence-item/cpu-server:${version}" "${PROJECT_ROOT}"
    
    # Build GPU image
    docker build -f "${PROJECT_ROOT}/Dockerfile.gpu" -t "influence-item/gpu-server:${version}" "${PROJECT_ROOT}"
    
    # Tag and push to ECR for each region
    for region in "${REGIONS[@]}"; do
        local ecr_repo_cpu="${AWS_ACCOUNT_ID}.dkr.ecr.${region}.amazonaws.com/influence-item/cpu-server"
        local ecr_repo_gpu="${AWS_ACCOUNT_ID}.dkr.ecr.${region}.amazonaws.com/influence-item/gpu-server"
        
        # Login to ECR
        aws ecr get-login-password --region "${region}" | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${region}.amazonaws.com"
        
        # Create repositories if they don't exist
        aws ecr describe-repositories --repository-names "influence-item/cpu-server" --region "${region}" || aws ecr create-repository --repository-name "influence-item/cpu-server" --region "${region}"
        aws ecr describe-repositories --repository-names "influence-item/gpu-server" --region "${region}" || aws ecr create-repository --repository-name "influence-item/gpu-server" --region "${region}"
        
        # Tag and push
        docker tag "influence-item/cpu-server:${version}" "${ecr_repo_cpu}:${version}"
        docker tag "influence-item/gpu-server:${version}" "${ecr_repo_gpu}:${version}"
        
        docker push "${ecr_repo_cpu}:${version}"
        docker push "${ecr_repo_gpu}:${version}"
    done
    
    log_success "Docker images built and pushed"
}

deploy_application() {
    local region=$1
    local version=$2
    log_info "Deploying application to region: ${region} (version: ${version})"
    
    # Configure kubectl for the region
    aws eks update-kubeconfig --region "${region}" --name "influence-item-${region}"
    
    # Create namespace
    kubectl apply -f - << EOF
apiVersion: v1
kind: Namespace
metadata:
  name: influence-item
  labels:
    name: influence-item
    version: ${version}
    region: ${region}
EOF
    
    # Create secrets
    kubectl create secret generic influence-item-secrets \
        --namespace=influence-item \
        --from-env-file="${PROJECT_ROOT}/.env" \
        --from-env-file="${PROJECT_ROOT}/.env.${region}" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply Kubernetes manifests
    envsubst < "${PROJECT_ROOT}/k8s-manifests.yml" | kubectl apply -f -
    
    # Wait for deployment to be ready
    kubectl wait --namespace=influence-item \
        --for=condition=available \
        --timeout=600s \
        deployment/influence-item-cpu \
        deployment/influence-item-gpu
    
    log_success "Application deployed to ${region}"
}

##############################################################################
# Monitoring and Health Check Functions
##############################################################################

setup_monitoring() {
    local region=$1
    log_info "Setting up monitoring for region: ${region}"
    
    # Install Prometheus and Grafana using Helm
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update
    
    # Install Prometheus
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --create-namespace \
        --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=50Gi \
        --set grafana.persistence.enabled=true \
        --set grafana.persistence.size=10Gi
    
    # Install custom monitoring dashboards
    kubectl apply -f "${PROJECT_ROOT}/monitoring/grafana-dashboards.yml"
    
    log_success "Monitoring setup completed for ${region}"
}

run_health_checks() {
    log_info "Running comprehensive health checks across all regions"
    
    local failed_regions=()
    
    for region in "${REGIONS[@]}"; do
        log_info "Checking health of ${region}..."
        
        # Configure kubectl for the region
        aws eks update-kubeconfig --region "${region}" --name "influence-item-${region}"
        
        # Check if pods are running
        if ! kubectl get pods --namespace=influence-item | grep -q "Running"; then
            log_error "Pods not running in ${region}"
            failed_regions+=("${region}")
            continue
        fi
        
        # Check if services are accessible
        local cpu_service=$(kubectl get service --namespace=influence-item influence-item-cpu-service -o jsonpath='{.spec.clusterIP}')
        local gpu_service=$(kubectl get service --namespace=influence-item influence-item-gpu-service -o jsonpath='{.spec.clusterIP}')
        
        if ! kubectl run --rm -i --tty --restart=Never test-pod --image=curlimages/curl -- curl -f "http://${cpu_service}:8501/_stcore/health"; then
            log_error "CPU service health check failed in ${region}"
            failed_regions+=("${region}")
        fi
        
        if ! kubectl run --rm -i --tty --restart=Never test-pod --image=curlimages/curl -- curl -f "http://${gpu_service}:8001/health"; then
            log_error "GPU service health check failed in ${region}"
            failed_regions+=("${region}")
        fi
        
        log_success "Health check passed for ${region}"
    done
    
    if [ ${#failed_regions[@]} -gt 0 ]; then
        log_error "Health checks failed for regions: ${failed_regions[*]}"
        return 1
    fi
    
    log_success "All health checks passed"
}

##############################################################################
# Main Deployment Orchestration
##############################################################################

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Influence Item system globally across multiple regions.

OPTIONS:
    -r, --regions REGIONS     Comma-separated list of regions (default: us-east-1,us-west-2,eu-west-1,ap-northeast-2)
    -e, --environment ENV     Environment (default: production)
    -v, --version VERSION     Application version (default: v1.0)
    -i, --infra-only         Deploy infrastructure only
    -a, --app-only           Deploy application only
    -m, --monitoring-only    Setup monitoring only
    -h, --help               Show this help message

EXAMPLES:
    $0                                          # Deploy everything to default regions
    $0 -r us-east-1,ap-northeast-2            # Deploy to specific regions
    $0 -i                                      # Deploy infrastructure only
    $0 -a -v v1.1                             # Deploy application only with version v1.1
EOF
}

main() {
    local regions_str=""
    local environment="${DEFAULT_ENVIRONMENT}"
    local version="${DEFAULT_VERSION}"
    local infra_only=false
    local app_only=false
    local monitoring_only=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -r|--regions)
                regions_str="$2"
                shift 2
                ;;
            -e|--environment)
                environment="$2"
                shift 2
                ;;
            -v|--version)
                version="$2"
                shift 2
                ;;
            -i|--infra-only)
                infra_only=true
                shift
                ;;
            -a|--app-only)
                app_only=true
                shift
                ;;
            -m|--monitoring-only)
                monitoring_only=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Set regions array
    if [[ -n "${regions_str}" ]]; then
        IFS=',' read -ra REGIONS <<< "${regions_str}"
    else
        REGIONS=("${DEFAULT_REGIONS[@]}")
    fi
    
    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    log_info "Starting global deployment"
    log_info "Regions: ${REGIONS[*]}"
    log_info "Environment: ${environment}"
    log_info "Version: ${version}"
    log_info "AWS Account: ${AWS_ACCOUNT_ID}"
    
    # Check prerequisites
    check_prerequisites
    create_directories
    
    # Deploy infrastructure
    if [[ "${infra_only}" == true || ("${app_only}" == false && "${monitoring_only}" == false) ]]; then
        for region in "${REGIONS[@]}"; do
            deploy_infrastructure "${region}"
        done
    fi
    
    # Build and deploy application
    if [[ "${app_only}" == true || ("${infra_only}" == false && "${monitoring_only}" == false) ]]; then
        build_and_push_images "${version}"
        
        for region in "${REGIONS[@]}"; do
            deploy_application "${region}" "${version}"
        done
    fi
    
    # Setup monitoring
    if [[ "${monitoring_only}" == true || ("${infra_only}" == false && "${app_only}" == false) ]]; then
        for region in "${REGIONS[@]}"; do
            setup_monitoring "${region}"
        done
    fi
    
    # Run health checks
    run_health_checks
    
    log_success "Global deployment completed successfully!"
    log_info "Application endpoints:"
    for region in "${REGIONS[@]}"; do
        log_info "  ${region}: https://influence-item-${region}.yourdomain.com"
    done
}

# Execute main function with all arguments
main "$@"