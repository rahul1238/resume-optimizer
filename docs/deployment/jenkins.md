# Local Jenkins CI

The root `Jenkinsfile` runs verification locally and does not deploy or require
cloud credentials. Jenkins itself is free; Docker Desktop performs the container
builds and Docker Scout performs the vulnerability gate.

## Prerequisites

Install Jenkins LTS on the development machine and make these commands available
to the Jenkins service user:

- `git`
- `node` and `npm`
- `docker`, with Docker Desktop running
- `docker scout`

The pipeline adds the standard Apple Silicon Homebrew and `/usr/local/bin` paths.
If a command is installed elsewhere, add that directory under **Manage Jenkins >
System > Global properties > Environment variables**.

Install only the suggested Jenkins plugins during initial setup, plus **Pipeline**
and **Git** if they are not already present. No paid Jenkins plugin or hosted
Jenkins service is required.

## Create the job

1. Select **New Item**, enter `resume-optimizer`, and choose **Pipeline**.
2. Under **Pipeline**, select **Pipeline script from SCM**.
3. Choose **Git**, enter the repository URL, and add GitHub credentials only if
   the repository is private.
4. Set the branch to `*/main` and the script path to `Jenkinsfile`.
5. Save and select **Build Now**.

The CI pipeline checks out a clean workspace, runs all API tests in the same
Tectonic-enabled Linux runtime used by production, lints and exports the web app,
builds the production API image for Linux AMD64, and fails on critical or high
Docker Scout findings. Placeholder public Firebase values are used only for the
static CI build; no request is made to Firebase or Render.

Deployment stages and their credentials are intentionally deferred to the next
step.
