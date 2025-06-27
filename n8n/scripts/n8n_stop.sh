#!/bin/bash

# n8n 프로세스 종료
echo "n8n 프로세스를 종료합니다..."
pkill -f "n8n start"
echo "n8n이 종료되었습니다."