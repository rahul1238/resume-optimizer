pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        timestamps()
        timeout(time: 45, unit: 'MINUTES')
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
                    docker scout version
                    docker scout cves --exit-code \
                        --only-severity critical,high \
                        "local://$API_IMAGE"
                '''
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
