pipeline {
    // Linux agent with Docker CLI + Compose v2, Python 3, Git, and Docker daemon access.
    agent any
    options {
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        timestamps()
        timeout(time: 15, unit: 'MINUTES')
    }
    triggers { githubPush() }
    parameters {
        string(name: 'DEPLOY_DIR', defaultValue: '/srv/telu-campus-vote', description: 'Absolute path shared identically by Jenkins agent and Docker host')
        string(name: 'APP_PORT', defaultValue: '8097', description: 'Frontend port on Docker host')
        string(name: 'HEALTH_BASE_URL', defaultValue: 'http://frontend:80', description: 'Jenkins container on app-net; use http://127.0.0.1:8097 for a host agent')
        booleanParam(name: 'ENABLE_DEMO_TOOLS', defaultValue: false, description: 'Allow explicit demo seed into empty storage')
    }
    environment {
        COMPOSE_PROJECT_NAME = 'telu-campus-vote'
        NIM_HMAC_SECRET = credentials('telu-nim-hmac')
        ADMIN_TOKEN = credentials('telu-admin-token')
        LOGIN_PASSWORD = credentials('telu-voter-password')
    }
    stages {
        stage('Checkout') {
            steps {
                // Configure the repository URL and GitHub PAT credential in Pipeline from SCM.
                checkout scm
                sh 'git rev-parse HEAD'
            }
        }
        stage('Syntax Check') {
            steps {
                sh 'python3 -m py_compile app.py tools/*.py tests/*.py'
                sh 'python3 -m unittest discover -s tests -v'
                sh 'python3 tools/check_candidate_assets.py'
                sh 'docker compose config --quiet'
            }
        }
        stage('Build Image') {
            steps { sh 'docker compose build --pull backend' }
        }
        stage('Automated Deployment') {
            steps {
                sh '''
                    set -eu
                    python3 tools/prepare_deploy.py --directory "$DEPLOY_DIR" --port "$APP_PORT" --demo "$ENABLE_DEMO_TOOLS"
                    docker compose --project-directory "$DEPLOY_DIR" -f "$DEPLOY_DIR/docker-compose.yml" up -d --no-build --force-recreate --remove-orphans --wait --wait-timeout 90
                '''
            }
        }
        stage('Health Check') {
            steps {
                sh 'python3 tools/health_check.py --url "$HEALTH_BASE_URL" --attempts 12 --delay 3'
            }
        }
    }
    post {
        success { echo 'Deployment selesai. Named Volume polling-db-data dipertahankan.' }
        failure { echo 'Pipeline gagal. Periksa log stage terkait; jangan hapus volume untuk memperbaiki build.' }
    }
}
