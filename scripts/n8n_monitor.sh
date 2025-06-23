#!/bin/bash

# N8N Monitoring and Management Script
# This script provides monitoring, alerting, and management functions for n8n

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
LOG_DIR="${HOME}/.n8n/logs"
METRICS_FILE="$LOG_DIR/metrics.log"
ALERT_THRESHOLD_CPU=80
ALERT_THRESHOLD_MEMORY=80
ALERT_THRESHOLD_DISK=90

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_DIR/monitor.log"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >> "$LOG_DIR/monitor.log"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] SUCCESS: $1" >> "$LOG_DIR/monitor.log"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1" >> "$LOG_DIR/monitor.log"
}

# Check if n8n containers are running
check_containers() {
    log "Checking n8n container status..."
    
    local containers=("n8n" "traefik")
    local failed_containers=()
    
    for container in "${containers[@]}"; do
        if ! docker ps --filter "name=$container" --filter "status=running" | grep -q "$container"; then
            failed_containers+=("$container")
        fi
    done
    
    if [[ ${#failed_containers[@]} -eq 0 ]]; then
        success "All n8n containers are running"
        return 0
    else
        error "Failed containers: ${failed_containers[*]}"
        return 1
    fi
}

# Get container resource usage
get_container_metrics() {
    local container_name="$1"
    
    # Get container stats (CPU, Memory)
    local stats=$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" "$container_name" 2>/dev/null)
    
    if [[ -n "$stats" ]]; then
        echo "$stats" | tail -n +2
    else
        echo "N/A N/A N/A N/A"
    fi
}

# Monitor system resources
monitor_resources() {
    log "Monitoring system resources..."
    
    # CPU Usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    
    # Memory Usage
    local memory_info=$(free | grep Mem)
    local total_mem=$(echo $memory_info | awk '{print $2}')
    local used_mem=$(echo $memory_info | awk '{print $3}')
    local memory_usage=$(echo "scale=2; $used_mem * 100 / $total_mem" | bc)
    
    # Disk Usage
    local disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    # Log metrics
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    echo "$timestamp,CPU,$cpu_usage" >> "$METRICS_FILE"
    echo "$timestamp,Memory,$memory_usage" >> "$METRICS_FILE"
    echo "$timestamp,Disk,$disk_usage" >> "$METRICS_FILE"
    
    # Check thresholds
    if (( $(echo "$cpu_usage > $ALERT_THRESHOLD_CPU" | bc -l) )); then
        warning "High CPU usage: ${cpu_usage}%"
        send_alert "High CPU usage: ${cpu_usage}%"
    fi
    
    if (( $(echo "$memory_usage > $ALERT_THRESHOLD_MEMORY" | bc -l) )); then
        warning "High memory usage: ${memory_usage}%"
        send_alert "High memory usage: ${memory_usage}%"
    fi
    
    if [[ $disk_usage -gt $ALERT_THRESHOLD_DISK ]]; then
        warning "High disk usage: ${disk_usage}%"
        send_alert "High disk usage: ${disk_usage}%"
    fi
    
    success "Resource monitoring completed"
    echo "CPU: ${cpu_usage}%, Memory: ${memory_usage}%, Disk: ${disk_usage}%"
}

# Monitor n8n specific metrics
monitor_n8n_metrics() {
    log "Monitoring n8n specific metrics..."
    
    # Get n8n container metrics
    local n8n_metrics=$(get_container_metrics "n8n")
    local traefik_metrics=$(get_container_metrics "traefik")
    
    log "n8n Container: $n8n_metrics"
    log "Traefik Container: $traefik_metrics"
    
    # Check n8n health endpoint
    if curl -sf "http://localhost:5678/healthz" >/dev/null 2>&1; then
        success "n8n health check passed"
    else
        error "n8n health check failed"
        send_alert "n8n health check failed"
        return 1
    fi
    
    # Get workflow execution stats
    local workflow_stats=$(get_workflow_stats)
    log "Workflow Stats: $workflow_stats"
}

# Get workflow execution statistics
get_workflow_stats() {
    # This would require n8n API access
    # For now, we'll get basic container logs info
    local recent_logs=$(docker logs n8n --since="1h" 2>&1 | wc -l)
    echo "Recent log entries (1h): $recent_logs"
}

# Send alert notification
send_alert() {
    local message="$1"
    local timestamp=$(date +'%Y-%m-%d %H:%M:%S')
    
    log "ALERT: $message"
    
    # Write to alert log
    echo "[$timestamp] ALERT: $message" >> "$LOG_DIR/alerts.log"
    
    # Send to webhook if configured
    if [[ -n "$ALERT_WEBHOOK_URL" ]]; then
        curl -X POST "$ALERT_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"text\": \"🚨 n8n Alert: $message\", \"timestamp\": \"$timestamp\"}" \
            >/dev/null 2>&1 || true
    fi
    
    # Send email if configured
    if [[ -n "$ALERT_EMAIL" ]]; then
        echo "Subject: n8n Alert: $message
        
Alert: $message
Time: $timestamp
Server: $(hostname)

This is an automated alert from n8n monitoring system." | \
        sendmail "$ALERT_EMAIL" 2>/dev/null || true
    fi
}

# Restart n8n if unhealthy
auto_restart() {
    log "Checking if n8n needs restart..."
    
    if ! check_containers || ! monitor_n8n_metrics; then
        warning "n8n appears unhealthy, attempting restart..."
        
        # Try graceful restart first
        docker compose -f docker-compose.n8n.yml restart n8n
        
        # Wait for it to come back up
        sleep 30
        
        if check_containers && curl -sf "http://localhost:5678/healthz" >/dev/null 2>&1; then
            success "n8n restarted successfully"
            send_alert "n8n was restarted successfully after health check failure"
        else
            error "n8n restart failed"
            send_alert "n8n restart failed - manual intervention required"
            return 1
        fi
    else
        success "n8n is healthy, no restart needed"
    fi
}

# Generate monitoring report
generate_report() {
    local report_file="$LOG_DIR/report-$(date +%Y%m%d-%H%M%S).txt"
    
    log "Generating monitoring report..."
    
    {
        echo "=========================================="
        echo "n8n Monitoring Report"
        echo "Generated: $(date)"
        echo "=========================================="
        echo ""
        
        echo "Container Status:"
        docker ps --filter "name=n8n" --filter "name=traefik" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        echo ""
        
        echo "Resource Usage:"
        echo "$(monitor_resources 2>/dev/null)"
        echo ""
        
        echo "Recent Alerts (last 24h):"
        if [[ -f "$LOG_DIR/alerts.log" ]]; then
            tail -n 50 "$LOG_DIR/alerts.log" | grep "$(date -d '1 day ago' +%Y-%m-%d)" || echo "No alerts in the last 24 hours"
        else
            echo "No alerts found"
        fi
        echo ""
        
        echo "Recent Logs (last 100 lines):"
        docker logs n8n --tail=100 2>&1
        
    } > "$report_file"
    
    success "Report generated: $report_file"
    echo "$report_file"
}

# Cleanup old logs and reports
cleanup() {
    log "Cleaning up old logs and reports..."
    
    # Clean logs older than 30 days
    find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null || true
    find "$LOG_DIR" -name "report-*.txt" -mtime +7 -delete 2>/dev/null || true
    
    # Clean old docker logs
    docker system prune -f --filter "until=24h" >/dev/null 2>&1 || true
    
    success "Cleanup completed"
}

# Main monitoring loop
monitor_loop() {
    log "Starting continuous monitoring (interval: ${MONITOR_INTERVAL:-300} seconds)..."
    
    while true; do
        check_containers
        monitor_resources
        monitor_n8n_metrics
        
        sleep "${MONITOR_INTERVAL:-300}"
    done
}

# Main script logic
main() {
    case "${1:-status}" in
        "status")
            check_containers
            monitor_resources
            monitor_n8n_metrics
            ;;
        "monitor")
            monitor_loop
            ;;
        "restart")
            auto_restart
            ;;
        "report")
            generate_report
            ;;
        "cleanup")
            cleanup
            ;;
        "alert-test")
            send_alert "Test alert from n8n monitoring system"
            ;;
        *)
            echo "Usage: $0 {status|monitor|restart|report|cleanup|alert-test}"
            echo ""
            echo "Commands:"
            echo "  status     - Check current status"
            echo "  monitor    - Start continuous monitoring"
            echo "  restart    - Auto-restart if unhealthy"
            echo "  report     - Generate monitoring report"
            echo "  cleanup    - Clean old logs and reports"
            echo "  alert-test - Test alert system"
            exit 1
            ;;
    esac
}

# Load environment variables if available
if [[ -f ".env.n8n" ]]; then
    source .env.n8n
fi

# Run main function
main "$@"