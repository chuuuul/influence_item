#!/bin/bash

# N8N Deployment Script
# This script deploys n8n with Traefik reverse proxy and SSL certificates

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if required files exist
check_prerequisites() {
    log "Checking prerequisites..."
    
    if [[ ! -f "docker-compose.n8n.yml" ]]; then
        error "docker-compose.n8n.yml not found!"
        exit 1
    fi
    
    if [[ ! -f ".env.n8n" ]]; then
        if [[ -f ".env.n8n.template" ]]; then
            warning ".env.n8n not found. Please copy .env.n8n.template to .env.n8n and configure it."
            cp .env.n8n.template .env.n8n
            error "Please edit .env.n8n with your actual configuration values"
            exit 1
        else
            error ".env.n8n.template not found!"
            exit 1
        fi
    fi
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        error "Docker is not running!"
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker >/dev/null 2>&1; then
        error "Docker Compose is not installed!"
        exit 1
    fi
    
    success "Prerequisites check passed"
}

# Create necessary directories
create_directories() {
    log "Creating necessary directories..."
    
    mkdir -p n8n-local-files
    mkdir -p n8n-workflows
    mkdir -p backups
    
    # Set proper permissions
    chmod 755 n8n-local-files
    chmod 755 n8n-workflows
    chmod 755 backups
    
    success "Directories created"
}

# Deploy n8n stack
deploy_n8n() {
    log "Deploying n8n stack..."
    
    # Load environment variables
    source .env.n8n
    
    # Pull latest images
    log "Pulling latest Docker images..."
    docker compose -f docker-compose.n8n.yml pull
    
    # Start the stack
    log "Starting n8n stack..."
    docker compose -f docker-compose.n8n.yml up -d
    
    success "n8n stack deployed"
}

# Wait for services to be ready
wait_for_services() {
    log "Waiting for services to be ready..."
    
    # Wait for n8n to be healthy
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if docker compose -f docker-compose.n8n.yml ps --services --filter "status=running" | grep -q "n8n"; then
            if docker compose -f docker-compose.n8n.yml exec n8n wget --spider -q http://localhost:5678/healthz 2>/dev/null; then
                success "n8n is ready!"
                break
            fi
        fi
        
        log "Waiting for n8n to be ready... (attempt $attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    done
    
    if [[ $attempt -gt $max_attempts ]]; then
        error "n8n failed to start within the expected time"
        exit 1
    fi
}

# Show deployment status
show_status() {
    log "Deployment Status:"
    
    # Load environment variables
    source .env.n8n
    
    echo "========================================"
    echo "n8n Deployment Status"
    echo "========================================"
    echo "n8n URL: https://${N8N_SUBDOMAIN}.${DOMAIN_NAME}"
    echo "Username: ${N8N_BASIC_AUTH_USER}"
    echo "Password: ${N8N_BASIC_AUTH_PASSWORD}"
    echo "========================================"
    
    # Show container status
    docker compose -f docker-compose.n8n.yml ps
    
    # Show logs
    log "Recent logs:"
    docker compose -f docker-compose.n8n.yml logs --tail=20 n8n
}

# Create backup
create_backup() {
    log "Creating backup..."
    
    local backup_name="n8n-backup-$(date +%Y%m%d_%H%M%S)"
    
    # Run backup service
    docker compose -f docker-compose.n8n.yml run --rm n8n-backup
    
    success "Backup completed: ${backup_name}"
}

# Health check
health_check() {
    log "Performing health check..."
    
    # Load environment variables
    source .env.n8n
    
    # Check if containers are running
    if ! docker compose -f docker-compose.n8n.yml ps --services --filter "status=running" | grep -q "n8n"; then
        error "n8n container is not running"
        return 1
    fi
    
    # Check n8n health endpoint
    if ! curl -sf "https://${N8N_SUBDOMAIN}.${DOMAIN_NAME}/healthz" >/dev/null; then
        error "n8n health check failed"
        return 1
    fi
    
    success "Health check passed"
}

# Main script logic
main() {
    case "${1:-deploy}" in
        "deploy")
            check_prerequisites
            create_directories
            deploy_n8n
            wait_for_services
            show_status
            ;;
        "status")
            show_status
            ;;
        "backup")
            create_backup
            ;;
        "health")
            health_check
            ;;
        "stop")
            log "Stopping n8n stack..."
            docker compose -f docker-compose.n8n.yml down
            success "n8n stack stopped"
            ;;
        "restart")
            log "Restarting n8n stack..."
            docker compose -f docker-compose.n8n.yml restart
            wait_for_services
            show_status
            ;;
        "logs")
            docker compose -f docker-compose.n8n.yml logs -f n8n
            ;;
        *)
            echo "Usage: $0 {deploy|status|backup|health|stop|restart|logs}"
            echo ""
            echo "Commands:"
            echo "  deploy   - Deploy n8n stack"
            echo "  status   - Show deployment status"
            echo "  backup   - Create backup"
            echo "  health   - Perform health check"
            echo "  stop     - Stop n8n stack"
            echo "  restart  - Restart n8n stack"
            echo "  logs     - Show n8n logs"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"