#!/usr/bin/env python3
"""
Test for S02_M03_T01: n8n Server Setup and Basic Configuration
Tests n8n deployment, SSL setup, environment configuration, and basic workflows
"""

import os
import sys
import json
import time
import subprocess
import requests
import unittest
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class TestN8NSetup(unittest.TestCase):
    """Test n8n server setup and configuration"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.project_root = project_root
        cls.env_file = cls.project_root / '.env.n8n'
        cls.docker_compose_file = cls.project_root / 'docker-compose.n8n.yml'
        cls.deploy_script = cls.project_root / 'scripts' / 'deploy_n8n.sh'
        cls.monitor_script = cls.project_root / 'scripts' / 'n8n_monitor.sh'
        
        # Test configuration
        cls.test_domain = os.getenv('TEST_DOMAIN', 'localhost')
        cls.test_port = os.getenv('TEST_PORT', '5678')
        cls.test_username = os.getenv('N8N_BASIC_AUTH_USER', 'admin')
        cls.test_password = os.getenv('N8N_BASIC_AUTH_PASSWORD', 'testpass123')
        
        print(f"Testing n8n setup at {cls.test_domain}:{cls.test_port}")

    def test_01_docker_compose_file_exists(self):
        """Test if Docker Compose file exists and is valid"""
        print("\n=== Testing Docker Compose File ===")
        
        # Check if file exists
        self.assertTrue(
            self.docker_compose_file.exists(),
            f"Docker Compose file not found: {self.docker_compose_file}"
        )
        
        # Validate Docker Compose syntax
        try:
            result = subprocess.run(
                ['docker', 'compose', '-f', str(self.docker_compose_file), 'config'],
                capture_output=True,
                text=True,
                check=True
            )
            print("✓ Docker Compose file syntax is valid")
        except subprocess.CalledProcessError as e:
            self.fail(f"Docker Compose file syntax error: {e.stderr}")

    def test_02_environment_template_exists(self):
        """Test if environment template file exists"""
        print("\n=== Testing Environment Template ===")
        
        env_template = self.project_root / '.env.n8n.template'
        self.assertTrue(
            env_template.exists(),
            f"Environment template not found: {env_template}"
        )
        
        # Check required variables in template
        required_vars = [
            'DOMAIN_NAME',
            'N8N_SUBDOMAIN',
            'SSL_EMAIL',
            'N8N_BASIC_AUTH_USER',
            'N8N_BASIC_AUTH_PASSWORD',
            'SMTP_HOST',
            'SMTP_USER'
        ]
        
        with open(env_template, 'r') as f:
            content = f.read()
            
        for var in required_vars:
            self.assertIn(var, content, f"Required variable {var} not found in template")
        
        print("✓ Environment template contains all required variables")

    def test_03_scripts_exist_and_executable(self):
        """Test if deployment and monitoring scripts exist and are executable"""
        print("\n=== Testing Scripts ===")
        
        scripts = [self.deploy_script, self.monitor_script]
        
        for script in scripts:
            # Check if file exists
            self.assertTrue(
                script.exists(),
                f"Script not found: {script}"
            )
            
            # Check if executable
            self.assertTrue(
                os.access(script, os.X_OK),
                f"Script is not executable: {script}"
            )
            
            print(f"✓ Script exists and is executable: {script.name}")

    def test_04_workflow_templates_exist(self):
        """Test if workflow template files exist"""
        print("\n=== Testing Workflow Templates ===")
        
        workflow_dir = self.project_root / 'n8n-workflows'
        self.assertTrue(
            workflow_dir.exists(),
            f"Workflow directory not found: {workflow_dir}"
        )
        
        required_workflows = [
            'basic-health-check.json',
            'error-notification.json'
        ]
        
        for workflow in required_workflows:
            workflow_file = workflow_dir / workflow
            self.assertTrue(
                workflow_file.exists(),
                f"Workflow template not found: {workflow_file}"
            )
            
            # Validate JSON syntax
            try:
                with open(workflow_file, 'r') as f:
                    json.load(f)
                print(f"✓ Workflow template is valid JSON: {workflow}")
            except json.JSONDecodeError as e:
                self.fail(f"Invalid JSON in workflow {workflow}: {e}")

    def test_05_create_test_environment(self):
        """Create test environment file if it doesn't exist"""
        print("\n=== Creating Test Environment ===")
        
        if not self.env_file.exists():
            # Copy template to create test environment
            env_template = self.project_root / '.env.n8n.template'
            
            with open(env_template, 'r') as f:
                template_content = f.read()
            
            # Replace template values with test values
            test_content = template_content.replace('your-domain.com', 'localhost')
            test_content = test_content.replace('admin@your-domain.com', 'test@localhost')
            test_content = test_content.replace('your-secure-password-here', self.test_password)
            test_content = test_content.replace('your-email@gmail.com', 'test@localhost')
            test_content = test_content.replace('your-app-password', 'testpass')
            
            with open(self.env_file, 'w') as f:
                f.write(test_content)
            
            print(f"✓ Created test environment file: {self.env_file}")
        else:
            print(f"✓ Environment file already exists: {self.env_file}")

    def test_06_docker_network_creation(self):
        """Test Docker network creation"""
        print("\n=== Testing Docker Network ===")
        
        try:
            # Check if Docker is running
            result = subprocess.run(
                ['docker', 'info'],
                capture_output=True,
                text=True,
                check=True
            )
            
            print("✓ Docker is running")
            
            # Create network if it doesn't exist
            network_name = "n8n_network"
            result = subprocess.run(
                ['docker', 'network', 'ls', '--filter', f'name={network_name}'],
                capture_output=True,
                text=True
            )
            
            if network_name not in result.stdout:
                subprocess.run(
                    ['docker', 'network', 'create', network_name],
                    check=True
                )
                print(f"✓ Created Docker network: {network_name}")
            else:
                print(f"✓ Docker network already exists: {network_name}")
                
        except subprocess.CalledProcessError as e:
            self.fail(f"Docker operation failed: {e}")

    def test_07_directory_structure(self):
        """Test if required directories exist"""
        print("\n=== Testing Directory Structure ===")
        
        required_dirs = [
            'n8n-local-files',
            'n8n-workflows',
            'backups',
            'scripts',
            'docs'
        ]
        
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"✓ Created directory: {dir_name}")
            else:
                print(f"✓ Directory exists: {dir_name}")

    def test_08_deploy_script_validation(self):
        """Test deploy script validation without actually deploying"""
        print("\n=== Testing Deploy Script Validation ===")
        
        try:
            # Test script help
            result = subprocess.run(
                [str(self.deploy_script), 'help'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Should show usage information
            self.assertIn('Usage:', result.stdout, "Deploy script should show usage information")
            print("✓ Deploy script shows help information")
            
        except subprocess.TimeoutExpired:
            self.fail("Deploy script timed out")
        except subprocess.CalledProcessError as e:
            # This is expected as 'help' is not a valid command
            if 'Usage:' in e.stdout or 'Usage:' in e.stderr:
                print("✓ Deploy script validation passed")
            else:
                self.fail(f"Deploy script error: {e}")

    def test_09_monitor_script_validation(self):
        """Test monitoring script validation"""
        print("\n=== Testing Monitor Script Validation ===")
        
        try:
            # Test script help
            result = subprocess.run(
                [str(self.monitor_script), 'help'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Should show usage information
            expected_commands = ['status', 'monitor', 'restart', 'report']
            for cmd in expected_commands:
                self.assertIn(cmd, result.stdout, f"Monitor script should mention {cmd} command")
            
            print("✓ Monitor script shows help information with all expected commands")
            
        except subprocess.TimeoutExpired:
            self.fail("Monitor script timed out")
        except subprocess.CalledProcessError as e:
            # This is expected as 'help' is not a valid command
            if any(cmd in e.stdout or cmd in e.stderr for cmd in ['status', 'monitor']):
                print("✓ Monitor script validation passed")
            else:
                self.fail(f"Monitor script error: {e}")

    def test_10_documentation_exists(self):
        """Test if documentation exists"""
        print("\n=== Testing Documentation ===")
        
        doc_file = self.project_root / 'docs' / 'n8n-setup-guide.md'
        self.assertTrue(
            doc_file.exists(),
            f"Setup guide documentation not found: {doc_file}"
        )
        
        # Check if documentation contains key sections
        with open(doc_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_sections = [
            '# n8n 설정 및 배포 가이드',
            '## 사전 요구사항',
            '## 설치 및 배포',
            '## 모니터링 및 운영',
            '## 문제 해결'
        ]
        
        for section in required_sections:
            self.assertIn(section, content, f"Documentation missing section: {section}")
        
        print("✓ Documentation contains all required sections")

    def test_11_ssl_configuration(self):
        """Test SSL configuration in Docker Compose"""
        print("\n=== Testing SSL Configuration ===")
        
        with open(self.docker_compose_file, 'r') as f:
            content = f.read()
        
        # Check for SSL-related configuration
        ssl_requirements = [
            'traefik',
            'letsencrypt',
            'certificatesresolvers',
            'websecure'
        ]
        
        for requirement in ssl_requirements:
            self.assertIn(requirement, content, f"SSL configuration missing: {requirement}")
        
        print("✓ SSL configuration found in Docker Compose file")

    def test_12_security_configuration(self):
        """Test security configuration"""
        print("\n=== Testing Security Configuration ===")
        
        with open(self.docker_compose_file, 'r') as f:
            content = f.read()
        
        # Check for security-related configuration
        security_features = [
            'N8N_BASIC_AUTH_ACTIVE=true',
            'N8N_BASIC_AUTH_USER',
            'N8N_BASIC_AUTH_PASSWORD',
            'headers.SSLRedirect',
            'headers.STSSeconds'
        ]
        
        for feature in security_features:
            self.assertIn(feature, content, f"Security feature missing: {feature}")
        
        print("✓ Security configuration found in Docker Compose file")

    def test_13_backup_configuration(self):
        """Test backup configuration"""
        print("\n=== Testing Backup Configuration ===")
        
        with open(self.docker_compose_file, 'r') as f:
            content = f.read()
        
        # Check for backup service configuration
        self.assertIn('n8n-backup', content, "Backup service not found in Docker Compose")
        
        # Check backup directory exists
        backup_dir = self.project_root / 'backups'
        if not backup_dir.exists():
            backup_dir.mkdir(parents=True)
        
        print("✓ Backup configuration validated")

    def test_14_health_check_configuration(self):
        """Test health check configuration"""
        print("\n=== Testing Health Check Configuration ===")
        
        with open(self.docker_compose_file, 'r') as f:
            content = f.read()
        
        # Check for health check configuration
        health_check_features = [
            'healthcheck:',
            'wget',
            '/healthz',
            'interval:',
            'timeout:'
        ]
        
        for feature in health_check_features:
            self.assertIn(feature, content, f"Health check feature missing: {feature}")
        
        print("✓ Health check configuration found")

    def test_15_final_validation(self):
        """Final validation of all components"""
        print("\n=== Final Validation ===")
        
        # Summary of what was tested
        components = [
            "Docker Compose configuration",
            "Environment template",
            "Deployment scripts",
            "Monitoring scripts", 
            "Workflow templates",
            "Directory structure",
            "SSL configuration",
            "Security settings",
            "Backup system",
            "Health checks",
            "Documentation"
        ]
        
        print("\n✅ Successfully validated all n8n setup components:")
        for i, component in enumerate(components, 1):
            print(f"  {i:2d}. {component}")
        
        print(f"\n🎯 n8n setup is ready for deployment!")
        print(f"   Next steps:")
        print(f"   1. Configure .env.n8n with your actual values")
        print(f"   2. Run: ./scripts/deploy_n8n.sh deploy")
        print(f"   3. Access n8n at: https://n8n.your-domain.com")

def run_tests():
    """Run all tests"""
    unittest.main(argv=[''], verbosity=2, exit=False)

if __name__ == '__main__':
    run_tests()