pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        timeout(time: 60, unit: 'MINUTES')
    }

    triggers {
        pollSCM('H/5 * * * *')
    }

    environment {
        PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        API_TEST_IMAGE = "resume-optimizer-api:test-${env.BUILD_NUMBER}"
        API_IMAGE = "resume-optimizer-api:ci-${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('API quality') {
            steps {
                sh '''
                    python3 -m unittest discover \
                        --start-directory scripts/tests \
                        --pattern 'test_*.py'
                    docker build --platform linux/amd64 --target test \
                        --tag "$API_TEST_IMAGE" apps/api
                    docker run --rm "$API_TEST_IMAGE" \
                        ruff check app tests
                    docker run --rm "$API_TEST_IMAGE"
                '''
            }
        }

        stage('Web quality') {
            environment {
                NEXT_PUBLIC_FIREBASE_API_KEY = 'ci-placeholder'
                NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN = 'ci.firebaseapp.com'
                NEXT_PUBLIC_FIREBASE_PROJECT_ID = 'ci-project'
                NEXT_PUBLIC_FIREBASE_APP_ID = '1:1:web:ci'
                NEXT_PUBLIC_API_BASE_URL = 'https://api.example.invalid'
            }
            steps {
                sh '''
                    npm --prefix apps/web ci
                    npm --prefix apps/web audit --omit=dev --audit-level=high
                    npm --prefix apps/web run lint
                    npm --prefix apps/web run build
                    test -f apps/web/out/index.html
                    test -f apps/web/out/login.html
                    test -f apps/web/out/dashboard.html
                '''
            }
        }

        stage('Production image') {
            steps {
                sh '''
                    docker build --platform linux/amd64 \
                        --target production \
                        --tag "$API_IMAGE" apps/api
                '''
            }
        }

        stage('Vulnerability gate') {
            steps {
                sh '''
                    docker run --rm \
                        --volume /var/run/docker.sock:/var/run/docker.sock \
                        --volume trivy-cache:/root/.cache/trivy \
                        aquasec/trivy:0.72.0 image \
                        --quiet \
                        --exit-code 1 \
                        --severity CRITICAL,HIGH \
                        --ignore-unfixed \
                        "$API_IMAGE"
                '''
            }
        }

        stage('Production guard') {
            steps {
                sh '''
                    test "$(git rev-parse HEAD)" = \
                        "$(git rev-parse refs/remotes/origin/main)"
                '''
            }
        }

        stage('Deploy API') {
            steps {
                withCredentials([
                    string(credentialsId: 'render-api-key', variable: 'RENDER_API_KEY'),
                    string(credentialsId: 'render-service-id', variable: 'RENDER_SERVICE_ID')
                ]) {
                    sh '''
                        python3 scripts/deploy_render.py \
                            --commit "$(git rev-parse HEAD)"
                    '''
                }
            }
        }

        stage('Deploy web') {
            steps {
                withCredentials([
                    file(
                        credentialsId: 'firebase-service-account',
                        variable: 'GOOGLE_APPLICATION_CREDENTIALS'
                    ),
                    file(
                        credentialsId: 'web-production-env',
                        variable: 'WEB_PRODUCTION_ENV'
                    )
                ]) {
                    sh '''
                        trap 'rm -f apps/web/.env.production.local' EXIT
                        cp "$WEB_PRODUCTION_ENV" apps/web/.env.production.local
                        npm --prefix apps/web run build
                        test -f apps/web/out/index.html
                        test -f apps/web/out/login.html
                        test -f apps/web/out/dashboard.html

                        FIREBASE_PROJECT_ID="$(node -p \
                            "JSON.parse(require('fs').readFileSync(process.env.GOOGLE_APPLICATION_CREDENTIALS, 'utf8')).project_id")"
                        test -n "$FIREBASE_PROJECT_ID"
                        npx --yes firebase-tools@15.24.0 deploy \
                            --only hosting \
                            --project "$FIREBASE_PROJECT_ID" \
                            --non-interactive
                    '''
                }
            }
        }
    }

    post {
        always {
            sh '''
                docker image rm --force "$API_TEST_IMAGE" "$API_IMAGE" \
                    >/dev/null 2>&1 || true
            '''
            deleteDir()
        }
    }
}
